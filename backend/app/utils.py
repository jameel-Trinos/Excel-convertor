"""Utility functions for the PDF to Excel Converter backend."""

import os
from pathlib import Path
from typing import Optional

import aiofiles


def validate_pdf_file(content: bytes) -> Optional[str]:
    """
    Validate that the content is a valid PDF file.

    Args:
        content: File content as bytes

    Returns:
        Error message if validation fails, None if valid
    """
    # Check PDF magic bytes
    if not content.startswith(b"%PDF"):
        return "Invalid PDF file: File does not start with PDF header"

    # Check for PDF end marker (should contain %%EOF)
    # Some PDFs have data after %%EOF so we check for its presence
    if b"%%EOF" not in content[-1024:]:
        # Check a larger window
        if b"%%EOF" not in content:
            return "Invalid PDF file: Missing PDF end marker"

    # Basic sanity check on size
    if len(content) < 100:
        return "Invalid PDF file: File too small to be a valid PDF"

    return None


async def cleanup_file(file_path: Path) -> bool:
    """
    Safely delete a file.

    Args:
        file_path: Path to the file to delete

    Returns:
        True if file was deleted, False otherwise
    """
    try:
        if file_path.exists():
            os.remove(file_path)
            return True
    except Exception:
        pass
    return False


async def save_file(content: bytes, file_path: Path) -> bool:
    """
    Save content to a file asynchronously.

    Args:
        content: File content as bytes
        file_path: Path where to save the file

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        return True
    except Exception:
        return False


def get_file_size_str(size_bytes: int) -> str:
    """
    Convert file size in bytes to human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string (e.g., "1.5 MB")
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to remove potentially dangerous characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Remove path separators and null bytes
    filename = filename.replace("/", "_").replace("\\", "_").replace("\x00", "")

    # Remove other potentially dangerous characters
    dangerous_chars = '<>:"|?*'
    for char in dangerous_chars:
        filename = filename.replace(char, "_")

    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[: 255 - len(ext)] + ext

    return filename


def is_numeric_string(value: str) -> bool:
    """
    Check if a string represents a numeric value.

    Args:
        value: String to check

    Returns:
        True if the string is numeric
    """
    if not value:
        return False

    # Remove common numeric formatting
    cleaned = value.replace(",", "").replace(" ", "").strip()

    # Check for negative sign
    if cleaned.startswith("-"):
        cleaned = cleaned[1:]

    # Check for decimal point (only one allowed)
    parts = cleaned.split(".")
    if len(parts) > 2:
        return False

    # All parts should be digits
    return all(part.isdigit() for part in parts if part)


def parse_numeric_string(value: str) -> Optional[float]:
    """
    Parse a string to a numeric value.

    Args:
        value: String to parse

    Returns:
        Numeric value or None if parsing fails
    """
    if not value:
        return None

    try:
        # Remove common formatting
        cleaned = value.replace(",", "").replace(" ", "").strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def sanitize_text(value: Optional[str], single_line: bool = True) -> str:
    """
    Sanitize text by removing RTL/bidirectional control characters and fixing reversed text.

    This function removes Unicode bidirectional control characters that can cause
    text to appear mirrored or reversed in displays and Excel files.

    Args:
        value: Text to sanitize
        single_line: If True, replace newlines with spaces (default True for cleaner headers)

    Returns:
        Sanitized text with RTL characters removed and reversed text fixed
    """
    if value is None:
        return ""

    text = str(value)

    # Handle NaN values
    if text.lower() in ("nan", "none", "null", "undefined"):
        return ""

    # Check for RTL override character BEFORE removing it - if present, text needs reversal
    has_rlo = "\u202E" in text
    
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
        "\ufeff",  # Byte Order Mark (BOM)
    ]
    for char in bidi_chars:
        text = text.replace(char, "")

    # Remove null bytes and other control characters (keep newlines and tabs initially)
    text = text.replace("\x00", "")
    text = "".join(char for char in text if ord(char) >= 32 or char in "\n\t")

    # Handle newlines
    if single_line:
        # Replace newlines with spaces for cleaner single-line text
        text = text.replace("\n", " ").replace("\r", " ")
        # Normalize whitespace
        text = " ".join(text.split())

    # Clean up common OCR artifacts
    text = text.replace("�", "")  # Replacement character
    
    text = text.strip()
    
    # If RTL override was present, the text is likely reversed - fix it
    if has_rlo and text:
        text = text[::-1]
    # Also check for common reversed patterns even without RTL marker
    elif text and _is_likely_reversed(text):
        text = text[::-1]

    return text


