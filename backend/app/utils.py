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
        # After reversing, check if it's still reversed (shouldn't be)
        # If it is, it might be double-reversed or incorrectly detected
        if _is_likely_reversed(text):
            # Double-check: if reversing again makes it better, keep original
            double_reversed = text[::-1]
            if _score_text_naturalness(double_reversed) > _score_text_naturalness(text):
                text = double_reversed
    # Also check for common reversed patterns even without RTL marker
    elif text and _is_likely_reversed(text):
        original_text = text
        text = text[::-1]
        # Verify the fix improved the text (not double-reversed)
        if _is_likely_reversed(text):
            # If still reversed, might be incorrectly detected - check scores
            original_score = _score_text_naturalness(original_text)
            fixed_score = _score_text_naturalness(text)
            if original_score >= fixed_score:
                # Original was better, don't reverse
                text = original_text

    return text


def _score_text_naturalness(text: str) -> float:
    """
    Score text based on English bigram frequency and Indian election terminology.
    Returns: Higher score = more likely correct (not reversed).

    Uses common English bigrams (TH, HE, IN, ER) and impossible
    word-start patterns (JK, MJ, NK, etc.) to score naturalness.
    Also handles mixed English-Tamil text and Indian election terminology.
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
    
    # Common Indian election terminology patterns (when correct)
    ELECTION_TERMS = [
        'WARD', 'STREET', 'COLONY', 'NAGAR', 'CROSS', 'ROAD',
        'POLLING', 'STATION', 'ELECTOR', 'OVERSEAS', 'VALID',
        'VOTES', 'CANDIDATE', 'PARTY', 'ABBREVIATION', 'TOTAL',
        'REJECTED', 'TENDERED', 'NOTA', 'BUILDING', 'LOCATION',
        'AREA', 'AREAS', 'SIVAPURAM', 'PITCHIVAKKAM', 'EDAIYARPAKKAM'
    ]
    
    # Tamil place name endings (when correct)
    TAMIL_ENDINGS = ['AM', 'UR', 'AR', 'AI', 'AY', 'IN', 'AN', 'AL', 'IL', 'UL']

    # Normalize: remove punctuation, uppercase
    clean_text = ''.join(c for c in text if c.isalpha() or c.isspace()).upper()
    if len(clean_text) < 3:
        return 0
    
    # Extract words for term matching
    words = clean_text.split()
    text_alpha_only = ''.join(c for c in clean_text if c.isalpha())

    # Extract bigrams
    bigrams = [text_alpha_only[i:i+2] for i in range(len(text_alpha_only)-1)] if len(text_alpha_only) >= 2 else []

    # Score based on common English bigrams
    common_count = sum(1 for bg in bigrams if bg in COMMON_BIGRAMS)
    impossible_count = sum(1 for imp in IMPOSSIBLE_STARTS if text_alpha_only.startswith(imp))
    
    # Bonus for election terminology
    election_term_bonus = 0
    for term in ELECTION_TERMS:
        if term in clean_text:
            election_term_bonus += 2
    
    # Bonus for Tamil place name patterns (when correct, they end with common Tamil endings)
    tamil_bonus = 0
    for word in words:
        if len(word) >= 3:
            # Check if word ends with common Tamil place name endings
            if any(word.endswith(ending) for ending in TAMIL_ENDINGS):
                tamil_bonus += 1
    
    # Penalty for reversed patterns
    reversed_penalty = 0
    reversed_indicators = ['TEERTS', 'DRAW', 'RAGAN', 'SROTCEL', 'SAESREVO', 'MARUPAVIS']
    for indicator in reversed_indicators:
        if indicator in clean_text:
            reversed_penalty += 5

    base_score = common_count - (impossible_count * 5)
    return base_score + election_term_bonus + tamil_bonus - reversed_penalty


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
    
    Enhanced to detect corrupted/reversed text patterns like:
    - "teertS dr3 ragaN rayireP" (reversed street names)
    - Text with impossible consonant clusters
    - Text that scores poorly on naturalness
    
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
        # Polling station data patterns (reversed)
        ")p(",               # (p) - common in reversed polling area text
        ")pt(",              # (tp) - common in reversed polling area text
        "maragayileV",       # Veliyagaram (reversed)
        "tepillaP",          # Pallipet (reversed)
        "ruhtalok",          # Kolathur (reversed)
        "- ]",               # ] - (reversed bracket pattern)
        "] -",               # - [ (reversed bracket pattern)
        # Corrupted/reversed street patterns (like "teertS dr3 ragaN rayireP")
        "teertS",            # Street (reversed)
        "draw",              # ward (reversed)
        "yrehcaleV",         # Velachery (reversed)
        "ragaN",             # Nagar (reversed)
        "rayireP",           # Periyar (reversed)
        "ssorC",             # Cross (reversed)
        "ht",                # th (reversed, common in street numbers)
        "dr",                # rd (reversed, common in street numbers)
        "ts",                # st (reversed, common in street numbers)
        # Enhanced polling area specific patterns
        "srotcelE saesrevO", # Overseas Electors (reversed)
        "marupaviS",         # Sivapuram (reversed)
        ")P(",               # Reversed (P)
        ")V.R(",             # Reversed (R.V)
        ")999)-",            # Reversed (999)-
        "draW)V.R(",         # Reversed (R.V) Ward
        "teertS dr",         # Reversed Street rd
        "ynoloc",            # Reversed colony
        "srotcelE",          # Electors (reversed)
        "saesrevO",          # Overseas (reversed)
        "marupaviS 1",       # Sivapuram 1 (reversed)
        "marupaviS.7",       # 7.Sivapuram (reversed)
        "marupaviS.6",       # 6.Sivapuram (reversed)
        "marupaviS.5",       # 5.Sivapuram (reversed)
        "marupaviS.4",       # 4.Sivapuram (reversed)
        "marupaviS.3",       # 3.Sivapuram (reversed)
        "marupaviS.2",       # 2.Sivapuram (reversed)
        "marupaviS.1",       # 1.Sivapuram (reversed)
        "kuruk teertS",      # Street kuruk (reversed)
        "iaragartra teertS", # Street arrangement (reversed)
        "daor teertS",       # Street road (reversed)
        "udan teertS",       # Street nadu (reversed)
        "liokanajaB teertS", # Street Bajakanoli (reversed)
    ]
    
    # Check for corrupted text patterns (reversed street names, addresses)
    # Pattern: words ending with common reversed suffixes
    words = text_stripped.split()
    if len(words) > 1:
        reversed_suffixes = ["teertS", "draw", "ragaN", "rayireP", "ssorC", "srotcelE", "saesrevO", "marupaviS", "ynoloc"]
        for word in words:
            for suffix in reversed_suffixes:
                if word.endswith(suffix) or word.startswith(suffix):
                    return True
        
        # Check for reversed bracket patterns in polling area text
        # Pattern like ")P(" or ")V.R(" indicates reversed text
        for word in words:
            if word.startswith(")") and word.endswith("(") and len(word) >= 3:
                return True
            # Pattern like ")999)-" indicates reversed number pattern
            if word.startswith(")") and word.endswith(")-") and any(c.isdigit() for c in word):
                return True
    
    for pattern in reversed_patterns:
        if pattern in text_stripped:
            return True
    
    # Check if starts with punctuation (often indicates reversed text)
    # This includes closing parentheses/brackets which are common in reversed text
    if text_stripped and text_stripped[0] in ".,;:)]}" and len(text_stripped) > 1:
        # Check if reversing makes it start with a letter or opening bracket
        reversed_text = text_stripped[::-1]
        if reversed_text[0].isalpha() or reversed_text[0] in "[({":
            return True
    
    # Context-aware detection: If text contains polling area keywords, be more aggressive
    # Check for known polling area context words that suggest this is polling area text
    polling_area_keywords = ["Ward", "Street", "Colony", "Nagar", "Cross", "Road", "Area", "Areas", 
                            "Electors", "Overseas", "Polling", "Station", "Building", "Location"]
    text_upper = text_stripped.upper()
    has_polling_context = any(keyword.upper() in text_upper for keyword in polling_area_keywords)
    
    # If we have polling area context and text shows reversed patterns, be more aggressive
    if has_polling_context:
        # Check for reversed Tamil place name patterns (like "marupaviS")
        tamil_place_patterns = ["marupaviS", "tepillaP", "ruhtalok", "maragayileV", "yrehcaleV"]
        for pattern in tamil_place_patterns:
            if pattern in text_stripped:
                return True
        
        # Check for reversed bracket-number patterns like ")999)-" or ")P("
        if ")P(" in text_stripped or ")V.R(" in text_stripped or ")999)-" in text_stripped:
            return True
        
        # Check for pattern where text starts with closing bracket/parenthesis
        # and contains reversed place names or street names
        if text_stripped[0] in ")]}" and any(pattern in text_stripped for pattern in ["marupaviS", "teertS", "draw"]):
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
