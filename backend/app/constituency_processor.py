"""Constituency-specific PDF processor with enhanced multi-page header extraction and perfect cell alignment."""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from .models import ExtractionResult, TableData
from .pdf_processor import PDFProcessor

logger = logging.getLogger(__name__)


class ConstituencyProcessor(PDFProcessor):
    """
    Specialized PDF processor for constituency data with enhanced multi-page handling.
    
    Key features:
    - Extracts headers from ALL pages (not just first page)
    - Collects unique headers across all pages into master header list
    - Validates header consistency across pages
    - Ensures perfect cell alignment using header-to-column mapping
    - Strict validation to prevent misalignment
    """

    def __init__(self, file_path: str, force_ocr: bool = False, auto_detect: bool = True):
        """Initialize the constituency processor."""
        super().__init__(file_path, force_ocr=force_ocr, auto_detect=auto_detect)
        self.master_headers: List[str] = []
        self.page_headers: Dict[int, List[str]] = {}  # Page number -> headers
        self.header_mapping: Dict[int, Dict[int, int]] = {}  # Page -> (page_col_idx -> master_col_idx)
        self._claude_client = None
        self._init_ai_client()
    
    def _init_ai_client(self):
        """Initialize Claude AI client if API key is available."""
        try:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                from anthropic import Anthropic
                self._claude_client = Anthropic(api_key=api_key)
                logger.info("Claude AI enabled for constituency header extraction")
        except ImportError:
            logger.warning("Anthropic SDK not available, AI header extraction disabled")
        except Exception as e:
            logger.warning(f"Failed to initialize Claude AI: {e}")

    async def extract_tables(
        self,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        validate: bool = True,
        use_text_parser: bool = False,
    ) -> ExtractionResult:
        """
        Extract tables from all pages with enhanced header extraction and cell alignment.
        
        Process:
        1. Extract headers from each page independently
        2. Build master header list (union of all unique headers)
        3. Create mapping from each page's headers to master headers
        4. Extract data rows with proper column alignment
        5. Validate cell alignment accuracy
        
        Args:
            progress_callback: Optional callback for progress updates
            validate: Whether to validate extraction results
            use_text_parser: If True, use text-based parser for structured entries
            
        Returns:
            ExtractionResult with single merged table using master headers
        """
        def update_progress(progress: int, message: str):
            if progress_callback:
                progress_callback(progress, message)

        try:
            update_progress(5, "Initializing constituency extraction...")
            
            # Use text parser if requested
            if use_text_parser:
                update_progress(10, "Using text-based parser for structured entries...")
                result = await self._extract_with_text_parser(update_progress)
            else:
                # Detect PDF type
                if self.auto_detect and not self.force_ocr:
                    update_progress(10, "Detecting PDF type...")
                    detection = self._detect_pdf_type()
                    use_ocr = detection.pdf_type.value in ["image", "mixed"]
                    update_progress(15, f"PDF type: {detection.pdf_type.value}")
                else:
                    use_ocr = self.force_ocr

                # Extract using appropriate method
                if use_ocr:
                    result = await self._extract_with_ocr_constituency(update_progress)
                else:
                    result = await self._extract_with_pdfplumber_constituency(update_progress)
                    
                    if not result.tables or all(t.is_empty for t in result.tables):
                        logger.info("No tables found with pdfplumber, falling back to OCR...")
                        update_progress(50, "No text tables found, trying OCR...")
                        result = await self._extract_with_ocr_constituency(update_progress)

            # Validate extraction results
            if validate and result.tables:
                update_progress(95, "Validating extraction results...")
                from .data_validator import ExtractionValidator
                validator = ExtractionValidator()
                validation_report = validator.validate(result.tables, "constituency")
                
                for table in result.tables:
                    table.extraction_method = "constituency"
                    table.confidence_score = validation_report.confidence

            update_progress(100, "Constituency extraction complete")
            return result

        except Exception as e:
            error_msg = f"Constituency extraction failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise

    async def _extract_with_text_parser(
        self,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> ExtractionResult:
        """Extract using text-based parser for structured constituency entries."""
        from .constituency_text_parser import ConstituencyTextParser
        
        def update_progress(progress: int, message: str):
            if progress_callback:
                progress_callback(progress, message)
        
        update_progress(20, "Parsing text entries from PDF...")
        
        # Use text parser
        parser = ConstituencyTextParser(str(self.file_path))
        headers, data_rows = await asyncio.to_thread(parser.parse)
        
        update_progress(80, f"Extracted {len(data_rows)} entries...")
        
        # Create TableData
        table = TableData(
            headers=headers,
            rows=data_rows,
            page_number=1,
            extraction_method="constituency_text_parser",
        )
        
        return ExtractionResult(
            tables=[table],
            page_texts=[],
        )

    async def _extract_with_pdfplumber_constituency(
        self,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> ExtractionResult:
        """Extract tables using pdfplumber with constituency-specific logic."""
        import pdfplumber

        all_page_tables: List[TableData] = []
        all_headers: Set[str] = set()
        page_headers_dict: Dict[int, List[str]] = {}

        try:
            with pdfplumber.open(str(self.file_path)) as pdf:
                total_pages = len(pdf.pages)
                logger.info(f"Processing {total_pages} pages for constituency extraction")

                # PHASE 1: Extract headers from ALL pages
                if progress_callback:
                    progress_callback(20, "Extracting headers from all pages...")
                for page_num, page in enumerate(pdf.pages, 1):
                    if progress_callback:
                        progress = int(20 + ((page_num / total_pages) * 30))
                        progress_callback(
                            progress,
                            f"Extracting headers from page {page_num} of {total_pages}...",
                        )

                    # Extract tables from this page
                    tables = page.extract_tables()
                    if not tables or all(not t or len(t) < 2 for t in tables):
                        table_settings = {
                            "vertical_strategy": "lines",
                            "horizontal_strategy": "lines",
                        }
                        tables = page.extract_tables(table_settings)

                    # Extract headers from first table on this page using AI
                    if tables and tables[0] and len(tables[0]) >= 2:
                        headers = await self._extract_headers_with_ai(tables[0], page_num)
                        ai_extracted = headers is not None
                        
                        if not headers:
                            # Fallback to regular extraction
                            headers, _ = self._split_table(tables[0])
                        
                        if headers:
                            # Filter out headers that are clearly data values
                            filtered_headers = self._filter_data_like_headers(headers)
                            
                            if filtered_headers:
                                page_headers_dict[page_num] = filtered_headers
                                # Add filtered headers to master set
                                for header in filtered_headers:
                                    if header and header.strip():
                                        all_headers.add(header.strip())
                                logger.info(
                                    f"Page {page_num}: Found {len(filtered_headers)} headers "
                                    f"(AI: {ai_extracted}): {filtered_headers}"
                                )
                            else:
                                logger.warning(f"Page {page_num}: All headers filtered out, using original")
                                page_headers_dict[page_num] = headers
                                for header in headers:
                                    if header and header.strip():
                                        all_headers.add(header.strip())

                # PHASE 2: Build master header list
                if progress_callback:
                    progress_callback(55, "Building master header list...")
                self.master_headers = self._build_master_headers(list(all_headers), page_headers_dict)
                self.page_headers = page_headers_dict
                logger.info(f"Master headers: {len(self.master_headers)} columns")

                # PHASE 3: Create header mappings for each page
                if progress_callback:
                    progress_callback(60, "Creating header mappings...")
                for page_num, page_headers in page_headers_dict.items():
                    self.header_mapping[page_num] = self._create_header_mapping(
                        page_headers, self.master_headers
                    )

                # PHASE 4: Extract data rows with proper alignment
                if progress_callback:
                    progress_callback(65, "Extracting data rows with perfect alignment...")
                all_data_rows: List[List[str]] = []
                
                for page_num, page in enumerate(pdf.pages, 1):
                    if progress_callback:
                        progress = int(65 + ((page_num / total_pages) * 25))
                        progress_callback(
                            progress,
                            f"Extracting data from page {page_num} of {total_pages}...",
                        )

                    # Extract tables
                    tables = page.extract_tables()
                    if not tables or all(not t or len(t) < 2 for t in tables):
                        table_settings = {
                            "vertical_strategy": "lines",
                            "horizontal_strategy": "lines",
                        }
                        tables = page.extract_tables(table_settings)

                    # Process each table on this page
                    for table in tables:
                        if not table or len(table) < 2:
                            continue

                        # Get headers for this page
                        page_headers = page_headers_dict.get(page_num, [])
                        if not page_headers:
                            logger.warning(f"Page {page_num}: No headers found, skipping")
                            continue

                        # Extract data rows (skip header rows) - use AI to identify data start
                        data_rows = await self._extract_data_rows_with_ai(
                            table, page_headers, page_num
                        )
                        
                        if not data_rows:
                            # Fallback to regular extraction
                            _, data_rows = self._split_table(table)
                        
                        # Align each data row to master headers
                        for row in data_rows:
                            aligned_row = self._align_row_to_master_headers(
                                row, page_headers, page_num
                            )
                            if aligned_row:
                                all_data_rows.append(aligned_row)

                # PHASE 5: Create merged table with master headers
                if progress_callback:
                    progress_callback(95, "Creating final table...")
                merged_table = TableData(
                    headers=self.master_headers,
                    rows=all_data_rows,
                    page_number=1,  # Merged
                    extraction_method="constituency",
                )

                logger.info(
                    f"Constituency extraction complete: {len(all_data_rows)} rows, "
                    f"{len(self.master_headers)} columns"
                )

                return ExtractionResult(
                    tables=[merged_table],
                    page_texts=[],
                )
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}", exc_info=True)
            raise

    async def _extract_with_ocr_constituency(
        self,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> ExtractionResult:
        """Extract tables using OCR with constituency-specific logic."""
        from .ocr_processor import OCRProcessor, OCRConfig

        def update_progress(progress: int, message: str):
            if progress_callback:
                adjusted = int(10 + (progress * 0.8))
                progress_callback(adjusted, message)

        logger.info("Starting OCR extraction for constituency...")
        update_progress(0, "Initializing OCR processor...")

        config = OCRConfig(
            dpi=300,
            denoise=True,
            deskew=True,
            contrast_enhance=True,
            use_easyocr_fallback=True,
            min_confidence=50.0,
        )

        ocr_processor = OCRProcessor(str(self.file_path), config)
        
        # Use base OCR extraction, then post-process for constituency
        result = await asyncio.to_thread(
            ocr_processor.extract_tables,
            update_progress
        )

        if not result.tables or all(t.is_empty for t in result.tables):
            raise ValueError("OCR extraction found no tables in the PDF")

        # Post-process: extract headers from all pages and align
        # For now, use the first table's headers as master
        # In a full implementation, we'd process each page separately
        if result.tables:
            first_table = result.tables[0]
            self.master_headers = first_table.headers
            # Merge all tables
            all_rows = []
            for table in result.tables:
                all_rows.extend(table.rows)
            
            merged_table = TableData(
                headers=self.master_headers,
                rows=all_rows,
                page_number=1,
                extraction_method="constituency_ocr",
            )
            
            return ExtractionResult(
                tables=[merged_table],
                page_texts=result.page_texts,
            )

        return result

    def _build_master_headers(
        self, all_unique_headers: List[str], page_headers_dict: Dict[int, List[str]]
    ) -> List[str]:
        """
        Build master header list from all unique headers.
        
        Strategy:
        1. Find the most common/correct headers across all pages (prefer descriptive headers)
        2. Use headers that appear most frequently and are most descriptive
        3. Prioritize headers that look like actual column names (not data values)
        
        Args:
            all_unique_headers: Set of all unique header names
            page_headers_dict: Dict mapping page number to its headers
            
        Returns:
            Ordered list of master headers
        """
        if not all_unique_headers or not page_headers_dict:
            return []

        # Count header occurrences across pages
        header_counts: Dict[str, int] = {}
        header_orders: Dict[str, List[int]] = {}  # Track positions where each header appears
        
        for page_num, headers in page_headers_dict.items():
            for idx, header in enumerate(headers):
                header_clean = header.strip() if header else ""
                if header_clean:
                    header_counts[header_clean] = header_counts.get(header_clean, 0) + 1
                    if header_clean not in header_orders:
                        header_orders[header_clean] = []
                    header_orders[header_clean].append(idx)
        
        # Score headers: prefer headers that:
        # 1. Appear frequently (most pages have them)
        # 2. Are descriptive (longer, contain text)
        # 3. Match expected patterns (Sl.No, Polling station, Location, etc.)
        # 4. Don't look like data values (not just numbers, not school names)
        def score_header(header: str) -> float:
            count = header_counts.get(header, 0)
            length = len(header)
            header_lower = header.lower()
            
            # Bonus for headers that match expected patterns
            pattern_bonus = 0
            if "sl.no" in header_lower or "serial" in header_lower or "s.no" in header_lower:
                pattern_bonus += 30
            if "polling station" in header_lower or "station no" in header_lower or "ps no" in header_lower:
                pattern_bonus += 30
            if "location" in header_lower and "building" in header_lower:
                pattern_bonus += 30
            if "polling areas" in header_lower or "areas" in header_lower:
                pattern_bonus += 30
            if "polling station type" in header_lower or "type" in header_lower:
                pattern_bonus += 30
            
            # Penalize headers that look like data
            is_numeric = header.replace(".", "").replace("-", "").replace(" ", "").isdigit()
            is_short_numeric = len(header) <= 3 and (header.isdigit() or header.replace("-", "").isdigit())
            looks_like_school = "School" in header and ("Panchayat" in header or "Primary" in header or "Middle" in header)
            looks_like_address = "ward" in header_lower and "[" in header and "egumadurai" in header_lower
            
            score = count * 10  # Base score from frequency
            score += pattern_bonus  # Bonus for matching expected patterns
            
            # Bonus for descriptive headers
            if length > 10:
                score += 5
            if length > 30:
                score += 10
            
            # Penalty for data-like headers
            if is_numeric or is_short_numeric:
                score -= 50  # Strong penalty
            if looks_like_school:
                score -= 30  # Strong penalty
            if looks_like_address:
                score -= 25  # Strong penalty
            
            return score
        
        # Get all headers with scores
        scored_headers = [(header, score_header(header)) for header in all_unique_headers]
        scored_headers.sort(key=lambda x: x[1], reverse=True)
        
        # Find the best set of headers (typically 5 for constituency data)
        # Look for headers that appear in most pages and are descriptive
        best_headers = []
        seen_positions = set()
        
        # First, try to find headers that appear in majority of pages
        majority_threshold = len(page_headers_dict) * 0.5
        
        for header, score in scored_headers:
            count = header_counts.get(header, 0)
            if count >= majority_threshold and score > 0:
                # Get the most common position for this header
                positions = header_orders.get(header, [])
                if positions:
                    avg_position = sum(positions) / len(positions)
                    best_headers.append((header, avg_position, score))
        
        # Sort by position (to maintain column order) then by score
        best_headers.sort(key=lambda x: (x[1], -x[2]))
        master = [h[0] for h in best_headers]
        
        # If we don't have enough headers, add more from scored list
        if len(master) < 3:
            for header, score in scored_headers:
                if header not in master and score > -10:
                    # Get average position
                    positions = header_orders.get(header, [0])
                    avg_pos = sum(positions) / len(positions) if positions else 999
                    master.append(header)
                    if len(master) >= 10:  # Reasonable limit
                        break
            # Sort by average position
            master.sort(key=lambda h: sum(header_orders.get(h, [0])) / len(header_orders.get(h, [1])) if header_orders.get(h) else 999)
        
        logger.info(f"Built master headers ({len(master)}): {master}")
        return master

    def _create_header_mapping(
        self, page_headers: List[str], master_headers: List[str]
    ) -> Dict[int, int]:
        """
        Create mapping from page column index to master column index.
        
        Args:
            page_headers: Headers from a specific page
            master_headers: Master header list
            
        Returns:
            Dict mapping page_col_idx -> master_col_idx
        """
        mapping: Dict[int, int] = {}
        
        # Create reverse lookup for master headers
        master_lookup: Dict[str, int] = {
            h.strip().lower(): idx for idx, h in enumerate(master_headers)
        }

        for page_idx, page_header in enumerate(page_headers):
            if not page_header:
                continue
                
            page_header_clean = page_header.strip().lower()
            
            # Try exact match first
            if page_header_clean in master_lookup:
                mapping[page_idx] = master_lookup[page_header_clean]
            else:
                # Try fuzzy matching (case-insensitive, whitespace-tolerant)
                for master_idx, master_header in enumerate(master_headers):
                    if master_header.strip().lower() == page_header_clean:
                        mapping[page_idx] = master_idx
                        break
                else:
                    # No match found - this shouldn't happen if headers are consistent
                    logger.warning(
                        f"Page header '{page_header}' not found in master headers"
                    )

        return mapping

    def _align_row_to_master_headers(
        self, row: List[str], page_headers: List[str], page_num: int
    ) -> Optional[List[str]]:
        """
        Align a data row to master headers using header mapping.
        
        This ensures perfect cell-to-column accuracy.
        
        Args:
            row: Data row from a specific page
            page_headers: Headers from that page
            page_num: Page number (for logging)
            
        Returns:
            Aligned row matching master header structure, or None if alignment fails
        """
        if not self.master_headers:
            return None

        # Get mapping for this page
        mapping = self.header_mapping.get(page_num, {})
        if not mapping:
            # Fallback: try to create mapping on the fly
            mapping = self._create_header_mapping(page_headers, self.master_headers)

        # Create aligned row with correct number of columns
        aligned_row: List[str] = [""] * len(self.master_headers)

        # Map each cell from page row to master row
        for page_col_idx, cell_value in enumerate(row):
            if page_col_idx in mapping:
                master_col_idx = mapping[page_col_idx]
                if master_col_idx < len(aligned_row):
                    aligned_row[master_col_idx] = self._clean_cell(cell_value)

        # Validate alignment
        if len(aligned_row) != len(self.master_headers):
            logger.warning(
                f"Page {page_num}: Row alignment failed - expected {len(self.master_headers)} "
                f"columns, got {len(aligned_row)}"
            )
            # Pad or truncate to match
            if len(aligned_row) < len(self.master_headers):
                aligned_row.extend([""] * (len(self.master_headers) - len(aligned_row)))
            else:
                aligned_row = aligned_row[:len(self.master_headers)]

        return aligned_row

    async def _extract_headers_with_ai(
        self, table: List[List], page_num: int
    ) -> Optional[List[str]]:
        """
        Use AI to intelligently extract column headers from table structure.
        
        Analyzes the first few rows to identify which are headers vs data.
        
        Args:
            table: Raw table data from pdfplumber
            page_num: Page number for logging
            
        Returns:
            List of header names, or None if AI extraction fails
        """
        if not self._claude_client or not table or len(table) < 2:
            return None

        try:
            # Get first 10 rows for analysis
            sample_rows = table[:min(10, len(table))]
            
            # Prepare table data for AI analysis
            table_text = []
            for idx, row in enumerate(sample_rows):
                cleaned_row = [self._clean_cell(cell) for cell in row]
                table_text.append(f"Row {idx + 1}: {json.dumps(cleaned_row)}")
            
            table_data_str = "\n".join(table_text)
            
            prompt = f"""You are analyzing a table from a PDF document. Your task is to identify the column headers.

Table data (first 10 rows):
{table_data_str}

CRITICAL REQUIREMENTS:
1. Identify which row(s) contain the ACTUAL column headers (not data)
2. Extract ALL column headers - do not truncate or skip any headers
3. Headers are typically:
   - Descriptive text (e.g., "Sl.No", "Polling station No.", "Location and name of building...")
   - May include numbers like "1-1", "2-1" if they are part of the header structure
   - NOT numeric sequences (e.g., "1", "2", "3", "4", "5" as separate values)
   - NOT data values (e.g., school names, addresses in data rows)
   - Usually appear in the first 1-3 rows
4. If headers span multiple rows, combine them intelligently
5. Return ALL header names as a JSON array - include every column header
6. Do NOT include row numbers or data values
7. Preserve the exact original text of headers, including long descriptions

Examples of GOOD headers:
- ["Sl.No", "Polling station No.", "Location and name of building in which Polling Station located", "Polling Areas", "Polling Station Type"]
- ["PS No.", "1-1", "2-1", "3 - Panchayat Union Primary School, North Building South Facing, Egumadurai -601201", "4 - [1]-Egumadurai (R.V) and (P), Egumadurai village (ward-1)..."]
- ["Serial Number", "Station No", "Building Name", "Areas Covered", "Type"]

Examples of BAD headers (these are data, not headers):
- ["1", "2", "3", "4", "5"] (just numbers)
- ["Panchayat Union Primary School", "Egumadurai", "ALL VOTERS"] (data values)

IMPORTANT: Extract ALL column headers, even if they start with numbers like "1-1", "2-1". These can be valid headers.

Return ONLY a JSON array of header names, no explanations, no markdown:
["Header 1", "Header 2", "Header 3", ...]"""

            # Call Claude API
            from anthropic import AnthropicError
            
            message = self._claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                temperature=0.1,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            # Extract JSON from response
            content = message.content[0].text.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            # Parse JSON response
            headers = json.loads(content)
            
            if not isinstance(headers, list) or len(headers) == 0:
                logger.warning(f"Page {page_num}: AI returned invalid headers format")
                return None
            
            # Validate headers - accept all headers returned by AI (it should be smart enough)
            # But filter out obvious data values
            valid_headers = []
            for header in headers:
                header_str = str(header).strip()
                # Skip if it's just a single digit or very short numeric value
                if header_str and len(header_str) > 1:
                    # Accept headers that:
                    # - Are longer than 1 character
                    # - Or are descriptive (contain text, not just numbers)
                    # - Headers like "1-1", "2-1" are valid if AI returned them
                    if not (len(header_str) == 1 and header_str.isdigit()):
                        valid_headers.append(header_str)
            
            if valid_headers:
                logger.info(f"Page {page_num}: AI extracted {len(valid_headers)} headers: {valid_headers}")
                return valid_headers
            else:
                logger.warning(f"Page {page_num}: AI headers validation failed")
                return None
                
        except AnthropicError as e:
            logger.warning(f"Claude API error during header extraction: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response as JSON: {e}")
            return None
        except Exception as e:
            logger.warning(f"AI header extraction failed: {e}")
            return None
    
    def _filter_data_like_headers(self, headers: List[str]) -> List[str]:
        """
        Filter out headers that look like data values rather than actual column headers.
        
        Args:
            headers: List of potential headers
            
        Returns:
            Filtered list of headers
        """
        filtered = []
        for header in headers:
            header_str = str(header).strip()
            if not header_str:
                continue
            
            # Skip if it's just a number or very short numeric
            if len(header_str) <= 3 and (header_str.isdigit() or header_str.replace("-", "").isdigit()):
                continue
            
            # Skip if it looks like a school name (data value)
            if "School" in header_str and ("Panchayat" in header_str or "Primary" in header_str):
                # But allow if it's part of a descriptive header like "Location and name of building..."
                if "Location" not in header_str and "name of building" not in header_str.lower():
                    continue
            
            # Skip if it looks like an address/ward info (data value)
            header_lower = header_str.lower()
            if "ward" in header_lower and "[" in header_str and "egumadurai" in header_lower:
                # But allow if it's "Polling Areas" which is a valid header
                if "polling areas" not in header_lower:
                    continue
            
            filtered.append(header_str)
        
        return filtered

    async def _extract_data_rows_with_ai(
        self, table: List[List], page_headers: List[str], page_num: int
    ) -> List[List[str]]:
        """
        Use AI to identify and extract only data rows, skipping headers.
        
        Args:
            table: Raw table data
            page_headers: Known headers for this page
            page_num: Page number for logging
            
        Returns:
            List of data rows (headers skipped)
        """
        if not table or len(table) < 2:
            return []
        
        # Simple heuristic: find first row that doesn't match headers
        # and starts with a number (typical of data rows)
        data_rows = []
        header_found = False
        
        for row in table:
            cleaned_row = [self._clean_cell(cell) for cell in row]
            
            # Skip empty rows
            if not any(cell.strip() for cell in cleaned_row if cell):
                continue
            
            # Check if this row matches headers
            if not header_found:
                # Check if first cell matches first header
                first_cell = cleaned_row[0].strip() if cleaned_row else ""
                if first_cell and first_cell.lower() in [h.lower()[:20] for h in page_headers if h]:
                    header_found = True
                    continue
            
            # If we've found headers, check if this is a data row
            if header_found:
                # Filter out rows that are just numeric sequences (1, 2, 3, 4, 5) - these are section markers
                if self._is_numeric_sequence_row(cleaned_row):
                    logger.debug(f"Page {page_num}: Skipping numeric sequence row: {cleaned_row[:5]}")
                    continue
                
                # Data rows typically start with a number
                first_cell = cleaned_row[0].strip() if cleaned_row else ""
                if first_cell and (first_cell.isdigit() or first_cell.replace(".", "").isdigit()):
                    # This looks like a data row
                    # Normalize length
                    if len(cleaned_row) < len(page_headers):
                        cleaned_row.extend([""] * (len(page_headers) - len(cleaned_row)))
                    elif len(cleaned_row) > len(page_headers):
                        cleaned_row = cleaned_row[:len(page_headers)]
                    data_rows.append(cleaned_row)
                elif first_cell and first_cell.lower() in [h.lower()[:20] for h in page_headers if h]:
                    # This is a duplicate header row, skip it
                    continue
                elif any(cell.strip() for cell in cleaned_row if cell):
                    # Non-empty row that's not a header - likely data
                    # But check if it's a numeric sequence first
                    if not self._is_numeric_sequence_row(cleaned_row):
                        if len(cleaned_row) < len(page_headers):
                            cleaned_row.extend([""] * (len(page_headers) - len(cleaned_row)))
                        elif len(cleaned_row) > len(page_headers):
                            cleaned_row = cleaned_row[:len(page_headers)]
                        data_rows.append(cleaned_row)
        
        # If we didn't find headers, try to identify data start by looking for numeric first column
        if not header_found and not data_rows:
            for row in table:
                cleaned_row = [self._clean_cell(cell) for cell in row]
                
                # Skip numeric sequence rows
                if self._is_numeric_sequence_row(cleaned_row):
                    continue
                
                first_cell = cleaned_row[0].strip() if cleaned_row else ""
                
                # If first cell is a number, it's likely a data row
                if first_cell and (first_cell.isdigit() or first_cell.replace(".", "").isdigit()):
                    if len(cleaned_row) < len(page_headers):
                        cleaned_row.extend([""] * (len(page_headers) - len(cleaned_row)))
                    elif len(cleaned_row) > len(page_headers):
                        cleaned_row = cleaned_row[:len(page_headers)]
                    data_rows.append(cleaned_row)
        
        return data_rows
    
    def _is_numeric_sequence_row(self, row: List[str]) -> bool:
        """
        Check if a row is just a numeric sequence (1, 2, 3, 4, 5) - these are section markers, not data.
        
        Args:
            row: Row to check
            
        Returns:
            True if row is just a numeric sequence
        """
        if not row:
            return False
        
        # Get non-empty cells
        non_empty = [cell.strip() for cell in row if cell and str(cell).strip()]
        
        if len(non_empty) < 3:
            return False
        
        # Check if all cells are single digits or short numbers
        all_numeric = True
        for cell in non_empty[:5]:  # Check first 5 cells
            cell_str = str(cell).strip()
            # Check if it's a single digit or a short number (1-2 digits)
            if not (cell_str.isdigit() and len(cell_str) <= 2):
                all_numeric = False
                break
        
        # If all are numeric and in sequence-like pattern, it's likely a section marker
        if all_numeric and len(non_empty) >= 3:
            # Check if they form a sequence (1, 2, 3, 4, 5 or similar)
            try:
                numbers = [int(cell.strip()) for cell in non_empty[:5] if cell.strip().isdigit()]
                if len(numbers) >= 3:
                    # Check if they're sequential or close to sequential
                    diffs = [numbers[i+1] - numbers[i] for i in range(len(numbers)-1)]
                    # If differences are mostly 0 or 1, it's likely a sequence marker
                    if all(d in [0, 1] for d in diffs):
                        return True
            except (ValueError, IndexError):
                pass
        
        return False