def _score_text_naturalness(text: str) -> float:
    """
    Score text based on English bigram frequency.
    Returns: Higher score = more likely correct (not reversed).

    Uses common English bigrams (TH, HE, IN, ER) and impossible
    word-start patterns (JK, MJ, NK, etc.) to score naturalness.
    """
    COMMON_BIGRAMS = [
        'TH', 'HE', 'IN', 'ER', 'AN', 'RE', 'ON', 'AT', 'EN', 'ND',
        'TI', 'ES', 'OR', 'TE', 'ED', 'IS', 'IT', 'AL', 'AR', 'ST',
        'HA', 'AS', 'NG', 'SE', 'OU', 'IO', 'LE', 'NT', 'TO', 'RA'
    ]

    IMPOSSIBLE_STARTS = [
        'JK', 'MJ', 'DJ', 'NK', 'NL', 'TN', 'HL', 'HR', 'KM',
        'LT', 'MN', 'RK', 'TL', 'VL'
    ]

    # Normalize: remove punctuation, uppercase
    clean_text = ''.join(c for c in text if c.isalpha()).upper()
    if len(clean_text) < 3:
        return 0

    # Extract bigrams
    bigrams = [clean_text[i:i+2] for i in range(len(clean_text)-1)]

    # Score
    common_count = sum(1 for bg in bigrams if bg in COMMON_BIGRAMS)
    impossible_count = sum(1 for imp in IMPOSSIBLE_STARTS if clean_text.startswith(imp))

    return common_count - (impossible_count * 5)


def _has_impossible_consonant_clusters(text: str) -> bool:
    """Check for 4+ consecutive consonants (rare in English)."""
    CONSONANTS = 'BCDFGHJKLMNPQRSTVWXYZ'
    clean_text = ''.join(c for c in text if c.isalpha()).upper()

    cluster_length = 0
    for char in clean_text:
        if char in CONSONANTS:
            cluster_length += 1
            if cluster_length >= 4:
                return True
        else:
            cluster_length = 0
    return False


def _is_likely_reversed(text: str) -> bool:
    """
    Check if text appears to be reversed based on common patterns.
    
    Args:
        text: Text to check
        
    Returns:
        True if text appears reversed
    """
    if not text or len(text) < 3:
        return False
    
    text_stripped = text.strip()
    
    # Known reversed patterns (what reversed text looks like)
    reversed_patterns = [
        ".ON .LS",           # SL. NO.
        ".oN .lS",           # Sl. No.
        ".ON",               # NO.
        ".oN",               # No.
        "oN noitatS",        # Station No
        "noitatS gnilloP",   # Polling Station
        "gnilloP",           # Polling
        "ATON",              # NOTA
        "LATOT",             # TOTAL
        "latoT",             # Total
        "setov",             # votes
        "setoV",             # Votes
        "detcejeR",          # Rejected
        "deredneT",          # Tendered
        "ruovaf ni tsac",    # cast in favour
        "dilaV fo",          # of Valid
        "YTRAP",             # PARTY
        "ytraP",             # Party
        "NOITAIVERBA",       # ABBREVIATION
        "noitaivverbbA",     # Abbreviation
        "etadidnaC",         # Candidate
        "ETADIDNAC",         # CANDIDATE
        "rebmuN",            # Number
        "REBMUN",            # NUMBER
        "laredeF",           # Federal
        "snoitcelE",         # Elections
        "SNOITCELE",         # ELECTIONS
        "latoT dilaV",       # Valid Total
        "dilaV latoT",       # Total Valid
        "YTRAP BAJD",        # DMKP PARTY (example)
        # Indian political party abbreviations (reversed)
        "KMD",               # DMK
        "KMDMAIA",           # AIADMK
        "JKMDJAIA",          # AIMDJMK
        "PJB",               # BJP
        "KCV",               # VCK
        "KMP",               # PMK
        "KTN",               # NTK
        "PSB",               # BSP
        "KMDMD",             # MDMK
        "IPC",               # CPI
        "MPC",               # CPM
        # Common Tamil name patterns (reversed)
        "NAR",               # RAN (common ending)
        "MAR",               # RAM
        "NAS",               # SAN
    ]
    
    for pattern in reversed_patterns:
        if pattern in text_stripped:
            return True
    
    # Check if starts with punctuation (often indicates reversed text)
    if text_stripped and text_stripped[0] in ".,;:" and len(text_stripped) > 1:
        # Check if reversing makes it start with a letter
        reversed_text = text_stripped[::-1]
        if reversed_text[0].isalpha():
            return True

    # Statistical bigram analysis - only for longer text
    if len(text_stripped) > 5:
        current_score = _score_text_naturalness(text_stripped)
        reversed_score = _score_text_naturalness(text_stripped[::-1])

        # If reversing improves score by 5+, text is reversed
        if reversed_score - current_score >= 5:
            return True

    # Consonant cluster check - detect impossible 4+ consonant sequences
    if _has_impossible_consonant_clusters(text_stripped):
        # Verify reversing fixes it
        if not _has_impossible_consonant_clusters(text_stripped[::-1]):
            return True

    # Check if ends with common reversed suffixes
    # Indian names often end with initials like "V " or "K " when correct
    # When reversed, they start with those initials
    if len(text_stripped) > 3:
        # Check for pattern like "X ABCDEFGH" where X is single letter
        # This could be reversed "HGFEDCBA X" (name with initial at end)
        parts = text_stripped.split()
        if len(parts) >= 2:
            first_part = parts[0]
            # If first part is single letter and rest is longer, might be reversed
            if len(first_part) == 1 and first_part.isupper():
                rest = ' '.join(parts[1:])
                # Check if reversed rest looks more like a name
                reversed_rest = rest[::-1]
                # Common name endings when correct: AN, AM, AR, AH, etc.
                if reversed_rest[-2:].upper() in ['AN', 'AM', 'AR', 'AH', 'AI', 'AY', 'ER', 'EN', 'UM', 'IN']:
                    return True

    return False
