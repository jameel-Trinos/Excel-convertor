"""Comprehensive party alias mappings for Tamil Nadu election data.

This module contains the complete mapping of party abbreviations to all known
variations, including OCR errors, reversed text, and name variations.
"""

from typing import Dict, Set, Optional

# Comprehensive party alias mapping
# Key: Standard abbreviation (e.g., "DMK")
# Value: Set of all known variations/aliases for that party
TN_PARTY_ALIASES: Dict[str, Set[str]] = {
    "DMK": {
        "DMK",
        "DRAVIDA MUNNETRA KAZHAGAM",
        "MUNNETRA DRAVIDA KAZHAGAM",
        "KAZHAGAM DRAVIDA MUNNETRA",
        "MAGAHZAK ARTENNEM ADIVARD",   # OCR noise example
    },

    "AIADMK": {
        "AIADMK",
        "ALL INDIA ANNA DRAVIDA MUNNETRA KAZHAGAM",
        "ANNA DRAVIDA MUNNETRA KAZHAGAM",
        "ALL INDIA ANNA DRAVIDA KAZHAGAM",
        "ARTENNUM ANNA MAGAHZAK AIDNI ADIVARD LLA",  # OCR broken
        "MAGAHZAK ARTENNEM ANNA AIDNI ADIVARD",
    },

    "BJP": {
        "BJP",
        "BHARATIYA JANATA PARTY",
        "BHARATIHA JANATA PARTY",
        "JANATA BHARATIYA PARTY",
        "YTRAP ATANAJ AHITARAHB",  # reversed OCR
    },

    "INC": {
        "INC",
        "CONGRESS",
        "INDIAN NATIONAL CONGRESS",
        "NATIONAL CONGRESS",
        "SSERGNOC LANOITAN NAIDNI",  # reversed OCR
    },

    "PMK": {
        "PMK",
        "PATTALI MAKKAL KATCHI",
        "MAKKAL PATTALI KATCHI",
        "IHCTAK LAKKAM ILATTAP",  # reversed OCR
    },

    "VCK": {
        "VCK",
        "VIDUTHALAI CHIRUTHAIGAL KATCHI",
        "KATCHI VIDUTHALAI CHIRUTHAIGAL",
        "IHCTAK LAGIATHUR IALATHUDIV",  # reversed OCR
    },

    "NTK": {
        "NTK",
        "NAAM TAMIZHAR KATCHI",
        "NAAM TAMILAR KATCHI",
        "IHCTAK RAHZIMAT MAAN",  # reversed OCR
    },

    "DMDK": {
        "DMDK",
        "DESIYA MURPOKKU DRAVIDA KAZHAGAM",
        "MURPOKKU DRAVIDA KAZHAGAM",
    },

    "MDMK": {
        "MDMK",
        "MARUMALARCHI DRAVIDA MUNNETRA KAZHAGAM",
        "MARUMALARCHI DRAVIDA KAZHAGAM",
    },

    "AMMK": {
        "AMMK",
        "AMMA MAKKAL MUNNETRA KAZHAGAM",
        "AMMA MAKKAL KAZHAGAM",
    },

    "TMC(M)": {
        "TMC",
        "TMC(M)",
        "TAMIL MAANILA CONGRESS",
        "TAMIL MANILA CONGRESS",
        "TAMIL MAANILA CONGRESS MOOPANAR",
    },

    "CPI": {
        "CPI",
        "COMMUNIST PARTY OF INDIA",
    },

    "CPI(M)": {
        "CPI(M)",
        "COMMUNIST PARTY OF INDIA (MARXIST)",
        "COMMUNIST PARTY OF INDIA MARXIST",
    },

    "IUML": {
        "IUML",
        "INDIAN UNION MUSLIM LEAGUE",
        "MUSLIM LEAGUE",
    },

    "AIFB": {
        "AIFB",
        "ALL INDIA FORWARD BLOC",
        "FORWARD BLOC",
    },

    "RPI(A)": {
        "RPI(A)",
        "REPUBLICAN PARTY OF INDIA",
        "REPUBLICAN PARTY OF INDIA ATHAWALE",
    },

    "BSP": {
        "BSP",
        "BAHUJAN SAMAJ PARTY",
        "BAHUJAN PARTY SAMAJ",  # OCR swapped
    },

    "MNM": {
        "MNM",
        "MAKKAL NEEDHI MAIAM",
        "MAKKAL NEEDHI MAYAM",
    },

    "IJK": {
        "IJK",
        "INDIA JANANAYAKA KATCHI",
        "JANANAYAKA KATCHI",
    },

    "KMDK": {
        "KMDK",
        "KONGUNADU MAKKAL DESIA KATCHI",
        "KONGU MAKKAL KATCHI",
    },

    "MMK": {
        "MMK",
        "MANITHANEYA MAKKAL KATCHI",
    },

    "SDPI": {
        "SDPI",
        "SOCIAL DEMOCRATIC PARTY OF INDIA",
    },

    "PT": {
        "PT",
        "PUTHIYA TAMILAGAM",
        "PUTHIYA TAMILAGAM PARTY",
    },

    "AIMIM": {
        "AIMIM",
        "ALL INDIA MAJLIS E ITTEHADUL MUSLIMEEN",
        "MAJLIS ITTEHADUL MUSLIMEEN",
    },

    "TMK": {
        "TMK",
        "TAMILAGA MAKKAL KATCHI",
    },

    "IND": {
        "IND",
        "INDEPENDENT",
        "RALIMAT IHCTAK MAAN",  # OCR noise
    },

    "NOTA": {
        "NOTA",
        "NONE OF THE ABOVE",
        "evobA ehT fO enoN",  # reversed OCR
    },
}


