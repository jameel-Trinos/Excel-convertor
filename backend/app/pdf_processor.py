"""PDF table extraction with automatic text/image detection and Azure DI support."""

import asyncio
import hashlib
import logging
import os
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from .models import ExtractionResult, TableData
from .pdf_detector import PDFType, PDFTypeDetector, PDFDetectionResult
from .data_validator import ExtractionValidator, ValidationReport

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Raised when extraction fails."""

    pass


class PDFProcessor:
    """
    PDF table extraction processor with automatic text/image detection.

    Supports two extraction paths:
    1. Text-based PDFs: Uses pdfplumber for efficient extraction
    2. Image-based PDFs: Uses OCR (pytesseract + pdf2image) for scanned documents

    The processor automatically detects the PDF type and selects the appropriate
    extraction method. For mixed PDFs, it uses a hybrid approach.
    """

    def __init__(self, file_path: str, force_ocr: bool = False, auto_detect: bool = True):
        """
        Initialize the PDF processor.

        Args:
            file_path: Path to the PDF file to process
            force_ocr: Force OCR extraction even for text-based PDFs
            auto_detect: Automatically detect PDF type (default True)
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        self.force_ocr = force_ocr
        self.auto_detect = auto_detect
        self._detection_result: Optional[PDFDetectionResult] = None
        self._validation_report: Optional[ValidationReport] = None

    @property
    def pdf_type(self) -> PDFType:
        """Get the detected PDF type."""
        if self._detection_result is None:
            self._detect_pdf_type()
        return self._detection_result.pdf_type

    @property
    def detection_confidence(self) -> float:
        """Get the detection confidence score."""
        if self._detection_result is None:
            self._detect_pdf_type()
        return self._detection_result.confidence

    @property
    def validation_report(self) -> Optional[ValidationReport]:
        """Get the validation report from the last extraction."""
        return self._validation_report

    def _detect_pdf_type(self) -> PDFDetectionResult:
        """Detect if PDF is text-based or image-based."""
        detector = PDFTypeDetector()
        self._detection_result = detector.detect(str(self.file_path))
        logger.info(
            f"PDF type detected: {self._detection_result.pdf_type.value} "
            f"(confidence: {self._detection_result.confidence:.2f})"
        )
        return self._detection_result

    def get_detection_info(self) -> dict:
        """Get detailed detection information."""
        if self._detection_result is None:
            self._detect_pdf_type()
        return self._detection_result.to_dict()

    async def extract_tables(
        self,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        validate: bool = True,
    ) -> ExtractionResult:
        """
        Extract tables from all pages and merge into a single table.

        Automatically detects PDF type and uses appropriate extraction method:
        - Text-based PDFs: pdfplumber
        - Image-based PDFs: OCR (pytesseract)

        Args:
            progress_callback: Optional callback for progress updates (progress%, message)
            validate: Whether to validate extraction results (default True)

        Returns:
            ExtractionResult containing a single merged table

        Raises:
            ExtractionError: If extraction fails
        """
        def update_progress(progress: int, message: str):
            if progress_callback:
                progress_callback(progress, message)

        try:
            # Detect PDF type if auto-detection is enabled
            if self.auto_detect and not self.force_ocr:
                update_progress(5, "Detecting PDF type...")
                detection = self._detect_pdf_type()
                use_ocr = detection.pdf_type in [PDFType.IMAGE, PDFType.MIXED]
                update_progress(10, f"PDF type: {detection.pdf_type.value}")
            else:
                use_ocr = self.force_ocr

            # Route to appropriate extraction method
            if use_ocr:
                # Use Azure Document Intelligence for image/scanned PDFs
                result = await self._extract_with_ocr(update_progress)
                extraction_method = "azure_di"
            else:
                # Use pdfplumber for text-based PDFs
                update_progress(10, "Extracting tables from PDF...")
                tables = await asyncio.to_thread(self._extract_with_pdfplumber, update_progress)

                if not tables or all(t.is_empty for t in tables):
                    # Fallback to Azure DI
                    logger.info("No tables found with pdfplumber, falling back to Azure DI...")
                    update_progress(50, "Trying Azure DI fallback...")
                    result = await self._extract_with_ocr(update_progress)
                    extraction_method = "azure_di_fallback"
                else:
                    # Merge all tables into a single table
                    update_progress(80, "Merging tables from all pages...")
                    merged_table = self._merge_tables(tables)

                    # Extract page texts for AC number extraction
                    page_texts = await asyncio.to_thread(self._extract_page_texts)

                    result = ExtractionResult(
                        tables=[merged_table],
                        page_texts=page_texts,
                    )
                    extraction_method = "pdfplumber"

            # Validate extraction results
            if validate and result.tables:
                update_progress(95, "Validating extraction results...")
                validator = ExtractionValidator()
                self._validation_report = validator.validate(result.tables, extraction_method)

                # Add extraction metadata to tables
                for table in result.tables:
                    table.extraction_method = extraction_method
                    table.confidence_score = self._validation_report.confidence

                # Log validation summary
                logger.info(
                    f"Extraction validation: passed={self._validation_report.passed}, "
                    f"confidence={self._validation_report.confidence:.2f}"
                )

            update_progress(100, "Extraction complete")
            return result

        except ExtractionError:
            raise
        except Exception as e:
            error_msg = f"Extraction failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ExtractionError(error_msg)

    async def _extract_with_ocr(
        self,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> ExtractionResult:
        """
        Extract tables using Azure Document Intelligence (pdf_table_extractor).

        Uses the existing pdf_table_extractor.py functions:
        - get_client() to create the Azure DI client
        - analyze_pdf() to send the PDF to Azure DI
        - tables_to_rows() to convert Azure DI tables to header/data rows

        Args:
            progress_callback: Progress callback function

        Returns:
            ExtractionResult from Azure DI extraction
        """
        from .pdf_table_extractor import get_client, analyze_pdf, tables_to_rows

        def update_progress(progress: int, message: str):
            if progress_callback:
                adjusted = int(10 + (progress * 0.8))
                progress_callback(adjusted, message)

        logger.info("Starting Azure Document Intelligence extraction...")
        update_progress(5, "Sending PDF to Azure Document Intelligence...")

        client = get_client()
        result = await asyncio.to_thread(analyze_pdf, client, str(self.file_path))

        page_count = len(result.pages) if result.pages else 0
        table_count = len(result.tables) if result.tables else 0
        logger.info(f"Azure DI: {page_count} pages, {table_count} tables found")
        update_progress(60, f"Analyzed {page_count} pages, found {table_count} tables")

        if table_count == 0:
            raise ExtractionError("Azure DI found no tables in the PDF")

        # Convert Azure DI tables to header rows + data rows
        update_progress(70, "Processing extracted tables...")
        header_rows, data_rows = tables_to_rows(result)

        if not header_rows:
            raise ExtractionError("Azure DI could not extract headers from the PDF")

        # Build headers from header_rows (use last row as most specific)
        headers = header_rows[-1] if header_rows else []

        # Normalize data row lengths to match headers
        for i, row in enumerate(data_rows):
            if len(row) < len(headers):
                data_rows[i] = row + [""] * (len(headers) - len(row))
            elif len(row) > len(headers):
                data_rows[i] = row[:len(headers)]

        table_data = TableData(
            headers=headers,
            rows=data_rows,
            page_number=1,
            extraction_method="azure_di",
            confidence_score=0.90,
            header_rows=header_rows,
        )

        # Extract page texts from Azure DI result
        update_progress(85, "Extracting page texts...")
        page_texts = []
        if result.pages:
            for page in result.pages:
                page_text_parts = []
                if hasattr(page, "words") and page.words:
                    for word in page.words:
                        page_text_parts.append(word.content)
                page_texts.append(" ".join(page_text_parts) if page_text_parts else "")

        update_progress(95, "Azure DI extraction complete")
        logger.info(f"Azure DI: {len(headers)} headers, {len(data_rows)} data rows")

        return ExtractionResult(
            tables=[table_data],
            page_texts=page_texts,
        )

    def _extract_with_pdfplumber(
        self,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> List[TableData]:
        """
        Extract tables using pdfplumber from all pages.

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            List of TableData objects, one per page
        """
        import pdfplumber

        all_tables: List[TableData] = []
        first_page_headers = None  # Headers extracted from first page only

        with pdfplumber.open(str(self.file_path)) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"PDF has {total_pages} pages")

            for page_num, page in enumerate(pdf.pages, 1):
                if progress_callback:
                    progress = int(10 + ((page_num / total_pages) * 70))
                    progress_callback(
                        progress,
                        f"Extracting tables from page {page_num} of {total_pages}...",
                    )

                # Try multiple extraction strategies
                tables = None
                
                # Strategy 1: lines_strict (best for tables with clear borders)
                table_settings = {
                    "vertical_strategy": "lines_strict",
                    "horizontal_strategy": "lines_strict",
                    "intersection_tolerance": 3,
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                }
                tables = page.extract_tables(table_settings)

                # Strategy 2: lines (more lenient)
                if not tables or all(not t or len(t) < 2 for t in tables):
                    table_settings = {
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "intersection_tolerance": 5,
                        "snap_tolerance": 5,
                        "join_tolerance": 5,
                    }
                    tables = page.extract_tables(table_settings)

                # Strategy 3: default extraction
                if not tables or all(not t or len(t) < 2 for t in tables):
                    tables = page.extract_tables()

                # Process each table found on this page
                for table_idx, table in enumerate(tables):
                    if not table or len(table) < 2:
                        continue

                    # FIRST PAGE: Extract headers and data rows
                    if page_num == 1:
                        # Try AI-powered header extraction first
                        headers, data_rows = self._split_table_with_ai(page, table)
                        if not headers:
                            # Fallback to regular extraction
                            headers, data_rows = self._split_table(table)
                        
                        if headers:
                            first_page_headers = headers  # Store headers from first page
                            logger.info(f"Page 1: Extracted headers: {len(headers)} columns")
                        
                        if first_page_headers and data_rows:
                            table_data = TableData(
                                headers=first_page_headers,
                                rows=data_rows,
                                page_number=page_num,
                            )
                            all_tables.append(table_data)
                            logger.info(
                                f"Page {page_num}: Extracted {len(data_rows)} rows, {len(first_page_headers)} columns"
                            )
                    else:
                        # SUBSEQUENT PAGES: Only extract data rows (skip headers)
                        # Use headers from first page
                        if first_page_headers is None:
                            logger.warning(f"Page {page_num}: No headers from first page, skipping")
                            continue
                        
                        # Extract only data rows, skipping header rows
                        data_rows = self._extract_data_rows_only(table, first_page_headers)
                        
                        if data_rows:
                            table_data = TableData(
                                headers=first_page_headers,
                                rows=data_rows,
                                page_number=page_num,
                            )
                            all_tables.append(table_data)
                            logger.info(
                                f"Page {page_num}: Extracted {len(data_rows)} data rows (headers skipped)"
                            )

        logger.info(f"Extracted {len(all_tables)} tables from {total_pages} pages")
        return all_tables

    def _is_column_number_row(self, row: List[str]) -> bool:
        """
        Check if a row is a column number indicator row (e.g., 1, 2, 3, 4, 5).

        These rows appear at the top of PDF pages as column number markers
        and should be skipped during extraction.

        Args:
            row: Cleaned row data

        Returns:
            True if this is a column number row
        """
        if not row:
            return False

        # Get non-empty cells
        non_empty = [cell.strip() for cell in row if cell and cell.strip()]

        if len(non_empty) < 3:
            return False

        # Check if cells are sequential small integers starting from 1
        # Pattern: 1, 2, 3, 4, 5 or similar
        try:
            numbers = []
            for cell in non_empty:
                # Try to parse as integer
                num = int(cell)
                numbers.append(num)

            # Check if they form a sequential pattern starting from 1 or 2
            if len(numbers) >= 3:
                # Check if it's a sequence like 1,2,3,4,5 or 2,3,4,5
                is_sequential = all(
                    numbers[i] == numbers[i-1] + 1
                    for i in range(1, len(numbers))
                )
                # Must start with a small number (1-5) and be sequential
                if is_sequential and numbers[0] <= 5 and numbers[-1] <= 20:
                    logger.debug(f"Detected column number row: {non_empty[:5]}")
                    return True
        except (ValueError, TypeError):
            pass

        return False

    def _extract_data_rows_only(
        self,
        table: List[List],
        expected_headers: List[str]
    ) -> List[List[str]]:
        """
        Extract only data rows from a table, skipping header rows.

        This is used for subsequent pages where headers have already been
        extracted from the first page. It identifies and skips header rows
        that appear on each page.

        Args:
            table: Raw table data from pdfplumber
            expected_headers: Headers from first page (used for row normalization)

        Returns:
            List of data rows (headers skipped)
        """
        if not table or len(table) < 2:
            return []

        data_rows = []

        for row in table:
            cleaned_row = [self._clean_cell(cell) for cell in row]

            # Skip completely empty rows
            if not any(cell.strip() for cell in cleaned_row if cell):
                continue

            # Skip column number indicator rows (e.g., 1, 2, 3, 4, 5)
            if self._is_column_number_row(cleaned_row):
                continue

            # Check if this looks like a header row
            # First check: if first cell is numeric, it's likely a data row
            first_cell = cleaned_row[0].strip() if cleaned_row and cleaned_row[0] else ""
            if first_cell and first_cell.isdigit():
                # This is likely a data row - normalize and add it
                if len(cleaned_row) < len(expected_headers):
                    cleaned_row.extend([""] * (len(expected_headers) - len(cleaned_row)))
                elif len(cleaned_row) > len(expected_headers):
                    cleaned_row = cleaned_row[:len(expected_headers)]
                data_rows.append(cleaned_row)
                continue
            
            # Check for header keywords in the row
            row_text = " ".join(cleaned_row).upper()
            header_keywords = [
                "PARTY ABBREVIATION",
                "NO. OF VALID VOTES",
                "NO OF VALID VOTES",
                "VALID VOTES",
                "POLLING STATION",
                "SL. NO",
                "SL.NO",
                "SERIAL NUMBER",
                "S.NO"
            ]
            
            if any(keyword in row_text for keyword in header_keywords):
                logger.debug(f"Skipping header row: {cleaned_row[:3]}")
                continue
            
            # Check if row has mostly text (not numbers) - typical of headers
            non_empty = [cell for cell in cleaned_row if cell.strip()]
            if non_empty:
                numeric_count = sum(1 for cell in non_empty if self._is_numeric_string(cell))
                text_count = len(non_empty) - numeric_count
                
                # If mostly text (at least 70% text), it's likely a header row
                if len(non_empty) > 0 and text_count / len(non_empty) >= 0.7:
                    logger.debug(f"Skipping text-heavy row (likely header): {cleaned_row[:3]}")
                    continue
            
            # Check if this row matches expected headers (similarity check)
            if expected_headers and len(cleaned_row) >= len(expected_headers):
                row_values = [str(cell).strip().lower() for cell in cleaned_row[:len(expected_headers)]]
                header_values = [str(h).strip().lower() for h in expected_headers]
                
                # Count matches
                matches = sum(1 for r, h in zip(row_values, header_values) if r and h and r == h)
                
                # If more than 40% of cells match headers, it's likely a header row
                if matches > len(expected_headers) * 0.4:
                    logger.debug(f"Skipping row matching headers: {cleaned_row[:3]}")
                    continue
            
            # This is a data row - normalize length to match expected headers
            if len(cleaned_row) < len(expected_headers):
                cleaned_row.extend([""] * (len(expected_headers) - len(cleaned_row)))
            elif len(cleaned_row) > len(expected_headers):
                cleaned_row = cleaned_row[:len(expected_headers)]
            
            data_rows.append(cleaned_row)
        
        return data_rows

    def _split_table(self, table: List[List]) -> tuple[List[str], List[List[str]]]:
        """
        Split table into headers and data rows.
        
        Handles multi-row headers where:
        - Candidate names are in one row
        - Party abbreviations are in another row below
        - Need to combine them into proper column names

        Args:
            table: Raw table data from pdfplumber

        Returns:
            Tuple of (headers, data_rows)
        """
        if not table or len(table) < 2:
            return [], []

        # Header keywords that indicate a header row (expanded for different PDF structures)
        HEADER_KEYWORDS = [
            "sl.", "sl ", "s.l.", "s.l ", "serial", "no.", "number", "s.no", "s.no.",
            "polling", "station", "location", "building", "booth",
            "area", "areas", "type", "voter", "voters", "elector", "electors",
            "candidate", "party", "abbreviation", "abbr", "name",
            "valid", "votes", "total", "rejected", "tendered", "cast",
            "nota", "dmk", "aiadmk", "bjp", "congress", "independent", "ind",
            "assembly", "constituency", "ac", "ac no", "ac no."
        ]
        
        # Detect header rows (typically 1-3 rows at the top)
        header_rows = []
        data_start_idx = 0
        
        # Check first few rows to identify headers
        max_header_rows = 5
        for idx in range(min(max_header_rows, len(table))):
            row = table[idx]
            cleaned_row = [self._clean_cell(cell) for cell in row]
            non_empty = [cell for cell in cleaned_row if cell.strip()]
            
            if not non_empty:
                continue

            # Skip column number indicator rows (e.g., 1, 2, 3, 4, 5)
            if self._is_column_number_row(cleaned_row):
                data_start_idx = idx + 1
                continue

            # Check if first cell is numeric - if so, it's definitely a data row
            first_cell = cleaned_row[0].strip() if cleaned_row and cleaned_row[0] else ""
            if first_cell and self._is_numeric_string(first_cell):
                # First cell is numeric, this is a data row, not a header
                break
            
            # Check for header keywords in the row
            row_text = " ".join(str(cell).lower() for cell in cleaned_row if cell).lower()
            has_header_keywords = any(keyword in row_text for keyword in HEADER_KEYWORDS)
            
            # Count numeric vs text cells
            numeric_count = sum(1 for cell in non_empty if self._is_numeric_string(cell))
            text_count = len(non_empty) - numeric_count
            text_ratio = text_count / len(non_empty) if non_empty else 0
            
            # Row is a header if:
            # 1. It has header keywords, OR
            # 2. It has high text ratio (80%+) AND no numeric values in first column, OR
            # 3. First row with high text ratio (70%+), OR
            # 4. Row has mostly text and matches common header patterns (colored headers often have this)
            is_header = False
            if has_header_keywords:
                is_header = True
            elif text_ratio >= 0.8 and numeric_count == 0:
                # Very high text ratio with no numbers - likely header (common for colored headers)
                is_header = True
            elif idx == 0 and text_ratio >= 0.7:
                # First row with high text ratio - likely header
                is_header = True
            elif idx < 3 and text_ratio >= 0.75 and len(non_empty) >= 3:
                # Early rows with high text ratio and multiple columns - likely headers
                # This catches colored headers that may not have obvious keywords
                is_header = True
            
            if is_header:
                header_rows.append(cleaned_row)
                data_start_idx = idx + 1
            else:
                # Found first data row
                break
        
        # If no header rows detected, use first row as headers (fallback)
        if not header_rows:
            header_rows = [[self._clean_cell(cell) for cell in table[0]]]
            data_start_idx = 1
        
        # Combine multi-row headers intelligently
        headers = self._combine_header_rows(header_rows)
        
        # Log detected headers for debugging
        logger.info(f"Detected {len(header_rows)} header row(s), data starts at row {data_start_idx + 1}")
        logger.debug(f"Headers: {headers[:5]}...")  # Log first 5 headers
        
        # Extract data rows
        data_rows = []
        for row in table[data_start_idx:]:
            cleaned_row = [self._clean_cell(cell) for cell in row]
            # Skip completely empty rows
            if any(cell.strip() for cell in cleaned_row if cell):
                # Skip column number indicator rows (e.g., 1, 2, 3, 4, 5)
                if self._is_column_number_row(cleaned_row):
                    continue
                # Skip duplicate header rows (headers that appear again mid-table)
                if self._is_duplicate_header(cleaned_row, header_rows):
                    continue
                # Normalize row length to match headers PERFECTLY
                if len(cleaned_row) < len(headers):
                    cleaned_row.extend([""] * (len(headers) - len(cleaned_row)))
                elif len(cleaned_row) > len(headers):
                    cleaned_row = cleaned_row[:len(headers)]
                data_rows.append(cleaned_row)

        # Validate and fix header-to-data alignment
        sample_data = table[data_start_idx:data_start_idx+5] if len(table) > data_start_idx else []
        headers, data_rows = self._ensure_perfect_alignment(headers, data_rows, sample_data)

        logger.info(f"Extracted {len(data_rows)} data rows with {len(headers)} columns (aligned perfectly)")
        return headers, data_rows
    
    def _split_table_with_ai(self, page, table: List[List]) -> tuple[List[str], List[List[str]]]:
        """
        Split table into headers and data rows using AI-powered extraction.
        
        Args:
            page: pdfplumber page object (for text extraction)
            table: Raw table data from pdfplumber
            
        Returns:
            Tuple of (headers, data_rows)
        """
        if not table or len(table) < 2:
            return [], []
        
        # Check if Claude AI is available
        try:
            from .claude_processor import ClaudeProcessor
            
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                logger.info("ANTHROPIC_API_KEY not set, using regular header extraction")
                return self._split_table(table)
            
            # Initialize Claude processor
            claude = ClaudeProcessor(api_key=api_key)
            
            if not claude.enabled:
                logger.info("Claude AI not enabled, using regular header extraction")
                return self._split_table(table)
            
            # Extract page text for context
            page_text = page.extract_text() or ""
            
            # Use AI to extract headers
            headers, data_start_idx, confidence = claude.extract_headers_with_ai(page_text, table)
            
            if headers and confidence > 0.5:
                logger.info(f"AI extracted headers with confidence {confidence:.2f}")
                
                # Extract data rows starting from data_start_idx
                data_rows = []
                for row in table[data_start_idx:]:
                    cleaned_row = [self._clean_cell(cell) for cell in row]
                    # Skip completely empty rows
                    if any(cell.strip() for cell in cleaned_row if cell):
                        # Skip column number indicator rows (e.g., 1, 2, 3, 4, 5)
                        if self._is_column_number_row(cleaned_row):
                            continue
                        # Skip duplicate header rows
                        if self._is_duplicate_header(cleaned_row, [headers]):
                            continue
                        # Normalize row length to match headers PERFECTLY
                        if len(cleaned_row) < len(headers):
                            cleaned_row.extend([""] * (len(headers) - len(cleaned_row)))
                        elif len(cleaned_row) > len(headers):
                            cleaned_row = cleaned_row[:len(headers)]
                        data_rows.append(cleaned_row)
                
                # Validate and fix header-to-data alignment
                headers, data_rows = self._ensure_perfect_alignment(headers, data_rows, table[data_start_idx:data_start_idx+5] if len(table) > data_start_idx else [])
                
                logger.info(f"AI extraction: {len(headers)} headers, {len(data_rows)} data rows (aligned perfectly)")
                return headers, data_rows
            else:
                logger.warning(f"AI header extraction low confidence ({confidence:.2f}), falling back to regular extraction")
                return self._split_table(table)
                
        except Exception as e:
            logger.warning(f"AI header extraction failed: {e}, falling back to regular extraction")
            return self._split_table(table)
    
    def _combine_header_rows(self, header_rows: List[List[str]]) -> List[str]:
        """
        Combine multiple header rows into single column names.
        
        For election PDFs:
        - Row 1 might have: "SL. NO.", "Polling Station No.", "No. of valid votes cast in favour of" (spanning multiple cols)
        - Row 2 might have: candidate names
        - Row 3 might have: "PARTY ABBREVIATION", party names
        
        Strategy:
        - Use the most specific row (usually the last one with actual names)
        - Combine candidate name + party abbreviation when available
        - Handle spanning headers like "No. of valid votes cast in favour of"
        
        Args:
            header_rows: List of header rows (each row is a list of cells)
            
        Returns:
            List of combined header names
        """
        if not header_rows:
            return []
        
        if len(header_rows) == 1:
            return header_rows[0]
        
        # Find the maximum number of columns
        max_cols = max(len(row) for row in header_rows)
        combined_headers = []
        
        # Check if we have a "PARTY ABBREVIATION" row (indicates multi-row structure)
        has_party_row = False
        party_row_idx = -1
        for idx, row in enumerate(header_rows):
            # Check first cell for "PARTY ABBREVIATION" or similar
            if row and row[0]:
                first_cell = row[0].strip().upper()
                if "PARTY" in first_cell or "ABBREVIATION" in first_cell:
                    has_party_row = True
                    party_row_idx = idx
                    break
        
        for col_idx in range(max_cols):
            header_parts = []
            
            # Collect non-empty values from all header rows for this column
            for row_idx, row in enumerate(header_rows):
                if col_idx < len(row) and row[col_idx]:
                    value = row[col_idx].strip()
                    if value:
                        # Skip generic labels like "PARTY ABBREVIATION" in first column
                        if col_idx == 0 and ("PARTY" in value.upper() or "ABBREVIATION" in value.upper()):
                            continue
                        # Skip spanning headers that don't add value
                        if value.upper() in ["NO. OF VALID VOTES CAST IN FAVOUR OF", "VALID VOTES"]:
                            continue
                        header_parts.append((row_idx, value))
            
            if not header_parts:
                # No header found for this column
                combined_headers.append(f"Column {col_idx + 1}")
                continue
            
            # Strategy: Use the most specific value
            # If we have party row, prefer combining candidate name + party
            if has_party_row and len(header_parts) >= 2:
                # Find candidate name (usually before party row)
                candidate_name = None
                party_name = None
                
                for row_idx, value in header_parts:
                    if row_idx < party_row_idx:
                        candidate_name = value
                    elif row_idx == party_row_idx:
                        party_name = value
                
                # Extract party name only (not candidate name)
                if party_name:
                    # Use party name only, ignore candidate name
                    combined_headers.append(party_name)
                elif candidate_name:
                    # No party found, but might be in candidate name format "NAME (PARTY)"
                    # Try to extract party from candidate name
                    import re
                    paren_match = re.search(r'\(([^)]+)\)', candidate_name)
                    if paren_match:
                        party_in_parens = paren_match.group(1).strip()
                        combined_headers.append(party_in_parens)
                    else:
                        # No party found, keep candidate name (will be fixed later)
                        combined_headers.append(candidate_name)
                else:
                    # Use the last (most specific) value
                    combined_headers.append(header_parts[-1][1])
            else:
                # No party row structure, use the most specific value
                # Prefer values from later rows (more specific)
                # Filter out generic/spanning headers
                specific_parts = [
                    value for row_idx, value in header_parts
                    if value.upper() not in [
                        "NO. OF VALID VOTES CAST IN FAVOUR OF",
                        "VALID VOTES",
                        "PARTY ABBREVIATION"
                    ]
                ]
                
                if specific_parts:
                    # Use the last (most specific) part
                    combined_headers.append(specific_parts[-1])
                elif header_parts:
                    # Fallback to last part even if generic
                    combined_headers.append(header_parts[-1][1])
                else:
                    combined_headers.append(f"Column {col_idx + 1}")
        
        return combined_headers
    
    def _is_numeric_string(self, value: str) -> bool:
        """Check if string represents a number."""
        if not value:
            return False
        try:
            float(value.replace(",", "").replace(" ", ""))
            return True
        except ValueError:
            return False
    
    def _is_duplicate_header(self, row: List[str], header_rows: List[List[str]]) -> bool:
        """
        Check if a row is a duplicate of any header row.
        
        This handles cases where headers repeat on each page of a multi-page table.
        """
        if not header_rows or not row:
            return False
        
        # Quick check: if first cell is numeric, it's NOT a header duplicate
        first_cell = row[0].strip() if row and row[0] else ""
        if first_cell and first_cell.isdigit():
            return False
        
        # Check for header keywords in the row
        row_text = " ".join(str(cell) for cell in row).upper()
        header_keywords = [
            "PARTY ABBREVIATION",
            "NO. OF VALID VOTES",
            "NO OF VALID VOTES",
            "VALID VOTES",
            "POLLING STATION",
            "SL. NO",
            "SL.NO",
            "SERIAL NUMBER"
        ]
        
        if any(keyword in row_text for keyword in header_keywords):
            return True
        
        for header_row in header_rows:
            # Compare non-empty cells
            row_values = [cell.strip() for cell in row if cell.strip()]
            header_values = [cell.strip() for cell in header_row if cell.strip()]
            
            if not row_values or not header_values:
                continue
            
            # Both must have significant content
            if len(row_values) < 3 or len(header_values) < 3:
                continue
            
            # Check if rows are similar (allowing for minor variations)
            text_matches = 0
            text_comparisons = 0
            total_checks = min(len(row), len(header_row))
            
            for i in range(total_checks):
                row_cell = row[i].strip().lower() if i < len(row) else ""
                header_cell = header_row[i].strip().lower() if i < len(header_row) else ""
                
                # Skip numeric cells
                if row_cell.isdigit() or header_cell.isdigit():
                    continue
                
                text_comparisons += 1
                if row_cell and header_cell and row_cell == header_cell:
                    text_matches += 1
            
            # Need at least 60% text match AND at least 3 text cells compared (more lenient)
            if text_comparisons >= 3 and (text_matches / text_comparisons) >= 0.6:
                return True
        
        return False

    def _clean_cell(self, value) -> str:
        """
        Clean and sanitize a cell value, including fixing reversed text.

        Args:
            value: Raw cell value

        Returns:
            Cleaned string value with reversed text fixed
        """
        if value is None:
            return ""

        # Convert to string
        text = str(value)

        # Handle NaN values
        if text.lower() in ("nan", "none", "null", "undefined"):
            return ""

        # Use sanitize_text which handles RTL characters and reversed text detection
        # This is critical for fixing corrupted polling area data
        from .utils import sanitize_text, _is_likely_reversed
        text = sanitize_text(text, single_line=False)
        
        # Second-pass validation: Re-check for reversed text after initial sanitization
        # This catches any cases that might have been missed in the first pass
        if text and _is_likely_reversed(text):
            # Try reversing again and re-sanitize
            reversed_text = text[::-1]
            re_sanitized = sanitize_text(reversed_text, single_line=False)
            # Only use reversed version if it's better (not still reversed)
            if not _is_likely_reversed(re_sanitized):
                logger.warning(
                    f"Fixed reversed text in second pass: '{text[:100]}...' -> '{re_sanitized[:100]}...'"
                )
                text = re_sanitized
            else:
                # If reversed version is still reversed, log warning but keep original
                logger.warning(
                    f"Text still appears reversed after second pass: '{text[:100]}...'"
                )
        
        # Normalize whitespace
        text = " ".join(text.split())

        # Strip leading/trailing whitespace
        return text.strip()

    def _merge_tables(self, tables: List[TableData]) -> TableData:
        """
        Merge multiple tables into a single table.

        Assumes all tables have the same column structure (headers).
        Uses headers from the first table and merges all data rows.

        Args:
            tables: List of TableData objects to merge

        Returns:
            Single merged TableData object
        """
        if not tables:
            return TableData(headers=[], rows=[], page_number=1)

        # Use headers from first non-empty table
        headers = []
        for table in tables:
            if table.headers:
                headers = table.headers
                break

        if not headers:
            logger.warning("No headers found in any table")
            return TableData(headers=[], rows=[], page_number=1)

        # Merge all rows from all tables with deduplication
        all_rows = []
        seen_rows = set()  # Track rows we've already added to prevent duplicates
        
        for table in tables:
            if table.rows:
                # Ensure row length matches headers
                for row in table.rows:
                    normalized_row = row[:]
                    if len(normalized_row) < len(headers):
                        normalized_row.extend([""] * (len(headers) - len(normalized_row)))
                    elif len(normalized_row) > len(headers):
                        normalized_row = normalized_row[:len(headers)]
                    
                    # Create a unique key for this row
                    # Use first 3 columns (typically S.L.No, Polling Station No., etc.) for identification
                    # If those are empty, use more columns or the full row
                    row_key_parts = []
                    for i in range(min(3, len(normalized_row))):
                        cell = str(normalized_row[i]).strip().lower()
                        if cell:  # Only include non-empty cells
                            row_key_parts.append(cell)
                    
                    # If first 3 columns are empty, use more columns (up to 5)
                    if not row_key_parts and len(normalized_row) > 3:
                        for i in range(3, min(5, len(normalized_row))):
                            cell = str(normalized_row[i]).strip().lower()
                            if cell:
                                row_key_parts.append(cell)
                    
                    # If still no key parts, use a hash of the full row (for completely empty rows)
                    if not row_key_parts:
                        row_str = "|".join(str(cell).strip() for cell in normalized_row)
                        row_key = hashlib.md5(row_str.encode()).hexdigest()
                    else:
                        row_key = tuple(row_key_parts)
                    
                    # Skip if we've seen this row before (duplicate)
                    if row_key not in seen_rows:
                        all_rows.append(normalized_row)
                        seen_rows.add(row_key)
                    else:
                        logger.debug(f"Skipping duplicate row: {normalized_row[:3]}")

        logger.info(f"Merged {len(tables)} tables into single table: {len(all_rows)} rows, {len(headers)} columns (duplicates removed)")

        # Post-processing validation: Scan all cells for any remaining reversed text
        # This ensures no corrupted text reaches Excel output
        from .utils import sanitize_text, _is_likely_reversed
        corrected_count = 0
        for row_idx, row in enumerate(all_rows):
            for col_idx, cell_value in enumerate(row):
                if isinstance(cell_value, str) and cell_value.strip():
                    # Re-apply sanitization to catch any missed cases
                    sanitized = sanitize_text(cell_value, single_line=False)
                    # Double-check for reversed text
                    if sanitized != cell_value or _is_likely_reversed(sanitized):
                        if _is_likely_reversed(sanitized):
                            # Try reversing and re-sanitizing
                            reversed_text = sanitized[::-1]
                            re_sanitized = sanitize_text(reversed_text, single_line=False)
                            if not _is_likely_reversed(re_sanitized):
                                all_rows[row_idx][col_idx] = re_sanitized
                                corrected_count += 1
                                logger.debug(
                                    f"Post-processing fix: Row {row_idx+1}, Col {col_idx+1}: "
                                    f"'{cell_value[:50]}...' -> '{re_sanitized[:50]}...'"
                                )
                            else:
                                # Keep original sanitized version if reversed is still reversed
                                all_rows[row_idx][col_idx] = sanitized
                        else:
                            # Just update with sanitized version
                            all_rows[row_idx][col_idx] = sanitized
                            if sanitized != cell_value:
                                corrected_count += 1
        
        if corrected_count > 0:
            logger.info(f"Post-processing validation: Corrected {corrected_count} cells with reversed/corrupted text")

        # Remove duplicate sequential number columns (e.g., PS No. and Sl.No with same values)
        headers, all_rows = self._remove_duplicate_serial_columns(headers, all_rows)

        return TableData(
            headers=headers,
            rows=all_rows,
            page_number=1,  # Merged table
        )

    def _remove_duplicate_serial_columns(
        self, headers: List[str], rows: List[List[str]]
    ) -> tuple[List[str], List[List[str]]]:
        """
        Remove duplicate sequential number columns from the table.

        Some PDFs have duplicate serial number columns (e.g., 'PS No.' and 'Sl.No')
        that contain identical sequential values. This method detects and removes
        such duplicates.

        Args:
            headers: List of column headers
            rows: List of data rows

        Returns:
            Tuple of (cleaned_headers, cleaned_rows) with duplicates removed
        """
        if len(headers) < 2 or len(rows) < 3:
            return headers, rows

        columns_to_remove = set()

        # Check consecutive column pairs for duplicate sequential patterns
        for col_idx in range(len(headers) - 1):
            if col_idx in columns_to_remove:
                continue

            # Get values from both columns
            col1_values = [row[col_idx] if col_idx < len(row) else "" for row in rows[:20]]
            col2_values = [row[col_idx + 1] if col_idx + 1 < len(row) else "" for row in rows[:20]]

            # Check if both columns have sequential numbers
            if self._is_sequential_number_column(col1_values) and self._is_sequential_number_column(col2_values):
                # Check if values are identical or nearly identical
                if self._columns_have_identical_values(col1_values, col2_values):
                    header1 = headers[col_idx].upper() if headers[col_idx] else ""
                    header2 = headers[col_idx + 1].upper() if headers[col_idx + 1] else ""

                    # Only remove if BOTH headers are serial number type columns
                    # DO NOT remove columns with meaningful names like "Polling Station No."
                    meaningful_keywords = ["POLLING", "STATION", "LOCATION", "BOOTH", "BUILDING", "AREA"]
                    serial_keywords = ["SL.", "SL ", "SERIAL", "S.NO", "PS NO", "P.S.", "PS."]

                    # Check if either header has meaningful content (not just serial numbers)
                    header1_is_meaningful = any(kw in header1 for kw in meaningful_keywords)
                    header2_is_meaningful = any(kw in header2 for kw in meaningful_keywords)

                    # If either column has meaningful header, don't remove it
                    if header1_is_meaningful or header2_is_meaningful:
                        logger.debug(f"Keeping both columns - meaningful headers: '{headers[col_idx]}', '{headers[col_idx + 1]}'")
                        continue

                    # Both are serial-type columns - check which to remove
                    header1_is_serial = any(kw in header1 for kw in serial_keywords)
                    header2_is_serial = any(kw in header2 for kw in serial_keywords)

                    # Only remove if both are serial-type columns
                    if header1_is_serial and header2_is_serial:
                        # Prefer keeping "Sl.No" over "PS No."
                        if "SL" in header2 and "PS" in header1:
                            columns_to_remove.add(col_idx)
                            logger.info(f"Removing duplicate column '{headers[col_idx]}' (keeping '{headers[col_idx + 1]}')")
                        elif "SL" in header1 and "PS" in header2:
                            columns_to_remove.add(col_idx + 1)
                            logger.info(f"Removing duplicate column '{headers[col_idx + 1]}' (keeping '{headers[col_idx]}')")
                        else:
                            # Default: remove the first one
                            columns_to_remove.add(col_idx)
                            logger.info(f"Removing duplicate sequential column '{headers[col_idx]}'")

        if not columns_to_remove:
            return headers, rows

        # Build new headers and rows without the duplicate columns
        new_headers = [h for i, h in enumerate(headers) if i not in columns_to_remove]
        new_rows = []
        for row in rows:
            new_row = [val for i, val in enumerate(row) if i not in columns_to_remove]
            new_rows.append(new_row)

        logger.info(f"Removed {len(columns_to_remove)} duplicate column(s)")
        return new_headers, new_rows

    def _is_sequential_number_column(self, values: List[str]) -> bool:
        """
        Check if column values form a sequential number pattern.

        Args:
            values: List of column values

        Returns:
            True if values are sequential numbers (1, 2, 3, ...)
        """
        numbers = []
        for val in values:
            if val and str(val).strip():
                try:
                    num = int(str(val).strip())
                    numbers.append(num)
                except (ValueError, TypeError):
                    # If any non-numeric value, not a sequential number column
                    if len(numbers) < 3:
                        return False

        if len(numbers) < 3:
            return False

        # Check if mostly sequential (allowing some gaps)
        sequential_count = sum(
            1 for i in range(1, len(numbers))
            if numbers[i] == numbers[i-1] + 1 or numbers[i] == numbers[i-1]
        )

        return sequential_count >= len(numbers) * 0.7

    def _columns_have_identical_values(self, col1: List[str], col2: List[str]) -> bool:
        """
        Check if two columns have identical or nearly identical values.

        Args:
            col1: First column values
            col2: Second column values

        Returns:
            True if columns have identical values
        """
        matches = 0
        comparisons = 0

        for v1, v2 in zip(col1, col2):
            v1_clean = str(v1).strip() if v1 else ""
            v2_clean = str(v2).strip() if v2 else ""

            if v1_clean or v2_clean:
                comparisons += 1
                if v1_clean == v2_clean:
                    matches += 1

        if comparisons < 3:
            return False

        return matches / comparisons >= 0.8

    def _extract_page_texts(self) -> List[str]:
        """Extract raw text from all pages of the PDF."""
        import pdfplumber
        
        page_texts = []
        
        try:
            with pdfplumber.open(str(self.file_path)) as pdf:
                for page in pdf.pages:
                    try:
                        text = page.extract_text() or ""
                        page_texts.append(text)
                    except Exception as e:
                        logger.warning(f"Error extracting text from page: {e}")
                        page_texts.append("")
        except Exception as e:
            logger.error(f"Error extracting page texts: {e}", exc_info=True)
            return []
        
        return page_texts

    def get_page_count(self) -> int:
        """Get the number of pages in the PDF."""
        import pdfplumber

        with pdfplumber.open(str(self.file_path)) as pdf:
            return len(pdf.pages)

    def get_extraction_summary(self) -> dict:
        """
        Get summary of the extraction process.

        Returns:
            Dictionary with extraction metadata
        """
        summary = {
            "file_path": str(self.file_path),
            "file_name": self.file_path.name,
            "page_count": self.get_page_count(),
            "force_ocr": self.force_ocr,
            "auto_detect": self.auto_detect,
        }

        if self._detection_result:
            summary["detection"] = self._detection_result.to_dict()

        if self._validation_report:
            summary["validation"] = self._validation_report.to_dict()

        return summary
    
    def _ensure_perfect_alignment(
        self, 
        headers: List[str], 
        data_rows: List[List[str]], 
        sample_raw_data: List[List] = None
    ) -> Tuple[List[str], List[List[str]]]:
        """
        Ensure perfect alignment between headers and data columns.
        
        This method validates that:
        1. Number of headers matches number of data columns
        2. Headers align correctly with data columns
        3. Adjusts headers or data if misalignment is detected
        
        Args:
            headers: List of header names
            data_rows: List of data rows
            sample_raw_data: Sample of raw table data for validation
            
        Returns:
            Tuple of (adjusted_headers, adjusted_data_rows)
        """
        if not headers or not data_rows:
            return headers, data_rows
        
        # Check if we have a consistent column count across data rows
        if data_rows:
            # Find the most common column count in data rows
            column_counts = [len(row) for row in data_rows if row]
            if column_counts:
                most_common_count = max(set(column_counts), key=column_counts.count)
                
                # If headers don't match the most common column count, adjust
                if len(headers) != most_common_count:
                    logger.warning(
                        f"Header count ({len(headers)}) doesn't match data column count ({most_common_count}). "
                        f"Adjusting headers to match data."
                    )
                    
                    if len(headers) < most_common_count:
                        # Add empty headers for missing columns
                        headers.extend([f"Column {i+1}" for i in range(len(headers), most_common_count)])
                    elif len(headers) > most_common_count:
                        # Trim excess headers
                        headers = headers[:most_common_count]
                
                # Ensure all data rows have the same length as headers
                for i, row in enumerate(data_rows):
                    if len(row) < len(headers):
                        data_rows[i] = row + [""] * (len(headers) - len(row))
                    elif len(row) > len(headers):
                        data_rows[i] = row[:len(headers)]
        
        # Validate alignment using sample data if available
        if sample_raw_data and len(sample_raw_data) > 0:
            # Check if first data row aligns with headers
            first_data_row = [self._clean_cell(cell) for cell in sample_raw_data[0]] if sample_raw_data else []
            if first_data_row and len(first_data_row) != len(headers):
                logger.debug(
                    f"Sample data has {len(first_data_row)} columns, headers have {len(headers)}. "
                    f"Using data column count as reference."
                )
                # Use data column count as the source of truth
                if len(first_data_row) > len(headers):
                    # Add missing headers
                    headers.extend([f"Column {i+1}" for i in range(len(headers), len(first_data_row))])
                elif len(first_data_row) < len(headers):
                    # Trim excess headers
                    headers = headers[:len(first_data_row)]
        
        logger.debug(f"Final alignment: {len(headers)} headers, data rows with {len(data_rows[0]) if data_rows else 0} columns")
        return headers, data_rows
    


# Convenience functions for direct use


async def extract_tables_from_pdf(
    pdf_path: str,
    force_ocr: bool = False,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Tuple[ExtractionResult, dict]:
    """
    Convenience function to extract tables from a PDF.

    Args:
        pdf_path: Path to the PDF file
        force_ocr: Force OCR extraction
        progress_callback: Optional progress callback

    Returns:
        Tuple of (ExtractionResult, extraction_summary_dict)
    """
    processor = PDFProcessor(pdf_path, force_ocr=force_ocr)
    result = await processor.extract_tables(progress_callback)
    summary = processor.get_extraction_summary()
    return result, summary


def detect_pdf_type(pdf_path: str) -> dict:
    """
    Convenience function to detect PDF type.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Detection result dictionary
    """
    detector = PDFTypeDetector()
    result = detector.detect(pdf_path)
    return result.to_dict()
