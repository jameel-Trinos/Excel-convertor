"""Party name normalization for Tamil Nadu election data."""

import logging
import re
from typing import Dict, List, Optional

from .party_name_fixer import PartyNameFixer

logger = logging.getLogger(__name__)


class PartyNormalizer:
    """
    Normalize political party names into standardized column names.

    Specifically designed for Tamil Nadu election data to ensure consistent
    party vote column naming across different PDFs and formats.
    """

    # Party name mappings: key = standardized name, value = list of variations
    # Order defines standard output column order
    PARTY_MAPPINGS = {
        "BJP Votes": [
            "Bharatiya Janata Party",
            "BHARATIYA JANATA PARTY",
            "BJP",
            "B.J.P.",
            "B J P",
            "Bharatiya Janata Party Votes",
            "BJP Votes",
            # Word-order reversals
            "JANATA BHARATIYA PARTY",
            "PARTY JANATA BHARATIYA",
            "BHARATIYA PARTY JANATA",
        ],
        "AIADMK Votes": [
            "All India Dravida Munnetra Kazhagam",
            "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",  # Without ANNA (canonical)
            "All India Anna Dravida Munnetra Kazhagam",  # With ANNA (variant)
            "ALL INDIA ANNA DRAVIDA MUNNETRA KAZHAGAM",  # With ANNA (variant)
            "AIADMK",
            "A.I.A.D.M.K.",
            "A I A D M K",
            "All India Dravida Munnetra Kazhagam Votes",
            "AIADMK Votes",
            "Anna DMK",
            # Character-level reversals
            "ARTENNUM ANNA MAGAHZAK AIDNI ADIVARD LLA",
            "LLA ADIVARD AIDNI MAGAHZAK ANNA ARTENNUM",
            "MAGAHZAK ARTENNUM ANNA ADIVARD AIDNI LLA",
            # Word-order reversals (map to without ANNA)
            "MUNNETRA ANNA KAZHAGAM INDIA DRAVIDA ALL",
            "MUNNETRA KAZHAGAM INDIA DRAVIDA ALL",
            "ANNA DRAVIDA MUNNETRA KAZHAGAM INDIA ALL",
            "DRAVIDA MUNNETRA KAZHAGAM ANNA INDIA ALL",
            "DRAVIDA MUNNETRA KAZHAGAM INDIA ALL",
        ],
        "DMK Votes": [
            "Dravida Munnetra Kazhagam",
            "DRAVIDA MUNNETRA KAZHAGAM",
            "DMK",
            "D.M.K.",
            "D M K",
            "Dravida Munnetra Kazhagam Votes",
            "DMK Votes",
            # Character-level reversals
            "ARTENNUM MAGAHZAK ADIVARD",
            "MAGAHZAK ARTENNUM ADIVARD",
            "ADIVARD ARTENNUM MAGAHZAK",
            # Word-order reversals
            "MUNNETRA KAZHAGAM DRAVIDA",
            "KAZHAGAM MUNNETRA DRAVIDA",
            "DRAVIDA KAZHAGAM MUNNETRA",
        ],
        "Congress Votes": [
            "Indian National Congress",
            "INDIAN NATIONAL CONGRESS",
            "Congress",
            "INC",
            "I.N.C.",
            "Indian National Congress Votes",
            "Congress Votes",
            "Congress (I)",
            # Word-order reversals
            "NATIONAL INDIAN CONGRESS",
            "CONGRESS NATIONAL INDIAN",
            "INDIAN CONGRESS NATIONAL",
        ],
        "VCK Votes": [
            "Viduthalai Chiruthaigal Katchi",
            "VIDUTHALAI CHIRUTHAIGAL KATCHI",
            "VCK",
            "V.C.K.",
            "V C K",
            "Viduthalai Chiruthaigal Katchi Votes",
            "VCK Votes",
            # Word-order reversals
            "KATCHI VIDUTHALAI CHIRUTHAIGAL",
            "CHIRUTHAIGAL VIDUTHALAI KATCHI",
            "KATCHI CHIRUTHAIGAL VIDUTHALAI",
        ],
        "PMK Votes": [
            "Pattali Makkal Katchi",
            "PATTALI MAKKAL KATCHI",
            "PMK",
            "P.M.K.",
            "P M K",
            "Pattali Makkal Katchi Votes",
            "PMK Votes",
            # Character-level reversals
            "IHCTAK LAKKAM ILATTAP",
            "ILATTAP LAKKAM IHCTAK",
            # Word-order reversals
            "MAKKAL PATTALI KATCHI",
            "PATTALI KATCHI MAKKAL",
            "KATCHI PATTALI MAKKAL",
        ],
        "NTK Votes": [
            "Naam Tamizhar Katchi",
            "NAAM TAMIZHAR KATCHI",
            "NAAM TAMILAR KATCHI",  # Common variant
            "NTK",
            "N.T.K.",
            "N T K",
            "Naam Tamizhar Katchi Votes",
            "NTK Votes",
            # Character-level reversals
            "IHCTAK RALIMAT MAAN",
            "MAAN RALIMAT IHCTAK",
            "HCTAK RALIMAT MAAN",
            # Word-order reversals
            "TAMIZHAR KATCHI NAAM",
            "TAMILAR KATCHI NAAM",
            "KATCHI TAMIZHAR NAAM",
            "KATCHI TAMILAR NAAM",
            "NAAM KATCHI TAMIZHAR",
            "NAAM KATCHI TAMILAR",
        ],
        "BSP Votes": [
            "Bahujan Samaj Party",
            "BAHUJAN SAMAJ PARTY",
            "BSP",
            "B.S.P.",
            "B S P",
            "Bahujan Samaj Party Votes",
            "BSP Votes",
            # Character-level reversals
            "YTRAP NAJAS UJAHAB",
            # Word-order reversals
            "PARTY BAHUJAN SAMAJ",
            "SAMAJ PARTY BAHUJAN",
            "SAMAJ BAHUJAN PARTY",
            "PARTY SAMAJ BAHUJAN",
        ],
        "NMK Votes": [
            "Namma Makkal Katchi",
            "NMK",
            "N.M.K.",
            "N M K",
            "Namma Makkal Katchi Votes",
            "NMK Votes",
        ],
        "MDMK Votes": [
            "Marumalarchi Dravida Munnetra Kazhagam",
            "MDMK",
            "M.D.M.K.",
            "M D M K",
            "MDMK Votes",
        ],
        "CPI Votes": [
            "Communist Party of India",
            "CPI",
            "C.P.I.",
            "C P I",
            "CPI Votes",
        ],
        "CPM Votes": [
            "Communist Party of India (Marxist)",
            "CPM",
            "CPI(M)",
            "CPIM",
            "C.P.M.",
            "C P M",
            "CPM Votes",
        ],
        "Independent": [
            "Independent",
            "IND",
            "I.N.D.",
            "Independent Votes",
            "Ind",
            # Reversed variations
            "TNEDNEPEDNI",
        ],
        "NOTA": [
            "NOTA",
            "None of the Above",
            "NOTA Votes",
            # Reversed variations
            "ATON",
        ],
        "Other Votes": [
            "Others",
            "Other",
            "Other Votes",
        ],
        "MNK Votes": [
            "Makkal Naadaalum Katchi",
            "MAKKAL NAADAALUM KATCHI",
            "MNK",
            "M.N.K.",
            "M N K",
            "Makkal Naadaalum Katchi Votes",
            "MNK Votes",
            # Word-order reversals
            "KATCHI NAADAALUM MAKKAL",
            "NAADAALUM MAKKAL KATCHI",
            "KATCHI MAKKAL NAADAALUM",
            "NAADAALUM KATCHI MAKKAL",
        ],
    }

    def __init__(self):
        """Initialize the party normalizer with reverse lookup mapping."""
        # Create reverse mapping: variation -> standardized name
        self._reverse_mapping: Dict[str, str] = {}

        for standard_name, variations in self.PARTY_MAPPINGS.items():
            for variation in variations:
                # Store both exact match and normalized (lowercase, no spaces/dots)
                self._reverse_mapping[variation] = standard_name
                normalized = self._normalize_for_comparison(variation)
                self._reverse_mapping[normalized] = standard_name

        # Add abbreviation mappings (user requested format)
        self.ABBREVIATION_MAPPINGS = {
            "DMK": "DMK Votes",
            "AIADMK": "AIADMK Votes",
            "BJP": "BJP Votes",
            "VCK": "VCK Votes",
            "PMK": "PMK Votes",
            "NTK": "NTK Votes",
            "BSP": "BSP Votes",
            "CONGRESS": "Congress Votes",
            "IND": "Independent",
            "INDEPENDENT": "Independent",
        }
        
        # Add abbreviations to reverse mapping
        for abbrev, standard_name in self.ABBREVIATION_MAPPINGS.items():
            self._reverse_mapping[abbrev] = standard_name
            self._reverse_mapping[abbrev.upper()] = standard_name
            self._reverse_mapping[abbrev.lower()] = standard_name

        logger.info(f"Party normalizer initialized with {len(self.PARTY_MAPPINGS)} party mappings")

    def _normalize_for_comparison(self, text: str) -> str:
        """
        Normalize text for fuzzy comparison.

        Removes dots, spaces, and converts to lowercase for matching.
        """
        # Remove dots and spaces, convert to lowercase
        normalized = text.lower()
        normalized = normalized.replace(".", "")
        normalized = normalized.replace(" ", "")
        normalized = normalized.replace("-", "")
        return normalized

    def normalize_column_name(self, column_name: str) -> Optional[str]:
        """
        Normalize a single column name to standardized party name.

        Now handles reversed text by fixing it first using PartyNameFixer.

        Args:
            column_name: Original column name from PDF

        Returns:
            Standardized party name (e.g., "DMK Votes") or None if not a party column
        """
        if not column_name or not isinstance(column_name, str):
            return None

        column_name = column_name.strip()
        
        # First, try to fix reversed text (especially for party names)
        if PartyNameFixer.is_likely_party_name(column_name):
            fixed_column = PartyNameFixer.fix_reversed_party_name(column_name)
            if fixed_column != column_name:
                logger.debug(f"Fixed reversed party name before normalization: '{column_name}' -> '{fixed_column}'")
                column_name = fixed_column

        # Exact match first
        if column_name in self._reverse_mapping:
            return self._reverse_mapping[column_name]

        # Try normalized match
        normalized = self._normalize_for_comparison(column_name)
        if normalized in self._reverse_mapping:
            return self._reverse_mapping[normalized]

        # Check if column name contains party keywords (for partial matches)
        # This handles cases like "Total Votes - DMK" or "DMK (Votes)"
        for standard_name, variations in self.PARTY_MAPPINGS.items():
            for variation in variations:
                # Check if the variation appears in the column name
                variation_normalized = self._normalize_for_comparison(variation)
                if variation_normalized in normalized:
                    # Additional check: ensure it's likely a vote column
                    if any(keyword in normalized for keyword in ["vote", "votes", "total", "count"]):
                        logger.debug(f"Partial match: '{column_name}' -> '{standard_name}'")
                        return standard_name

        # Check for generic "other" or "independent" columns
        if any(keyword in normalized for keyword in ["independent", "nota", "other", "others"]):
            if any(keyword in normalized for keyword in ["vote", "votes", "total", "count"]):
                logger.debug(f"Generic match: '{column_name}' -> 'Other Votes'")
                return "Other Votes"

        return None

    def normalize_headers(self, headers: List[str]) -> List[str]:
        """
        Normalize a list of column headers.

        Args:
            headers: Original column headers from PDF

        Returns:
            List of normalized headers (party columns standardized, others unchanged)
        """
        normalized_headers = []

        for header in headers:
            standardized = self.normalize_column_name(header)
            if standardized:
                normalized_headers.append(standardized)
                logger.debug(f"Normalized '{header}' -> '{standardized}'")
            else:
                # Keep non-party columns unchanged
                normalized_headers.append(header)

        return normalized_headers

    def normalize_column_mapping(
        self,
        column_mapping: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """
        Apply party normalization to an existing column mapping from AI.

        This integrates with the AI column standardization process to ensure
        party names follow the Tamil Nadu election standards.

        Args:
            column_mapping: Column mapping from AI processor
                           Format: {"Standard Name": ["Variant1", "Variant2"]}

        Returns:
            Updated column mapping with party names normalized
        """
        normalized_mapping: Dict[str, List[str]] = {}

        for standard_name, variants in column_mapping.items():
            # Check if this column should be normalized to a party name
            party_name = self.normalize_column_name(standard_name)

            if party_name:
                # This is a party column - use standardized party name
                if party_name not in normalized_mapping:
                    normalized_mapping[party_name] = []

                # Add all variants to the standardized party name
                normalized_mapping[party_name].extend(variants)

                logger.info(f"Normalized party column: '{standard_name}' -> '{party_name}'")
            else:
                # Not a party column - keep as is
                normalized_mapping[standard_name] = variants

        # Deduplicate variants
        for key in normalized_mapping:
            normalized_mapping[key] = list(set(normalized_mapping[key]))

        return normalized_mapping

    def get_standardized_party_names(self) -> List[str]:
        """
        Get the list of all standardized party names.

        Returns:
            List of standardized party column names
        """
        return list(self.PARTY_MAPPINGS.keys())

    def is_party_column(self, column_name: str) -> bool:
        """
        Check if a column name represents a party vote column.

        Args:
            column_name: Column name to check

        Returns:
            True if this is a party vote column, False otherwise
        """
        return self.normalize_column_name(column_name) is not None

    def add_custom_mapping(self, party_name: str, variations: List[str]) -> None:
        """
        Add a custom party mapping (useful for regional parties or new parties).

        Args:
            party_name: Standardized party name (should end with " Votes")
            variations: List of name variations to map to this party
        """
        if party_name not in self.PARTY_MAPPINGS:
            self.PARTY_MAPPINGS[party_name] = []

        self.PARTY_MAPPINGS[party_name].extend(variations)

        # Update reverse mapping
        for variation in variations:
            self._reverse_mapping[variation] = party_name
            normalized = self._normalize_for_comparison(variation)
            self._reverse_mapping[normalized] = party_name

        logger.info(f"Added custom party mapping: {party_name} with {len(variations)} variations")
