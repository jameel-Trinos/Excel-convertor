"""
Deterministic election PDF processor.

Extracts party names from headers ONCE and applies them consistently.
NO AI inference, NO column guessing - pure header parsing.
"""

import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .header_extractor import HeaderExtractor
from .models import ExtractionResult, TableData
from .party_normalizer import PartyNormalizer

logger = logging.getLogger(__name__)


class ElectionProcessor:
    """
    Deterministic processor for election PDF documents.

    Key features:
    - Extracts column headers ONLY from first page
    - Maps party abbreviations to standardized names
    - Extracts data rows without header regeneration
    - Produces consistent, deterministic output
    """

    # Metadata columns (always included first)
    METADATA_COLUMNS = ["SL. NO.", "Polling Station"]

    # Summary columns (always included last)
    SUMMARY_COLUMNS = [
        "NOTA",
        "TOTAL VALID VOTES",
        "NO OF REJECTED VOTES",
        "TOTAL",
        "NO.OF TENDERED VOTES",
    ]

    # Normalized versions for matching
    IGNORE_FOR_PARTY = {
        "slno", "sl.no", "sl no", "serial", "serialno", "serialnumber",
        "pollingstation", "polling", "station",
        "nota", "noneoftheabove",
        "totalvalidvotes", "validvotes", "totalvotes", "total",
        "rejectedvotes", "noofrejectedvotes",
        "tenderedvotes", "nooftenderedvotes",
    }

    def __init__(self, file_path: str):
        """
        Initialize election processor.

        Args:
            file_path: Path to the PDF file
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        self.header_extractor = HeaderExtractor(file_path)
        self.party_normalizer = PartyNormalizer()

        # Cached extraction results
        self._headers: Optional[List[str]] = None
        self._party_column_indices: Optional[Dict[int, str]] = None
        self._column_mapping: Optional[Dict[str, str]] = None

    def extract_headers(self) -> Tuple[List[str], Dict[str, str]]:
        """
        Extract and standardize headers from PDF.

        Returns:
            Tuple of:
            - List of standardized column headers
            - Dict mapping original header to standardized name
        """
        if self._headers is not None:
            return self._headers, self._column_mapping

        import pdfplumber

        standardized_headers = []
        original_to_standard = {}
        party_columns_found = []
        independent_count = 0

        with pdfplumber.open(str(self.file_path)) as pdf:
            if not pdf.pages:
                logger.warning("PDF has no pages")
                return [], {}

            page = pdf.pages[0]

            # Get the table from first page
            tables = page.extract_tables()

            if not tables:
                table_settings = {
                    "vertical_strategy": "lines_strict",
                    "horizontal_strategy": "lines_strict",
                }
                tables = page.extract_tables(table_settings)

            if not tables:
                logger.warning("No tables found on first page")
                return [], {}

            first_table = tables[0]
            if not first_table or len(first_table) < 2:
                return [], {}

            # Find header row - look for row with party abbreviations in parentheses
            header_row = self._find_header_row(first_table)

            if not header_row:
                logger.warning("Could not identify header row")
                return [], {}

            # Process each column
            for idx, cell in enumerate(header_row):
                if not cell:
                    standardized_headers.append(f"Column_{idx}")
                    continue

                cell_text = self._clean_cell(str(cell))
                cell_normalized = self._normalize_for_match(cell_text)

                # Check if it's a metadata/summary column
                if cell_normalized in self.IGNORE_FOR_PARTY:
                    # Keep original name but clean it
                    standardized_headers.append(cell_text.upper())
                    original_to_standard[cell_text] = cell_text.upper()
                    continue

                # Try to extract party from parentheses
                party_name = self._extract_party_from_cell(cell_text)

                if party_name:
                    # Normalize the party name
                    standard_party = self.party_normalizer.normalize_column_name(party_name)

                    if standard_party:
                        if standard_party == "Independent":
                            independent_count += 1
                            col_name = f"IND_{independent_count}"
                            standardized_headers.append(col_name)
                            original_to_standard[cell_text] = col_name
                            party_columns_found.append(col_name)
                        else:
                            standardized_headers.append(standard_party)
                            original_to_standard[cell_text] = standard_party
                            party_columns_found.append(standard_party)
                    else:
                        # Unknown party - keep abbreviation with Votes suffix
                        col_name = f"{party_name} Votes"
                        standardized_headers.append(col_name)
                        original_to_standard[cell_text] = col_name
                        party_columns_found.append(col_name)
                else:
                    # Not a party column - keep as is
                    standardized_headers.append(cell_text)
                    original_to_standard[cell_text] = cell_text

        self._headers = standardized_headers
        self._column_mapping = original_to_standard

        logger.info(f"Extracted {len(standardized_headers)} columns, {len(party_columns_found)} party columns")

        return standardized_headers, original_to_standard

    def _find_header_row(self, table: List[List]) -> Optional[List]:
        """Find the header row in a table."""
        # Check first 5 rows for header pattern
        for row_idx, row in enumerate(table[:5]):
            if not row:
                continue

            # Count cells with party pattern (NAME (PARTY))
            party_pattern_count = 0
            total_text_cells = 0

            for cell in row:
                if not cell:
                    continue

                cell_str = str(cell).upper()
                total_text_cells += 1

                if re.search(r'\([A-Z]+\)', cell_str):
                    party_pattern_count += 1

            # If at least 3 party patterns found, this is likely the header
            if party_pattern_count >= 3:
                logger.info(f"Found header row at index {row_idx} with {party_pattern_count} party columns")
                return row

            # Also check if row has many text cells (potential header row)
            if total_text_cells >= 5:
                # Check if cells are mostly text (not numbers)
                numeric_count = sum(
                    1 for cell in row if cell and self._is_numeric(str(cell))
                )
                if numeric_count < total_text_cells * 0.3:  # Less than 30% numbers
                    logger.info(f"Found header row at index {row_idx} based on text content")
                    return row

        # Fallback: return first non-empty row after any title rows
        for row in table[1:]:  # Skip first row (might be title)
            if row and len([c for c in row if c and str(c).strip()]) > 3:
                return row

        return table[0] if table else None

    def _extract_party_from_cell(self, cell_text: str) -> Optional[str]:
        """
        Extract party abbreviation from cell text.

        Handles formats like:
        - "CANDIDATE NAME (BJP)"
        - "CANDIDATE NAME. R (AIADMK)"
        - "BJP" (bare abbreviation)
        """
        cell_upper = cell_text.upper()

        # Try to extract from parentheses
        match = re.search(r'\(([A-Z]+)\)', cell_upper)
        if match:
            return match.group(1)

        # Check if cell is just a party abbreviation
        clean = re.sub(r'[\s.\-_]+', '', cell_upper)
        known_parties = [
            "BJP", "AIADMK", "DMK", "INC", "CONGRESS", "VCK", "PMK",
            "NTK", "BSP", "NMK", "MDMK", "CPI", "CPM", "CPIM", "IND",
        ]

        for party in known_parties:
            if clean == party or clean.startswith(party):
                return party

        return None

    def _is_numeric(self, value: str) -> bool:
        """Check if string is numeric."""
        try:
            float(value.replace(",", "").replace(" ", ""))
            return True
        except ValueError:
            return False

    def _normalize_for_match(self, text: str) -> str:
        """Normalize text for matching against known columns."""
        return re.sub(r'[\s.\-_]+', '', text.lower())

    def _clean_cell(self, value: str) -> str:
        """Clean cell value."""
        if not value:
            return ""

        if value.lower() in ("nan", "none", "null"):
            return ""

        # Normalize whitespace
        text = " ".join(value.split())

        # Handle vertical text (spaced letters): "B J P" -> "BJP"
        if re.match(r'^([A-Z] )+[A-Z]$', text.upper()):
            text = text.replace(" ", "")

        return text.strip()

    async def extract_all(
        self,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> ExtractionResult:
        """
        Extract headers and data from PDF.

        Args:
            progress_callback: Optional progress callback

        Returns:
            ExtractionResult with standardized headers and data
        """
        import asyncio
        import pdfplumber

        def update_progress(progress: int, message: str):
            if progress_callback:
                progress_callback(progress, message)

        # Step 1: Extract headers (cached)
        update_progress(10, "Extracting column headers...")
        headers, column_mapping = self.extract_headers()

        if not headers:
            raise ValueError("Failed to extract headers from PDF")

        # Step 2: Extract page texts
        update_progress(20, "Extracting page text...")
        page_texts = await asyncio.to_thread(self._extract_page_texts)

        # Step 3: Extract all tables
        update_progress(30, "Extracting data tables...")
        tables = await asyncio.to_thread(
            self._extract_tables_with_headers, headers, update_progress
        )

        update_progress(100, "Extraction complete")

        return ExtractionResult(
            tables=tables,
            page_texts=page_texts,
            column_mapping={h: [h] for h in headers if h},  # Simple mapping
        )

    def _extract_page_texts(self) -> List[str]:
        """Extract raw text from all pages."""
        import pdfplumber

        page_texts = []

        with pdfplumber.open(str(self.file_path)) as pdf:
            for page in pdf.pages:
                try:
                    text = page.extract_text() or ""
                    page_texts.append(text)
                except Exception:
                    page_texts.append("")

        return page_texts

    def _extract_tables_with_headers(
        self,
        standardized_headers: List[str],
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> List[TableData]:
        """
        Extract tables using pre-extracted headers.

        Headers are applied consistently across all pages.
        """
        import pdfplumber

        all_tables = []

        with pdfplumber.open(str(self.file_path)) as pdf:
            total_pages = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, 1):
                if progress_callback:
                    progress = int(30 + (page_num / total_pages) * 60)
                    progress_callback(progress, f"Processing page {page_num} of {total_pages}...")

                # Try multiple extraction strategies
                tables = page.extract_tables()

                if not tables or all(not t or len(t) < 2 for t in tables):
                    table_settings = {
                        "vertical_strategy": "lines_strict",
                        "horizontal_strategy": "lines_strict",
                    }
                    tables = page.extract_tables(table_settings)

                if not tables or all(not t or len(t) < 2 for t in tables):
                    table_settings = {
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                    }
                    tables = page.extract_tables(table_settings)

                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    # Extract data rows only (skip headers/titles)
                    data_rows = self._extract_data_rows(table, standardized_headers)

                    if data_rows:
                        table_data = TableData(
                            headers=standardized_headers,
                            rows=data_rows,
                            page_number=page_num,
                        )
                        all_tables.append(table_data)

        return all_tables

    def _extract_data_rows(
        self,
        table: List[List],
        expected_headers: List[str],
    ) -> List[List[str]]:
        """
        Extract data rows from table, skipping headers and titles.

        Args:
            table: Raw table data
            expected_headers: Expected column headers (for matching)

        Returns:
            List of cleaned data rows
        """
        data_rows = []
        skip_count = 0

        for row_idx, row in enumerate(table):
            if not row:
                continue

            cleaned_row = [self._clean_cell(str(cell)) if cell else "" for cell in row]

            # Skip if row looks like a header or title
            if self._is_header_row(cleaned_row):
                skip_count += 1
                continue

            # Skip if row looks like a title (few cells filled)
            non_empty = [c for c in cleaned_row if c.strip()]
            if len(non_empty) <= 2 and len(cleaned_row) > 3:
                skip_count += 1
                continue

            # Skip empty rows
            if not any(c.strip() for c in cleaned_row):
                continue

            # Normalize row length to match headers
            num_headers = len(expected_headers)
            if len(cleaned_row) < num_headers:
                cleaned_row.extend([""] * (num_headers - len(cleaned_row)))
            elif len(cleaned_row) > num_headers:
                cleaned_row = cleaned_row[:num_headers]

            data_rows.append(cleaned_row)

        logger.debug(f"Extracted {len(data_rows)} data rows, skipped {skip_count} header/title rows")

        return data_rows

    def _is_header_row(self, row: List[str]) -> bool:
        """Check if row is a header row (should be skipped)."""
        # Check for party pattern in cells
        party_pattern_count = sum(
            1 for cell in row if cell and re.search(r'\([A-Z]+\)', cell.upper())
        )
        if party_pattern_count >= 3:
            return True

        # Check if row contains mostly text (not numbers)
        non_empty = [c for c in row if c.strip()]
        if not non_empty:
            return False

        numeric_count = sum(1 for c in non_empty if self._is_numeric(c))
        text_ratio = (len(non_empty) - numeric_count) / len(non_empty)

        # If more than 70% text, likely a header
        if text_ratio > 0.7 and len(non_empty) > 3:
            return True

        return False

    def get_party_columns(self) -> List[str]:
        """
        Get list of party vote columns found in PDF.

        Returns:
            List of standardized party column names
        """
        headers, _ = self.extract_headers()

        party_columns = []
        for header in headers:
            # Check if it's a party column (ends with "Votes" or is "Independent")
            if header.endswith(" Votes") or header.startswith("IND_"):
                party_columns.append(header)

        return party_columns

    def get_output_column_order(self) -> List[str]:
        """
        Get standardized output column order.

        Returns columns in this order:
        1. Metadata columns (SL. NO., Polling Station)
        2. Party columns (in order found)
        3. Summary columns (NOTA, Total, etc.)
        """
        headers, _ = self.extract_headers()

        # Categorize columns
        metadata = []
        parties = []
        summary = []
        other = []

        for header in headers:
            header_norm = self._normalize_for_match(header)

            if any(m in header_norm for m in ["slno", "serial", "polling", "station"]):
                metadata.append(header)
            elif any(s in header_norm for s in ["nota", "total", "rejected", "tendered", "valid"]):
                summary.append(header)
            elif header.endswith(" Votes") or header.startswith("IND_"):
                parties.append(header)
            else:
                other.append(header)

        return metadata + parties + other + summary


def extract_election_data(pdf_path: str) -> Dict[str, Any]:
    """
    Main function to extract election data from PDF.

    Args:
        pdf_path: Path to election PDF

    Returns:
        Dict containing:
        - headers: Standardized column headers
        - party_columns: List of party vote column names
        - column_mapping: Mapping of original to standard names
    """
    processor = ElectionProcessor(pdf_path)

    headers, column_mapping = processor.extract_headers()
    party_columns = processor.get_party_columns()
    output_order = processor.get_output_column_order()

    return {
        "headers": headers,
        "party_columns": party_columns,
        "column_mapping": column_mapping,
        "output_column_order": output_order,
    }