def get_party_abbreviation(alias: str) -> Optional[str]:
    """
    Get the standard party abbreviation for a given alias.
    
    Args:
        alias: Party name variation/alias to look up
        
    Returns:
        Standard abbreviation (e.g., "DMK", "AIADMK") or None if not found
    """
    if not alias:
        return None
    
    alias_upper = alias.upper().strip()
    
    # Direct lookup (case-insensitive)
    for abbrev, aliases in TN_PARTY_ALIASES.items():
        if alias_upper in aliases:
            return abbrev
    
    # Normalized lookup (remove spaces, dots, etc.)
    normalized_alias = _normalize_for_matching(alias_upper)
    for abbrev, aliases in TN_PARTY_ALIASES.items():
        normalized_aliases = {_normalize_for_matching(a) for a in aliases}
        if normalized_alias in normalized_aliases:
            return abbrev
    
    # Check if alias contains any known party alias
    for abbrev, aliases in TN_PARTY_ALIASES.items():
        for known_alias in aliases:
            if known_alias in alias_upper or alias_upper in known_alias:
                # Additional check: ensure significant overlap
                if len(known_alias) >= 5 and len(alias_upper) >= 5:
                    return abbrev
    
    return None


def get_standardized_party_name(alias: str) -> Optional[str]:
    """
    Get the standardized party column name for a given alias.
    
    Standardized format: "{ABBREVIATION} Votes" (e.g., "DMK Votes", "AIADMK Votes")
    Special cases: "Independent" for IND, "NOTA" for NOTA
    
    Args:
        alias: Party name variation/alias to look up
        
    Returns:
        Standardized party name (e.g., "DMK Votes") or None if not found
    """
    abbrev = get_party_abbreviation(alias)
    
    if not abbrev:
        return None
    
    # Special handling for Independent and NOTA
    if abbrev == "IND":
        return "Independent"
    if abbrev == "NOTA":
        return "NOTA"
    
    # Standard format: "{ABBREVIATION} Votes"
    return f"{abbrev} Votes"


def get_all_aliases(abbreviation: str) -> Set[str]:
    """
    Get all known aliases for a given party abbreviation.
    
    Args:
        abbreviation: Party abbreviation (e.g., "DMK", "AIADMK")
        
    Returns:
        Set of all known aliases for that party, or empty set if not found
    """
    return TN_PARTY_ALIASES.get(abbreviation.upper(), set())


def is_party_alias(text: str) -> bool:
    """
    Check if a given text matches any known party alias.
    
    Args:
        text: Text to check
        
    Returns:
        True if text matches any known party alias, False otherwise
    """
    return get_party_abbreviation(text) is not None


def _normalize_for_matching(text: str) -> str:
    """
    Normalize text for matching (remove spaces, dots, hyphens, etc.).
    
    Args:
        text: Text to normalize
        
    Returns:
        Normalized text
    """
    import re
    normalized = text.upper()
    normalized = re.sub(r'[\s.\-_()]+', '', normalized)
    return normalized


def get_all_party_abbreviations() -> Set[str]:
    """
    Get all known party abbreviations.
    
    Returns:
        Set of all party abbreviations
    """
    return set(TN_PARTY_ALIASES.keys())


def get_party_abbreviation_to_standard_name() -> Dict[str, str]:
    """
    Get mapping from abbreviation to standardized name.
    
    Returns:
        Dict mapping abbreviation to standardized name (e.g., {"DMK": "DMK Votes"})
    """
    mapping = {}
    for abbrev in TN_PARTY_ALIASES.keys():
        if abbrev == "IND":
            mapping[abbrev] = "Independent"
        elif abbrev == "NOTA":
            mapping[abbrev] = "NOTA"
        else:
            mapping[abbrev] = f"{abbrev} Votes"
    return mapping

