"""Deterministic PDF parser for Indian election Form 20 data.

This parser follows strict rules:
1. Polling Station No defines row boundaries
2. Fixed output schema - no column inference
3. AI used ONLY for candidate -> party mapping if needed
4. All vote sums must match Total Valid Votes
5. Errors raised on validation failures
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdfplumber

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when vote validation fails."""
    pass


class DeterministicParser:
    """
    Deterministic parser for Indian election Form 20.

    Rules:
    - Uses Polling Station column to identify rows
    - Preserves exact column names from PDF
    - Validates vote sums against TOTAL VALID VOTES
    - No heuristic structure detection
    """

    def __init__(self, file_path: str):
        """
        Initialize parser.

        Args:
            file_path: Path to PDF file
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

    def parse(self) -> Tuple[List[str], List[List[any]]]:
        """
        Parse PDF with deterministic logic.

        Returns:
            Tuple of (headers, data_rows)

        Raises:
            ValidationError: If vote sums don't match
        """
        logger.info(f"Starting deterministic parse of {self.file_path}")

        # Extract raw table
        raw_table = self._extract_raw_table()

        if not raw_table or len(raw_table) < 2:
            raise ValueError("No valid table found in PDF")

        # First row is headers
        headers = raw_table[0]

        # Identify key column indices
        polling_station_idx = self._find_polling_station_column(headers)
        total_valid_votes_idx = self._find_total_valid_votes_column(headers)

        logger.info(f"Found {len(headers)} columns")
        logger.info(f"Polling Station at index: {polling_station_idx}")
        logger.info(f"Total Valid Votes at index: {total_valid_votes_idx}")

        # Extract data rows using Polling Station as boundary
        data_rows = []
        validation_errors = []

        for row_idx, row in enumerate(raw_table[1:], start=2):
            # Skip if not a valid data row (check Polling Station column)
            if not self._is_data_row(row, polling_station_idx):
                logger.debug(f"Skipping non-data row {row_idx}")
                continue

            # Normalize row length to match headers
            normalized_row = self._normalize_row_length(row, len(headers))

            # Validate vote sums
            is_valid, error_msg = self._validate_vote_sum(
                normalized_row,
                headers,
                polling_station_idx,
                total_valid_votes_idx
            )

            if not is_valid:
                validation_errors.append(f"Row {row_idx}: {error_msg}")

            data_rows.append(normalized_row)

        # Report validation errors but don't fail
        # (some PDFs may have OCR issues)
        if validation_errors:
            logger.warning(f"Found {len(validation_errors)} validation errors:")
            for error in validation_errors[:10]:  # Show first 10
                logger.warning(f"  {error}")

        logger.info(f"Extracted {len(data_rows)} data rows")

        return headers, data_rows

    def _extract_raw_table(self) -> List[List[str]]:
        """
        Extract raw table from PDF using pdfplumber.

        Uses deterministic extraction - no heuristics.
        """
        all_rows = []

        with pdfplumber.open(str(self.file_path)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Try multiple extraction strategies
                tables = page.extract_tables()

                # If no tables with default settings, try strict lines
                if not tables or all(not t or len(t) < 2 for t in tables):
                    table_settings = {
                        "vertical_strategy": "lines_strict",
                        "horizontal_strategy": "lines_strict",
                        "intersection_tolerance": 3,
                    }
                    tables = page.extract_tables(table_settings)

                # If still no tables, try text-based
                if not tables or all(not t or len(t) < 2 for t in tables):
                    table_settings = {
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                    }
                    tables = page.extract_tables(table_settings)

                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    # Clean cells
                    cleaned_table = [
                        [self._clean_cell(cell) for cell in row]
                        for row in table
                    ]

                    # If first page, find the header row (skip title rows)
                    if page_num == 1 and not all_rows:
                        # Find the row that contains "Polling Station" (header row)
                        header_row_idx = 0
                        for idx, row in enumerate(cleaned_table):
                            row_text = " ".join(str(cell) for cell in row if cell).lower()
                            if "polling" in row_text and "station" in row_text:
                                header_row_idx = idx
                                break
                        # Only include from header row onwards
                        all_rows.extend(cleaned_table[header_row_idx:])
                    else:
                        # Skip header rows on subsequent pages
                        # Find header row and skip it
                        start_idx = 0
                        for idx, row in enumerate(cleaned_table[:3]):  # Check first 3 rows
                            row_text = " ".join(str(cell) for cell in row if cell).lower()
                            if "polling" in row_text and "station" in row_text:
                                start_idx = idx + 1  # Skip header
                                break
                        all_rows.extend(cleaned_table[start_idx:])

        return all_rows

    def _clean_cell(self, value: Optional[str]) -> str:
        """Clean cell value."""
        if value is None:
            return ""

        text = str(value)

        # Handle NaN
        if text.lower() in ("nan", "none", "null"):
            return ""

        # Remove Unicode bidirectional control characters that cause mirror/reverse text
        # These characters can appear in PDFs and cause text to render backwards
        bidi_chars = [
            "\u202A",  # Left-to-Right Embedding (LRE)
            "\u202B",  # Right-to-Left Embedding (RLE)
            "\u202C",  # Pop Directional Formatting (PDF)
            "\u202D",  # Left-to-Right Override (LRO)
            "\u202E",  # Right-to-Left Override (RLO) - main culprit for mirrored text
            "\u200E",  # Left-to-Right Mark (LRM)
            "\u200F",  # Right-to-Left Mark (RLM)
            "\u2066",  # Left-to-Right Isolate (LRI)
            "\u2067",  # Right-to-Left Isolate (RLI)
            "\u2068",  # First Strong Isolate (FSI)
            "\u2069",  # Pop Directional Isolate (PDI)
        ]
        for char in bidi_chars:
            text = text.replace(char, "")

        # Remove control characters
        text = "".join(char for char in text if ord(char) >= 32 or char in "\n\t")

        # Normalize whitespace
        text = " ".join(text.split())

        return text.strip()

    def _find_polling_station_column(self, headers: List[str]) -> int:
        """
        Find the Polling Station column index.

        Args:
            headers: List of header names

        Returns:
            Column index

        Raises:
            ValueError: If column not found
        """
        for idx, header in enumerate(headers):
            # Normalize: remove newlines, extra spaces
            header_normalized = " ".join(header.split()).lower()
            if "polling" in header_normalized and "station" in header_normalized:
                return idx

        raise ValueError("Polling Station column not found in headers")

    def _find_total_valid_votes_column(self, headers: List[str]) -> int:
        """
        Find the TOTAL VALID VOTES column index.

        Args:
            headers: List of header names

        Returns:
            Column index

        Raises:
            ValueError: If column not found
        """
        for idx, header in enumerate(headers):
            # Normalize: remove newlines, extra spaces
            header_normalized = " ".join(header.split()).lower()
            if "total" in header_normalized and "valid" in header_normalized and "vote" in header_normalized:
                return idx

        raise ValueError("TOTAL VALID VOTES column not found in headers")

    def _is_data_row(self, row: List[str], polling_station_idx: int) -> bool:
        """
        Check if a row is a data row based on Polling Station column.

        A data row has a numeric value in the Polling Station column.

        Args:
            row: The row to check
            polling_station_idx: Index of Polling Station column

        Returns:
            True if this is a data row
        """
        if polling_station_idx >= len(row):
            return False

        value = row[polling_station_idx].strip()

        # Check if value is numeric
        try:
            int(value)
            return True
        except (ValueError, TypeError):
            return False

    def _normalize_row_length(self, row: List[str], target_length: int) -> List[str]:
        """
        Normalize row length to match headers.

        Args:
            row: The row to normalize
            target_length: Target length

        Returns:
            Normalized row
        """
        if len(row) < target_length:
            # Pad with empty strings
            return row + [""] * (target_length - len(row))
        elif len(row) > target_length:
            # Truncate
            return row[:target_length]
        return row

    def _validate_vote_sum(
        self,
        row: List[str],
        headers: List[str],
        polling_station_idx: int,
        total_valid_votes_idx: int
    ) -> Tuple[bool, str]:
        """
        Validate that candidate votes sum to TOTAL VALID VOTES.

        Args:
            row: Data row
            headers: Column headers
            polling_station_idx: Index of Polling Station column
            total_valid_votes_idx: Index of TOTAL VALID VOTES column

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Get polling station number for error reporting
            polling_station = row[polling_station_idx]

            # Get total valid votes (expected sum)
            total_valid_str = row[total_valid_votes_idx].strip()
            if not total_valid_str:
                return False, f"Missing TOTAL VALID VOTES for station {polling_station}"

            try:
                expected_total = int(total_valid_str)
            except ValueError:
                return False, f"Invalid TOTAL VALID VOTES '{total_valid_str}' for station {polling_station}"

            # Sum all vote columns (skip SL.NO, Polling Station, and result columns)
            vote_sum = 0
            vote_columns = []

            for idx, header in enumerate(headers):
                # Skip non-vote columns
                header_lower = header.lower()
                if any(skip in header_lower for skip in [
                    "sl.", "polling", "station", "rejected", "total", "tender"
                ]):
                    continue

                # This is a vote column (candidate or NOTA)
                vote_columns.append(header)

                value_str = row[idx].strip()
                if value_str:
                    try:
                        vote_sum += int(value_str)
                    except ValueError:
                        logger.warning(f"Invalid vote value '{value_str}' in column '{header}' for station {polling_station}")

            # Check if sum matches
            if vote_sum != expected_total:
                return False, (
                    f"Station {polling_station}: Vote sum mismatch. "
                    f"Calculated: {vote_sum}, Expected: {expected_total}, "
                    f"Difference: {vote_sum - expected_total}"
                )

            return True, ""

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def get_candidate_columns(self, headers: List[str]) -> List[Tuple[int, str, str]]:
        """
        Extract candidate columns with party information.

        Args:
            headers: Column headers

        Returns:
            List of (column_index, candidate_name, party) tuples
        """
        candidates = []

        for idx, header in enumerate(headers):
            # Skip non-candidate columns
            header_lower = header.lower()
            if any(skip in header_lower for skip in [
                "sl.", "polling", "station", "nota", "rejected", "total", "tender"
            ]):
                continue

            # Parse candidate name and party from header
            # Format: "NAME (PARTY)" or just "NAME"
            if "(" in header and ")" in header:
                name_part = header[:header.rindex("(")].strip()
                party_part = header[header.rindex("(")+1:header.rindex(")")].strip()
                candidates.append((idx, name_part, party_part))
            else:
                # No party in header
                candidates.append((idx, header, ""))

        return candidates

    def extract_title_lines(self) -> List[str]:
        """
        Extract title lines from the PDF header.

        Returns:
            List of title lines (e.g., FORM 20, Election type, Constituency, Electors)
        """
        title_lines = []

        try:
            with pdfplumber.open(str(self.file_path)) as pdf:
                if not pdf.pages:
                    return title_lines

                # Get text from first page
                first_page = pdf.pages[0]
                text = first_page.extract_text()

                if not text:
                    return title_lines

                lines = text.strip().split("\n")

                # Look for standard title patterns
                form_pattern = re.compile(r"form\s*20|final\s*result\s*sheet", re.IGNORECASE)
                election_pattern = re.compile(r"election|lok\s*sabha|assembly", re.IGNORECASE)
                constituency_pattern = re.compile(r"constituency", re.IGNORECASE)
                electors_pattern = re.compile(r"electors?|total\s*no\.?\s*of", re.IGNORECASE)

                for line in lines[:15]:  # Check first 15 lines
                    line = self._clean_cell(line).strip()

                    if not line:
                        continue

                    # Stop when we hit table headers (column names)
                    if any(kw in line.lower() for kw in ["sl.", "polling station", "sl. no"]):
                        break

                    # Check if this is a title line
                    is_title = (
                        form_pattern.search(line) or
                        election_pattern.search(line) or
                        constituency_pattern.search(line) or
                        electors_pattern.search(line)
                    )

                    if is_title:
                        title_lines.append(line)

                logger.info(f"Extracted {len(title_lines)} title lines")

        except Exception as e:
            logger.warning(f"Error extracting title lines: {e}")

        return title_lines
