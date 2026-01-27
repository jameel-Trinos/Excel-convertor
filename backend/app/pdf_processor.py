"""PDF table extraction with automatic text/image detection and OCR support."""

import asyncio
import logging
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

            # Extract using appropriate method
            if use_ocr:
                result = await self._extract_with_ocr(update_progress)
                extraction_method = "ocr"
            else:
                update_progress(10, "Extracting tables from PDF...")
                tables = await asyncio.to_thread(self._extract_with_pdfplumber, update_progress)

                if not tables or all(t.is_empty for t in tables):
                    # Fallback to OCR if pdfplumber finds nothing
                    logger.info("No tables found with pdfplumber, falling back to OCR...")
                    update_progress(50, "No text tables found, trying OCR...")
                    result = await self._extract_with_ocr(update_progress)
                    extraction_method = "ocr_fallback"
                else:
                    # Merge all tables into a single table
                    update_progress(80, "Merging tables from all pages...")
                    merged_table = self._merge_tables(tables)
                    result = ExtractionResult(
                        tables=[merged_table],
                        page_texts=[],
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
        Extract tables using OCR.

        Args:
            progress_callback: Progress callback function

        Returns:
            ExtractionResult from OCR extraction
        """
        from .ocr_processor import OCRProcessor, OCRConfig

        def update_progress(progress: int, message: str):
            if progress_callback:
                # Adjust progress range for OCR phase (10-90%)
                adjusted = int(10 + (progress * 0.8))
                progress_callback(adjusted, message)

        logger.info("Starting OCR extraction...")
        update_progress(0, "Initializing OCR processor...")

        # Configure OCR
        config = OCRConfig(
            dpi=300,
            denoise=True,
            deskew=True,
            contrast_enhance=True,
            use_easyocr_fallback=True,
            min_confidence=50.0,
        )

        # Run OCR extraction
        ocr_processor = OCRProcessor(str(self.file_path), config)
        result = await asyncio.to_thread(
            ocr_processor.extract_tables,
            update_progress
        )

        if not result.tables or all(t.is_empty for t in result.tables):
            raise ExtractionError("OCR extraction found no tables in the PDF")

        return result

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

        # Detect header rows (typically 2-4 rows at the top)
        # Headers are rows with mostly text, not numbers
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
            
            # Check if this looks like a header row
            # Headers typically have more text than numbers
            numeric_count = sum(1 for cell in non_empty if self._is_numeric_string(cell))
            text_count = len(non_empty) - numeric_count
            
            # If mostly text (at least 60% text), it's likely a header row
            if len(non_empty) > 0 and text_count / len(non_empty) >= 0.6:
                header_rows.append(cleaned_row)
                data_start_idx = idx + 1
            else:
                # Found first data row
                break
        
        # If no header rows detected, use first row as headers
        if not header_rows:
            header_rows = [[self._clean_cell(cell) for cell in table[0]]]
            data_start_idx = 1
        
        # Combine multi-row headers intelligently
        headers = self._combine_header_rows(header_rows)
        
        # Extract data rows
        data_rows = []
        for row in table[data_start_idx:]:
            cleaned_row = [self._clean_cell(cell) for cell in row]
            # Skip completely empty rows
            if any(cell.strip() for cell in cleaned_row if cell):
                # Skip duplicate header rows (headers that appear again mid-table)
                if self._is_duplicate_header(cleaned_row, header_rows):
                    continue
                # Normalize row length to match headers
                if len(cleaned_row) < len(headers):
                    cleaned_row.extend([""] * (len(headers) - len(cleaned_row)))
                elif len(cleaned_row) > len(headers):
                    cleaned_row = cleaned_row[:len(headers)]
                data_rows.append(cleaned_row)

        return headers, data_rows
    
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
                
                if candidate_name and party_name:
                    # Combine: "CANDIDATE_NAME (PARTY)"
                    combined = f"{candidate_name} ({party_name})"
                    combined_headers.append(combined)
                elif candidate_name:
                    combined_headers.append(candidate_name)
                elif party_name:
                    combined_headers.append(party_name)
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
        Clean and sanitize a cell value.

        Args:
            value: Raw cell value

        Returns:
            Cleaned string value
        """
        if value is None:
            return ""

        # Convert to string
        text = str(value)

        # Handle NaN values
        if text.lower() in ("nan", "none", "null", "undefined"):
            return ""

        # Remove null bytes and control characters
        text = text.replace("\x00", "")
        text = "".join(char for char in text if ord(char) >= 32 or char in "\n\t")

        # Replace newlines with spaces
        text = text.replace("\n", " ").replace("\r", " ")
        
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

        # Merge all rows from all tables
        all_rows = []
        for table in tables:
            if table.rows:
                # Ensure row length matches headers
                for row in table.rows:
                    normalized_row = row[:]
                    if len(normalized_row) < len(headers):
                        normalized_row.extend([""] * (len(headers) - len(normalized_row)))
                    elif len(normalized_row) > len(headers):
                        normalized_row = normalized_row[:len(headers)]
                    all_rows.append(normalized_row)

        logger.info(f"Merged {len(tables)} tables into single table: {len(all_rows)} rows, {len(headers)} columns")
        
        return TableData(
            headers=headers,
            rows=all_rows,
            page_number=1,  # Merged table
        )

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
