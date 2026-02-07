"""Party name normalization for Tamil Nadu election data."""

import logging
import re
from typing import Dict, List, Optional

from .party_aliases import (
    TN_PARTY_ALIASES,
    get_party_abbreviation,
    get_standardized_party_name,
    get_all_aliases,
    is_party_alias,
)
from .party_name_fixer import PartyNameFixer

logger = logging.getLogger(__name__)


class PartyNormalizer:
    """
    Normalize political party names into standardized column names.

    Specifically designed for Tamil Nadu election data to ensure consistent
    party vote column naming across different PDFs and formats.
    """

    # Party name mappings: key = standardized name, value = list of variations
    # Built from comprehensive TN_PARTY_ALIASES mapping
    # Order defines standard output column order
    PARTY_MAPPINGS: Dict[str, List[str]] = {}

    def __init__(self):
        """Initialize the party normalizer with reverse lookup mapping."""
        # Build PARTY_MAPPINGS from comprehensive TN_PARTY_ALIASES
        self._build_party_mappings_from_aliases()
        
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
            "INC": "Congress Votes",
            "IND": "Independent",
            "INDEPENDENT": "Independent",
            "NOTA": "NOTA",
        }
        
        # Add all parties from TN_PARTY_ALIASES to abbreviation mappings
        for abbrev in TN_PARTY_ALIASES.keys():
            if abbrev not in self.ABBREVIATION_MAPPINGS:
                if abbrev == "IND":
                    self.ABBREVIATION_MAPPINGS[abbrev] = "Independent"
                elif abbrev == "NOTA":
                    self.ABBREVIATION_MAPPINGS[abbrev] = "NOTA"
                elif abbrev == "INC":
                    self.ABBREVIATION_MAPPINGS[abbrev] = "Congress Votes"
                else:
                    self.ABBREVIATION_MAPPINGS[abbrev] = f"{abbrev} Votes"
        
        # Add abbreviations to reverse mapping
        for abbrev, standard_name in self.ABBREVIATION_MAPPINGS.items():
            self._reverse_mapping[abbrev] = standard_name
            self._reverse_mapping[abbrev.upper()] = standard_name
            self._reverse_mapping[abbrev.lower()] = standard_name

        logger.info(f"Party normalizer initialized with {len(self.PARTY_MAPPINGS)} party mappings")

    def _build_party_mappings_from_aliases(self):
        """Build PARTY_MAPPINGS from comprehensive TN_PARTY_ALIASES."""
        # Standard order for output (major parties first)
        standard_order = [
            "BJP", "AIADMK", "DMK", "INC", "PMK", "VCK", "NTK", "DMDK",
            "MDMK", "AMMK", "TMC(M)", "CPI", "CPI(M)", "IUML", "AIFB",
            "RPI(A)", "BSP", "MNM", "IJK", "KMDK", "MMK", "SDPI", "PT",
            "AIMIM", "TMK", "IND", "NOTA"
        ]
        
        # Build mappings in standard order
        for abbrev in standard_order:
            if abbrev not in TN_PARTY_ALIASES:
                continue
            
            # Get standardized name
            if abbrev == "IND":
                standard_name = "Independent"
            elif abbrev == "NOTA":
                standard_name = "NOTA"
            elif abbrev == "INC":
                standard_name = "Congress Votes"
            else:
                standard_name = f"{abbrev} Votes"
            
            # Get all aliases for this party
            aliases = get_all_aliases(abbrev)
            
            # Convert set to list and add to PARTY_MAPPINGS
            self.PARTY_MAPPINGS[standard_name] = list(aliases)
            
            # Also add common variations with dots/spaces (only for simple abbreviations)
            if len(abbrev) <= 5 and not any(c in abbrev for c in "()"):
                abbrev_variations = [
                    abbrev,
                    ".".join(abbrev),  # D.M.K.
                    " ".join(abbrev),  # D M K
                ]
                for var in abbrev_variations:
                    if var not in self.PARTY_MAPPINGS[standard_name]:
                        self.PARTY_MAPPINGS[standard_name].append(var)
        
        # Add "Other Votes" for non-party columns
        self.PARTY_MAPPINGS["Other Votes"] = ["Others", "Other", "Other Votes"]

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
        Uses comprehensive alias mapping from party_aliases.py.

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

        # Try comprehensive alias matching first (from party_aliases.py)
        standardized_name = get_standardized_party_name(column_name)
        if standardized_name:
            logger.debug(f"Matched via comprehensive aliases: '{column_name}' -> '{standardized_name}'")
            return standardized_name

        # Exact match in reverse mapping
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
