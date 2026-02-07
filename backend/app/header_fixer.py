"""Header text correction utilities for PDF extraction."""

import logging
import re
from typing import List

from .party_name_fixer import PartyNameFixer

logger = logging.getLogger(__name__)


class HeaderFixer:
    """Fix common header extraction issues from PDFs."""

    # Known patterns that indicate text is reversed
    KNOWN_REVERSED_PATTERNS = [
        ".ON .LS",      # SL. NO.
        ".oN .lS",      # Sl. No.
        "oN noitatS gnilloP",  # Polling Station No
        "noitatS gnilloP",     # Polling Station
        "ATON",         # NOTA
        "LATOT",        # TOTAL
        "setov dilav latoT",   # Total valid votes
    ]
    
    # Known correct patterns to check against
    KNOWN_CORRECT_STARTS = [
        "SL", "Sl", "S.", "NO", "No", 
        "POLLING", "Polling", 
        "TOTAL", "Total",
        "NOTA", "VALID", "Valid",
        "REJECTED", "Rejected",
        "TENDERED", "Tendered",
    ]

    @staticmethod
    def fix_reversed_text(text: str) -> str:
        """
        Fix reversed/mirrored text that sometimes appears in PDF extraction.

        Example: ".oN noitatS gnilloP" -> "Polling Station No."

        Now handles:
        - Character-level reversal (traditional)
        - Word-by-word reversal (for Tamil party names)
        - Party name specific fixes

        IMPORTANT: This function is now more conservative - it only fixes text
        if it's CLEARLY reversed, not if it looks correct.

        Args:
            text: Potentially reversed text

        Returns:
            Corrected text
        """
        if not text or len(text) < 2:
            return text

        original = text.strip()
        
        # First, check if text already starts with known correct patterns
        # If it does, it's likely already correct - don't modify it
        for pattern in HeaderFixer.KNOWN_CORRECT_STARTS:
            if original.upper().startswith(pattern.upper()):
                return original  # Already correct, don't touch it
        
        # Check for common correct patterns in the text (not just at start)
        # This helps identify headers like "PS No." or "Polling Station No."
        common_correct_patterns = [
            "PS", "No.", "NO.", "Station", "Polling", "Location", "Building",
            "Area", "Type", "Sl.", "Serial", "Voter", "Voters"
        ]
        for pattern in common_correct_patterns:
            if pattern.upper() in original.upper():
                # Text contains correct patterns, likely already correct
                # Only proceed if we find clear evidence of reversal
                break
        else:
            # No common correct patterns found, might be reversed
            pass
        
        # First, check if this is a party name and fix it using party-specific logic
        if PartyNameFixer.is_likely_party_name(original):
            fixed_party = PartyNameFixer.fix_reversed_party_name(original)
            if fixed_party != original:
                logger.debug(f"Fixed party name: '{original}' -> '{fixed_party}'")
                return fixed_party
        
        # Check if text matches known reversed patterns (definitive evidence)
        for pattern in HeaderFixer.KNOWN_REVERSED_PATTERNS:
            if pattern.lower() in original.lower():
                # Definitely reversed, fix it
                logger.debug(f"Fixed reversed text (known pattern): '{original}' -> '{original[::-1]}'")
                return original[::-1]
        
        # Try word-by-word reversal for longer text (likely party names or multi-word headers)
        # But only if original doesn't look natural
        if len(original) > 10 and ' ' in original:
            original_score = HeaderFixer._english_score(original)
            # Only try fixing if original score is very low (likely reversed)
            if original_score < 2:
                word_fixed = HeaderFixer._fix_word_reversed_text(original)
                if word_fixed != original:
                    word_fixed_score = HeaderFixer._english_score(word_fixed)
                    # Only use if significantly better
                    if word_fixed_score > original_score + 2:
                        logger.debug(f"Fixed word-reversed text: '{original}' -> '{word_fixed}'")
                        return word_fixed
        
        # Heuristic checks for character-level reversed text
        # Only apply if original doesn't look natural
        original_score = HeaderFixer._english_score(original)
        if original_score >= 2:
            # Original looks natural, don't reverse it
            return original
        
        reversed_text = original[::-1]
        
        # Check 1: Does it start with punctuation but reversed version doesn't?
        if original[0] in ".," and reversed_text[0] not in ".,":
            if HeaderFixer._looks_natural(reversed_text):
                reversed_score = HeaderFixer._english_score(reversed_text)
                # Only use if significantly better
                if reversed_score > original_score + 2:
                    logger.debug(f"Fixed reversed text (punctuation check): '{original}' -> '{reversed_text}'")
                    return reversed_text
        
        # Check 2: Does reversed version start with known patterns?
        for pattern in HeaderFixer.KNOWN_CORRECT_STARTS:
            if reversed_text.upper().startswith(pattern.upper()):
                reversed_score = HeaderFixer._english_score(reversed_text)
                # Only use if significantly better
                if reversed_score > original_score + 2:
                    logger.debug(f"Fixed reversed text (pattern match): '{original}' -> '{reversed_text}'")
                    return reversed_text
        
        # Check 3: Count common English word patterns
        reversed_score = HeaderFixer._english_score(reversed_text)
        
        # Only reverse if reversed version is SIGNIFICANTLY better
        if reversed_score > original_score + 3 and reversed_score >= 3:
            logger.debug(f"Fixed reversed text (score check): '{original}' -> '{reversed_text}'")
            return reversed_text

        # Default: keep original (it's likely correct)
        return original
    
    @staticmethod
    def _fix_word_reversed_text(text: str) -> str:
        """
        Fix text that is reversed word-by-word (common in vertical text extraction).
        
        Strategy:
        1. Reverse each word individually
        2. Reverse the word order
        3. Return if it improves the score
        
        Args:
            text: Text that may be word-reversed
            
        Returns:
            Corrected text, or original if no improvement
        """
        if not text or len(text.strip()) < 3:
            return text
        
        words = text.strip().split()
        if len(words) < 2:
            return text
        
        # Strategy 1: Reverse each word, then reverse word order
        reversed_words = [word[::-1] for word in words]
        reversed_word_order = reversed_words[::-1]
        candidate1 = ' '.join(reversed_word_order)
        
        # Strategy 2: Just reverse word order (words themselves may be correct)
        candidate2 = ' '.join(words[::-1])
        
        # Strategy 3: Reverse each word but keep word order
        candidate3 = ' '.join([word[::-1] for word in words])
        
        # Score each candidate
        original_score = HeaderFixer._english_score(text)
        candidates = [
            (candidate1, HeaderFixer._english_score(candidate1)),
            (candidate2, HeaderFixer._english_score(candidate2)),
            (candidate3, HeaderFixer._english_score(candidate3)),
        ]
        
        # Find best candidate
        best_candidate = text
        best_score = original_score
        
        for candidate, score in candidates:
            if score > best_score:
                best_score = score
                best_candidate = candidate
        
        # Only return if significantly better
        if best_score > original_score and best_score >= 2:
            return best_candidate
        
        return text

    @staticmethod
    def _english_score(text: str) -> int:
        """Score text based on common English patterns."""
        score = 0
        text_lower = text.lower()
        
        # Common English word patterns
        patterns = [
            "the", "and", "for", "of", "in", "to", "is", "no", "no.",
            "sl", "poll", "station", "total", "valid", "vote", "nota",
            "reject", "tender", "cast", "favour",
        ]
        
        for pattern in patterns:
            if pattern in text_lower:
                score += 1
        
        # Check for natural word boundaries (space + capital or space + lowercase)
        words = text.split()
        for word in words:
            if word and word[0].isupper() and len(word) > 1 and word[1:].islower():
                score += 1
        
        return score

    @staticmethod
    def _looks_natural(text: str) -> bool:
        """Check if text looks like natural language."""
        # Natural text typically:
        # - Starts with capital letter or number
        # - Contains mostly letters
        # - Doesn't start with punctuation

        if not text:
            return False

        first_char = text[0]
        if first_char.isupper() or first_char.isdigit():
            # Count letter ratio
            letters = sum(1 for c in text if c.isalpha())
            total = len(text)

            if total > 0 and (letters / total) > 0.5:
                return True

        return False

    @staticmethod
    def clean_multiline_header(text: str) -> str:
        """
        Clean multi-line headers by joining them properly.

        Args:
            text: Header text potentially with line breaks

        Returns:
            Cleaned single-line header
        """
        if not text:
            return text

        # Split by newlines
        lines = text.split('\n')

        # Clean each line
        cleaned_lines = [line.strip() for line in lines if line.strip()]

        # Join with space
        return ' '.join(cleaned_lines)

    @staticmethod
    def format_candidate_header(text: str) -> str:
        """
        Format candidate name headers to be cleaner.
        
        Converts: "KARTHIYAYI NI. P (BJP)" -> "KARTHIYAYI NI. P (BJP)"
        Handles multi-line names and ensures party abbreviation is preserved.
        
        Args:
            text: Header text with candidate name and party
            
        Returns:
            Cleaned header
        """
        if not text:
            return text
            
        # First clean any newlines
        text = text.replace('\n', ' ').replace('\r', ' ')
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        # Check if it has party abbreviation in parentheses
        # Pattern: NAME (PARTY) where PARTY is uppercase letters
        match = re.search(r'\(([A-Z]+)\)\s*$', text)
        if match:
            party = match.group(1)
            name = text[:match.start()].strip()
            # Format nicely: "NAME (PARTY)"
            return f"{name} ({party})"
        
        return text

    @staticmethod
    def fix_header_list(headers: List[str]) -> List[str]:
        """
        Fix all headers in a list, including reversed candidate names and party names.

        Args:
            headers: List of potentially broken headers

        Returns:
            List of fixed headers
        """
        fixed = []

        for header in headers:
            if not header or not header.strip():
                fixed.append(header)
                continue
            
            original_header = header
            
            # Step 1: Fix party names in parentheses (e.g., "NAME (reversed party)" -> "NAME (correct party)")
            # Pattern: "CANDIDATE (PARTY)" where PARTY might be reversed
            paren_match = re.search(r'\(([^)]+)\)', header)
            if paren_match:
                party_in_parens = paren_match.group(1).strip()
                name_part = header[:paren_match.start()].strip()
                
                # Fix the party name in parentheses
                fixed_party = PartyNameFixer.fix_reversed_party_name(party_in_parens)
                if fixed_party != party_in_parens:
                    # Replace the party part
                    header = f"{name_part} ({fixed_party})"
                    logger.debug(f"Fixed party in parentheses: '{party_in_parens}' -> '{fixed_party}'")
                
                # Also check if the name part itself is reversed
                if name_part:
                    fixed_name = HeaderFixer._fix_candidate_name(name_part)
                    if fixed_name != name_part:
                        header = f"{fixed_name} ({fixed_party if fixed_party != party_in_parens else party_in_parens})"
                        logger.debug(f"Fixed candidate name: '{name_part}' -> '{fixed_name}'")
            
            # Step 2: Fix "NAME - PARTY" format
            elif ' - ' in header:
                parts = header.split(' - ', 1)
                if len(parts) == 2:
                    name_part = parts[0].strip()
                    party_part = parts[1].strip()
                    
                    # Fix candidate name
                    fixed_name = HeaderFixer._fix_candidate_name(name_part)
                    
                    # Fix party name
                    if party_part.upper() in ['INDEPENDENT', 'IND', 'NOTA']:
                        fixed_party = party_part  # Keep as is
                    else:
                        fixed_party = PartyNameFixer.fix_reversed_party_name(party_part)
                    
                    header = f"{fixed_name} - {fixed_party}"
            
            # Step 3: Fix party names in headers (handles standalone party names)
            else:
                # Check if it's a party name
                if PartyNameFixer.is_likely_party_name(header):
                    header = PartyNameFixer.fix_header_with_party(header)
                else:
                    # Might be a candidate name without party - fix it
                    fixed_name = HeaderFixer._fix_candidate_name(header)
                    if fixed_name != header:
                        header = fixed_name
                    # Also try general reversal fix
                    else:
                        header = HeaderFixer.fix_reversed_text(header)

            # Step 4: Clean multiline
            header = HeaderFixer.clean_multiline_header(header)
            
            # Step 5: Format candidate headers (with party abbreviations)
            header = HeaderFixer.format_candidate_header(header)

            # Step 6: Remove extra whitespace
            header = ' '.join(header.split())
            
            if header != original_header:
                logger.debug(f"Fixed header: '{original_header}' -> '{header}'")

            fixed.append(header)

        return fixed
    
    @staticmethod
    def _fix_candidate_name(name: str) -> str:
        """
        Fix reversed candidate names.
        
        Candidate names often have patterns like:
        - "JURAK.J" (might be correct)
        - "J.RAKU" (reversed)
        - "O J.R" (might be "J.R O" reversed)
        
        Args:
            name: Candidate name that might be reversed
            
        Returns:
            Fixed candidate name
        """
        if not name or len(name) < 2:
            return name
        
        original = name.strip()
        
        # Check if it looks like a reversed name
        # Pattern: names often have periods and capital letters
        # Reversed names might have periods at the end instead of middle
        
        # If name ends with period and starts with lowercase, might be reversed
        if original.endswith('.') and len(original) > 2:
            # Check if reversing improves it
            reversed_name = original[::-1]
            original_score = HeaderFixer._english_score(original)
            reversed_score = HeaderFixer._english_score(reversed_name)
            
            # Also check for common name patterns
            # Names often have: "FIRST.MIDDLE LAST" or "FIRST LAST"
            # Reversed might be: "TSAL .DLEMID .TSRIF"
            if reversed_score > original_score + 1:
                return reversed_name
        
        # Try word-by-word reversal for multi-word names
        if ' ' in original:
            words = original.split()
            # Check if reversing word order helps
            reversed_words = words[::-1]
            reversed_order = ' '.join(reversed_words)
            
            original_score = HeaderFixer._english_score(original)
            reversed_score = HeaderFixer._english_score(reversed_order)
            
            if reversed_score > original_score + 1:
                return reversed_order
        
        # Try character-level reversal if it's short and looks reversed
        if len(original) < 20 and not original[0].isupper():
            reversed_chars = original[::-1]
            original_score = HeaderFixer._english_score(original)
            reversed_score = HeaderFixer._english_score(reversed_chars)
            
            if reversed_score > original_score + 2:
                return reversed_chars
        
        return original

    @staticmethod
    def standardize_common_headers(headers: List[str]) -> List[str]:
        """
        Standardize common header variations.

        Args:
            headers: List of headers

        Returns:
            Standardized headers
        """
        standardizations = {
            # Serial number variations
            r'^\.?[Ss]\.?\s*[Nn][Oo]\.?$': 'S.NO',
            r'^[Ss]erial\.?\s*[Nn]o\.?$': 'S.NO',
            r'^[Ss][Rr]\.?\s*[Nn][Oo]\.?$': 'S.NO',

            # Polling station variations
            r'^[Pp]olling\.?\s*[Ss]tation\.?\s*[Nn]o\.?$': 'Polling Station No.',
            r'^[Pp][Ss]\.?\s*[Nn][Oo]\.?$': 'Polling Station No.',

            # Total variations
            r'^[Tt]otal\.?\s*[Vv]otes?$': 'Total Votes',
            r'^[Tt]otal$': 'Total',
        }

        result = []
        for header in headers:
            standardized = header

            # Try each pattern
            for pattern, replacement in standardizations.items():
                if re.match(pattern, header.strip(), re.IGNORECASE):
                    standardized = replacement
                    break

            result.append(standardized)

        return result
