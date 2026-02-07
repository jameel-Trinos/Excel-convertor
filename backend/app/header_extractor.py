"""
Deterministic header extraction for election PDF documents.

Extracts ONLY party names from PDF headers, ignoring candidate names.
Produces a fixed, ordered list of standardized party vote columns.
"""

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .party_aliases import (
    get_party_abbreviation,
    get_standardized_party_name,
    is_party_alias,
    get_party_abbreviation_to_standard_name,
)

logger = logging.getLogger(__name__)


class HeaderExtractor:
    """
    Extract party names from PDF election result headers.

    This class:
    - Reads ONLY the first page of the PDF
    - Extracts party abbreviations from header text
    - Maps to standardized party vote column names
    - Caches results for reuse

    The output is deterministic - same PDF always produces same headers.
    """

    # Standard party abbreviation to full name mapping
    # Built from comprehensive TN_PARTY_ALIASES
    # This is initialized from party_aliases module
    PARTY_ABBREVIATIONS: Dict[str, str] = {}

    # Columns to IGNORE completely (not party vote columns)
    IGNORE_COLUMNS = {
        "SL. NO",
        "SL.NO",
        "SLNO",
        "S.NO",
        "SNO",
        "SERIAL NUMBER",
        "POLLING STATION",
        "POLLING",
        "STATION",
        "NOTA",
        "TOTAL VALID VOTES",
        "TOTAL VOTES",
        "VALID VOTES",
        "NO OF REJECTED VOTES",
        "REJECTED VOTES",
        "NO.OF REJECTED VOTES",
        "TOTAL",
        "NO.OF TENDERED VOTES",
        "TENDERED VOTES",
        "NO OF TENDERED VOTES",
        "ROUND NUMBER",
        "ROUND",
    }

    # Standard output column order
    STANDARD_PARTY_ORDER = [
        "BJP Votes",
        "AIADMK Votes",
        "DMK Votes",
        "Congress Votes",
        "VCK Votes",
        "PMK Votes",
        "NTK Votes",
        "BSP Votes",
        "NMK Votes",
        "MDMK Votes",
        "CPI Votes",
        "CPM Votes",
        "Independent",
        "NOTA",  # Keep NOTA as a data column
    ]

    def __init__(self, file_path: str):
        """
        Initialize header extractor.

        Args:
            file_path: Path to the PDF file
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        # Initialize PARTY_ABBREVIATIONS from comprehensive alias mapping
        if not HeaderExtractor.PARTY_ABBREVIATIONS:
            HeaderExtractor.PARTY_ABBREVIATIONS = get_party_abbreviation_to_standard_name()
            # Add common aliases
            HeaderExtractor.PARTY_ABBREVIATIONS["CONGRESS"] = "Congress Votes"
            HeaderExtractor.PARTY_ABBREVIATIONS["INDEPENDENT"] = "Independent"
            HeaderExtractor.PARTY_ABBREVIATIONS["CPM"] = "CPM Votes"
            HeaderExtractor.PARTY_ABBREVIATIONS["CPIM"] = "CPM Votes"

        self._cached_headers: Optional[List[str]] = None
        self._cached_party_mapping: Optional[Dict[str, str]] = None

    def extract_party_headers(self) -> Tuple[List[str], Dict[str, str]]:
        """
        Extract party names from PDF headers.

        Returns:
            Tuple of:
            - List of standardized party column names in order found
            - Dict mapping original header text to standardized name
        """
        if self._cached_headers is not None:
            return self._cached_headers, self._cached_party_mapping

        import pdfplumber

        party_columns = []
        original_to_standard = {}
        seen_parties = set()
        independent_count = 0

        with pdfplumber.open(str(self.file_path)) as pdf:
            # Only read first page
            if not pdf.pages:
                logger.warning("PDF has no pages")
                return [], {}

            page = pdf.pages[0]

            # Extract table from first page to get headers
            tables = page.extract_tables()

            if not tables:
                # Try with explicit settings
                table_settings = {
                    "vertical_strategy": "lines_strict",
                    "horizontal_strategy": "lines_strict",
                }
                tables = page.extract_tables(table_settings)

            if not tables:
                logger.warning("No tables found on first page")
                return [], {}

            # Get first table's header rows (usually first 1-2 rows)
            first_table = tables[0]
            if not first_table or len(first_table) < 2:
                logger.warning("Table too small to have headers")
                return [], {}

            # Find the header row (row with party abbreviations in parentheses)
            header_row = None
            for row_idx, row in enumerate(first_table[:5]):  # Check first 5 rows
                # Count cells with party pattern (NAME (PARTY))
                party_pattern_count = sum(
                    1 for cell in row
                    if cell and re.search(r'\([A-Z]+\)', str(cell).upper())
                )
                if party_pattern_count >= 3:  # At least 3 party columns
                    header_row = row
                    logger.info(f"Found header row at index {row_idx}")
                    break

            if header_row is None:
                # Fall back to first row after title
                header_row = first_table[1] if len(first_table) > 1 else first_table[0]
                logger.info("Using fallback header row detection")

            # Process each header cell
            for cell in header_row:
                if not cell:
                    continue

                cell_text = self._clean_cell(str(cell))
                cell_upper = cell_text.upper()

                # Skip ignored columns
                if self._should_ignore_column(cell_upper):
                    continue

                # Extract party from parentheses: "CANDIDATE NAME (PARTY)"
                party_match = re.search(r'\(([A-Z]+)\)', cell_upper)

                if party_match:
                    party_abbr = party_match.group(1)
                    standard_name = self._get_standard_party_name(party_abbr)

                    if standard_name:
                        if standard_name == "Independent":
                            # Count independents but group them
                            independent_count += 1
                            original_to_standard[cell_text] = f"Independent_{independent_count}"
                        else:
                            if standard_name not in seen_parties:
                                party_columns.append(standard_name)
                                seen_parties.add(standard_name)
                            original_to_standard[cell_text] = standard_name
                else:
                    # Check if the cell itself is a party name (using comprehensive aliases)
                    # First try direct alias matching
                    standard_name = get_standardized_party_name(cell_text)
                    
                    if not standard_name:
                        # Fall back to abbreviation matching
                        normalized = self._normalize_text(cell_upper)
                        standard_name = self._get_standard_party_name(normalized)
                    
                    # Also check if cell contains party name (for cases like "DMK Votes" or full party name)
                    if not standard_name:
                        # Try matching against full cell text
                        standard_name = get_standardized_party_name(cell_upper)

                    if standard_name:
                        if standard_name == "Independent":
                            independent_count += 1
                            original_to_standard[cell_text] = f"Independent_{independent_count}"
                        else:
                            if standard_name not in seen_parties:
                                party_columns.append(standard_name)
                                seen_parties.add(standard_name)
                            original_to_standard[cell_text] = standard_name

        # Add Independent as single column at end if any independents found
        if independent_count > 0 and "Independent" not in party_columns:
            party_columns.append("Independent")

        # Cache results
        self._cached_headers = party_columns
        self._cached_party_mapping = original_to_standard

        logger.info(f"Extracted {len(party_columns)} party columns: {party_columns}")

        return party_columns, original_to_standard

    def get_standardized_headers(self) -> List[str]:
        """
        Get standardized party column headers for output.

        Returns:
            List of standardized column names in a fixed order
        """
        party_columns, _ = self.extract_party_headers()

        # Sort according to standard order
        ordered = []
        for std_name in self.STANDARD_PARTY_ORDER:
            if std_name in party_columns:
                ordered.append(std_name)

        # Add any remaining parties not in standard order
        for party in party_columns:
            if party not in ordered:
                ordered.append(party)

        return ordered

    def get_full_header_row(self, include_metadata: bool = True) -> List[str]:
        """
        Get full header row for Excel output.

        Args:
            include_metadata: Include SL.NO, Polling Station columns

        Returns:
            Complete header row for Excel
        """
        headers = []

        if include_metadata:
            headers.extend(["SL. NO.", "Polling Station"])

        headers.extend(self.get_standardized_headers())

        if include_metadata:
            headers.extend([
                "NOTA",
                "Total Valid Votes",
                "Rejected Votes",
                "Total",
                "Tendered Votes"
            ])

        return headers

    def _should_ignore_column(self, text: str) -> bool:
        """Check if column should be ignored."""
        normalized = self._normalize_text(text)

        for ignore_pattern in self.IGNORE_COLUMNS:
            if self._normalize_text(ignore_pattern) == normalized:
                return True
            if self._normalize_text(ignore_pattern) in normalized:
                return True

        return False

    def _get_standard_party_name(self, abbreviation: str) -> Optional[str]:
        """
        Map party abbreviation or alias to standard name.
        
        Uses comprehensive alias matching from party_aliases.py.

        Args:
            abbreviation: Party abbreviation or alias (e.g., "BJP", "AIADMK", "DRAVIDA MUNNETRA KAZHAGAM")

        Returns:
            Standard party name or None if not recognized
        """
        if not abbreviation:
            return None
            
        abbr_upper = abbreviation.upper().strip()

        # First try comprehensive alias matching
        standard_name = get_standardized_party_name(abbr_upper)
        if standard_name:
            return standard_name

        # Direct lookup in PARTY_ABBREVIATIONS
        if abbr_upper in self.PARTY_ABBREVIATIONS:
            return self.PARTY_ABBREVIATIONS[abbr_upper]

        # Try without dots/spaces
        normalized = self._normalize_text(abbr_upper)
        for key, value in self.PARTY_ABBREVIATIONS.items():
            if self._normalize_text(key) == normalized:
                return value

        return None

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        return re.sub(r'[\s.\-_]+', '', text.upper())

    def _clean_cell(self, value: str) -> str:
        """Clean cell value, including fixing reversed text."""
        if not value:
            return ""

        # Handle NaN
        if value.lower() in ("nan", "none", "null"):
            return ""

        # Use sanitize_text which handles RTL characters and reversed text detection
        # This is critical for fixing corrupted polling area data
        from .utils import sanitize_text
        text = sanitize_text(value, single_line=False)

        # Handle vertical text by checking for single spaced letters
        # e.g., "B J P" -> "BJP"
        if re.match(r'^([A-Z] )+[A-Z]$', text.upper()):
            text = text.replace(" ", "")

        return text.strip()


def extract_election_headers(pdf_path: str) -> Dict[str, any]:
    """
    Main function to extract election headers from PDF.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Dict with:
        - party_columns: List of standardized party column names
        - original_mapping: Mapping of original headers to standard names
        - full_headers: Complete header row for Excel output
    """
    extractor = HeaderExtractor(pdf_path)

    party_columns, original_mapping = extractor.extract_party_headers()

    return {
        "party_columns": party_columns,
        "original_mapping": original_mapping,
        "full_headers": extractor.get_full_header_row(),
        "standardized_headers": extractor.get_standardized_headers(),
    }


# Module-level cache for header extraction results
_header_cache: Dict[str, Dict] = {}


def get_cached_headers(pdf_path: str) -> Dict[str, any]:
    """
    Get headers with caching.

    Results are cached by file path to avoid re-extraction.
    """
    path_key = str(Path(pdf_path).resolve())

    if path_key not in _header_cache:
        _header_cache[path_key] = extract_election_headers(pdf_path)

    return _header_cache[path_key]


def clear_header_cache():
    """Clear the header cache."""
    _header_cache.clear()


def get_standardized_party_list(pdf_path: str, group_independents: bool = True) -> List[str]:
    """
    Get a fixed ordered list of standardized party columns.

    This is the EXPECTED OUTPUT FORMAT per requirements:
    [
      "BJP Votes",
      "AIADMK Votes",
      "DMK Votes",
      "Congress Votes",
      "VCK Votes",
      "PMK Votes",
      "NTK Votes",
      "Other Votes"
    ]

    Args:
        pdf_path: Path to PDF file
        group_independents: If True, all independents are grouped as "Other Votes"

    Returns:
        Fixed ordered list of standardized party column names
    """
    extractor = HeaderExtractor(pdf_path)
    party_columns, _ = extractor.extract_party_headers()

    # Standard party order (matching user's expected output)
    STANDARD_ORDER = [
        "BJP Votes",
        "AIADMK Votes",
        "DMK Votes",
        "Congress Votes",
        "VCK Votes",
        "PMK Votes",
        "NTK Votes",
        "BSP Votes",
        "NMK Votes",
        "MDMK Votes",
        "CPI Votes",
        "CPM Votes",
    ]

    result = []

    # Add parties in standard order
    for party in STANDARD_ORDER:
        if party in party_columns:
            result.append(party)

    # Handle independents
    if group_independents:
        # Group all independents as "Other Votes"
        has_independents = any(
            col.startswith("IND_") or col == "Independent"
            for col in party_columns
        )
        if has_independents:
            result.append("Other Votes")
    else:
        # Keep individual independent columns
        for col in party_columns:
            if col.startswith("IND_") or col == "Independent":
                result.append(col)

    # Add any remaining parties not in standard order
    for party in party_columns:
        if party not in result and not party.startswith("IND_") and party != "Independent":
            result.append(party)

    return result


def get_column_mapping_for_excel(pdf_path: str) -> Dict[str, List[str]]:
    """
    Get column mapping for Excel output.

    Maps original header names to standardized names, with independents
    grouped together as "Other Votes".

    Returns:
        Dict mapping standardized name to list of original names
    """
    extractor = HeaderExtractor(pdf_path)
    _, original_mapping = extractor.extract_party_headers()

    # Reverse the mapping: standardized -> [originals]
    result = {}

    for original, standard in original_mapping.items():
        # Group independents
        if standard.startswith("IND_"):
            standard = "Other Votes"

        if standard not in result:
            result[standard] = []
        result[standard].append(original)

    return result
