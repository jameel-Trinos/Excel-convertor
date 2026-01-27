"""Party name fixer for correcting reversed/mirrored Tamil party names from PDF extraction."""

import logging
import re
from itertools import permutations
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PartyNameFixer:
    """
    Fix reversed/mirrored party names extracted from PDFs with vertical text.
    
    Handles word-by-word reversal that occurs when vertical text is extracted
    in the wrong direction (common in Tamil party names).
    """

    # Dictionary of known reversed party patterns: reversed_text -> correct_text
    # Correct canonical forms (as per user specification):
    # - "DRAVIDA MUNNETRA KAZHAGAM": "DMK"
    # - "ALL INDIA ANNA DRAVIDA MUNNETRA KAZHAGAM": "AIADMK"
    # - "BHARATIYA JANATA PARTY": "BJP"
    # - "INDIAN NATIONAL CONGRESS": "Congress"
    # - "VIDUTHALAI CHIRUTHAIGAL KATCHI": "VCK"
    # - "PATTALI MAKKAL KATCHI": "PMK"
    # - "NAAM TAMIZHAR KATCHI": "NTK" (note: TAMIZHAR not TAMILAR)
    # - "INDEPENDENT": "IND"
    
    REVERSED_PARTY_PATTERNS: Dict[str, str] = {
        # DRAVIDA MUNNETRA KAZHAGAM (DMK) - canonical form
        "DRAVIDA MUNNETRA KAZHAGAM": "DRAVIDA MUNNETRA KAZHAGAM",  # Already correct
        # Character-level reversals
        "ARTENNUM MAGAHZAK ADIVARD": "DRAVIDA MUNNETRA KAZHAGAM",
        "MAGAHZAK ARTENNUM ADIVARD": "DRAVIDA MUNNETRA KAZHAGAM",
        "ADIVARD ARTENNUM MAGAHZAK": "DRAVIDA MUNNETRA KAZHAGAM",
        "MAGAHZAK ARTENNUM ADIVARD DRAVIDA": "DRAVIDA MUNNETRA KAZHAGAM",
        # Word-order reversals
        "MUNNETRA KAZHAGAM DRAVIDA": "DRAVIDA MUNNETRA KAZHAGAM",
        "KAZHAGAM MUNNETRA DRAVIDA": "DRAVIDA MUNNETRA KAZHAGAM",
        "DRAVIDA KAZHAGAM MUNNETRA": "DRAVIDA MUNNETRA KAZHAGAM",
        "KAZHAGAM DRAVIDA MUNNETRA": "DRAVIDA MUNNETRA KAZHAGAM",
        "MUNNETRA DRAVIDA KAZHAGAM": "DRAVIDA MUNNETRA KAZHAGAM",
        
        # ALL INDIA DRAVIDA MUNNETRA KAZHAGAM (AIADMK) - canonical form (without ANNA)
        "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",  # Already correct
        # Word-order reversals (without ANNA)
        "MUNNETRA KAZHAGAM INDIA DRAVIDA ALL": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",
        "DRAVIDA MUNNETRA KAZHAGAM INDIA ALL": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",
        "KAZHAGAM MUNNETRA DRAVIDA INDIA ALL": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",
        "MUNNETRA KAZHAGAM DRAVIDA INDIA ALL": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",
        "INDIA DRAVIDA MUNNETRA KAZHAGAM ALL": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",
        # Word-order reversals with ANNA (map to without ANNA)
        "MUNNETRA ANNA KAZHAGAM INDIA DRAVIDA ALL": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",
        "ANNA DRAVIDA MUNNETRA KAZHAGAM INDIA ALL": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",
        "DRAVIDA MUNNETRA KAZHAGAM ANNA INDIA ALL": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",
        "KAZHAGAM MUNNETRA DRAVIDA ANNA INDIA ALL": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",
        "MUNNETRA KAZHAGAM DRAVIDA ANNA INDIA ALL": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",
        "ANNA KAZHAGAM INDIA DRAVIDA MUNNETRA ALL": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",
        # Also keep the variant with ANNA for backward compatibility, but prefer without ANNA
        "ALL INDIA ANNA DRAVIDA MUNNETRA KAZHAGAM": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",
        # Character-level reversals (map to without ANNA)
        "ARTENNUM ANNA MAGAHZAK AIDNI ADIVARD LLA": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",
        "LLA ADIVARD AIDNI MAGAHZAK ANNA ARTENNUM": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",
        "MAGAHZAK ARTENNUM ANNA ADIVARD AIDNI LLA": "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",
        
        # BHARATIYA JANATA PARTY (BJP) - canonical form
        "BHARATIYA JANATA PARTY": "BHARATIYA JANATA PARTY",  # Already correct
        # Word-order reversals
        "JANATA BHARATIYA PARTY": "BHARATIYA JANATA PARTY",
        "PARTY JANATA BHARATIYA": "BHARATIYA JANATA PARTY",
        "BHARATIYA PARTY JANATA": "BHARATIYA JANATA PARTY",
        "PARTY BHARATIYA JANATA": "BHARATIYA JANATA PARTY",
        "JANATA PARTY BHARATIYA": "BHARATIYA JANATA PARTY",
        
        # INDIAN NATIONAL CONGRESS - canonical form
        "INDIAN NATIONAL CONGRESS": "INDIAN NATIONAL CONGRESS",  # Already correct
        # Word-order reversals
        "NATIONAL INDIAN CONGRESS": "INDIAN NATIONAL CONGRESS",
        "CONGRESS NATIONAL INDIAN": "INDIAN NATIONAL CONGRESS",
        "INDIAN CONGRESS NATIONAL": "INDIAN NATIONAL CONGRESS",
        "CONGRESS INDIAN NATIONAL": "INDIAN NATIONAL CONGRESS",
        "NATIONAL CONGRESS INDIAN": "INDIAN NATIONAL CONGRESS",
        
        # VIDUTHALAI CHIRUTHAIGAL KATCHI (VCK) - canonical form
        "VIDUTHALAI CHIRUTHAIGAL KATCHI": "VIDUTHALAI CHIRUTHAIGAL KATCHI",  # Already correct
        # Word-order reversals
        "KATCHI VIDUTHALAI CHIRUTHAIGAL": "VIDUTHALAI CHIRUTHAIGAL KATCHI",
        "CHIRUTHAIGAL VIDUTHALAI KATCHI": "VIDUTHALAI CHIRUTHAIGAL KATCHI",
        "KATCHI CHIRUTHAIGAL VIDUTHALAI": "VIDUTHALAI CHIRUTHAIGAL KATCHI",
        "CHIRUTHAIGAL KATCHI VIDUTHALAI": "VIDUTHALAI CHIRUTHAIGAL KATCHI",
        
        # AMMA MAKKAL MUNNETRA KAZHAGAM variations
        "LAKKAM ARTENNUM MAGAHZAK AMMA": "AMMA MAKKAL MUNNETRA KAZHAGAM",
        "MAGAHZAK ARTENNUM LAKKAM AMMA": "AMMA MAKKAL MUNNETRA KAZHAGAM",
        "AMMA MAGAHZAK ARTENNUM LAKKAM": "AMMA MAKKAL MUNNETRA KAZHAGAM",
        # Word-order reversals
        "MAKKAL MUNNETRA KAZHAGAM AMMA": "AMMA MAKKAL MUNNETRA KAZHAGAM",
        "MUNNETRA KAZHAGAM MAKKAL AMMA": "AMMA MAKKAL MUNNETRA KAZHAGAM",
        "KAZHAGAM MUNNETRA MAKKAL AMMA": "AMMA MAKKAL MUNNETRA KAZHAGAM",
        "AMMA KAZHAGAM MUNNETRA MAKKAL": "AMMA MAKKAL MUNNETRA KAZHAGAM",
        
        # BAHUJAN SAMAJ PARTY - canonical form
        "BAHUJAN SAMAJ PARTY": "BAHUJAN SAMAJ PARTY",  # Already correct
        # Word-order reversals
        "PARTY BAHUJAN SAMAJ": "BAHUJAN SAMAJ PARTY",
        "SAMAJ PARTY BAHUJAN": "BAHUJAN SAMAJ PARTY",
        "SAMAJ BAHUJAN PARTY": "BAHUJAN SAMAJ PARTY",
        "PARTY SAMAJ BAHUJAN": "BAHUJAN SAMAJ PARTY",
        "BAHUJAN PARTY SAMAJ": "BAHUJAN SAMAJ PARTY",
        # Character-level reversed
        "YTRAP NAJAS UJAHAB": "BAHUJAN SAMAJ PARTY",
        
        # INDIA JANAYAKA KATCHI (also handle INDIYA variant)
        "INDIA JANAYAKA KATCHI": "INDIA JANAYAKA KATCHI",  # Already correct
        "INDIYA JANAYAKA KATCHI": "INDIA JANAYAKA KATCHI",  # Variant spelling
        # Character-level reversals - all word order combinations
        "IHCTAK AKAYANAJ AYIDNI": "INDIA JANAYAKA KATCHI",
        "AYIDNI AKAYANAJ IHCTAK": "INDIA JANAYAKA KATCHI",
        "AKAYANAJ AYIDNI IHCTAK": "INDIA JANAYAKA KATCHI",
        "AYIDNI IHCTAK AKAYANAJ": "INDIA JANAYAKA KATCHI",
        "AKAYANAJ IHCTAK AYIDNI": "INDIA JANAYAKA KATCHI",  # User reported pattern
        "IHCTAK AYIDNI AKAYANAJ": "INDIA JANAYAKA KATCHI",
        # Word-order reversals
        "JANAYAKA KATCHI INDIA": "INDIA JANAYAKA KATCHI",
        "JANAYAKA KATCHI INDIYA": "INDIA JANAYAKA KATCHI",
        "KATCHI JANAYAKA INDIA": "INDIA JANAYAKA KATCHI",
        "KATCHI JANAYAKA INDIYA": "INDIA JANAYAKA KATCHI",
        "INDIA KATCHI JANAYAKA": "INDIA JANAYAKA KATCHI",
        "INDIYA KATCHI JANAYAKA": "INDIA JANAYAKA KATCHI",
        
        # ANNA DRAVIDAR KAZHAGAM
        "MAGAHZAK RADIVARD ANNA": "ANNA DRAVIDAR KAZHAGAM",
        "ANNA RADIVARD MAGAHZAK": "ANNA DRAVIDAR KAZHAGAM",
        "KAZHAGAM DRAVIDAR ANNA": "ANNA DRAVIDAR KAZHAGAM",
        # Word-order reversals
        "DRAVIDAR KAZHAGAM ANNA": "ANNA DRAVIDAR KAZHAGAM",
        "KAZHAGAM DRAVIDAR ANNA": "ANNA DRAVIDAR KAZHAGAM",
        "ANNA KAZHAGAM DRAVIDAR": "ANNA DRAVIDAR KAZHAGAM",
        
        # PATTALI MAKKAL KATCHI (PMK) - canonical form
        "PATTALI MAKKAL KATCHI": "PATTALI MAKKAL KATCHI",  # Already correct
        # Character-level reversals - all word order combinations
        "IHCTAK LAKKAM ILATTAP": "PATTALI MAKKAL KATCHI",
        "ILATTAP LAKKAM IHCTAK": "PATTALI MAKKAL KATCHI",
        "LAKKAM ILATTAP IHCTAK": "PATTALI MAKKAL KATCHI",  # User reported pattern
        "LAKKAM IHCTAK ILATTAP": "PATTALI MAKKAL KATCHI",
        "ILATTAP IHCTAK LAKKAM": "PATTALI MAKKAL KATCHI",
        "IHCTAK ILATTAP LAKKAM": "PATTALI MAKKAL KATCHI",
        # Word-order reversals
        "MAKKAL PATTALI KATCHI": "PATTALI MAKKAL KATCHI",
        "PATTALI KATCHI MAKKAL": "PATTALI MAKKAL KATCHI",
        "KATCHI PATTALI MAKKAL": "PATTALI MAKKAL KATCHI",
        "KATCHI MAKKAL PATTALI": "PATTALI MAKKAL KATCHI",
        "MAKKAL KATCHI PATTALI": "PATTALI MAKKAL KATCHI",
        
        # NAAM TAMILAR KATCHI (NTK) - canonical form (user prefers TAMILAR)
        "NAAM TAMILAR KATCHI": "NAAM TAMILAR KATCHI",  # Already correct
        "NAAM TAMIZHAR KATCHI": "NAAM TAMILAR KATCHI",  # Variant spelling
        # Character-level reversals - all word order combinations
        "IHCTAK RALIMAT MAAN": "NAAM TAMILAR KATCHI",
        "MAAN RALIMAT IHCTAK": "NAAM TAMILAR KATCHI",
        "RALIMAT IHCTAK MAAN": "NAAM TAMILAR KATCHI",  # User reported pattern
        "RALIMAT MAAN IHCTAK": "NAAM TAMILAR KATCHI",
        "IHCTAK MAAN RALIMAT": "NAAM TAMILAR KATCHI",
        "MAAN IHCTAK RALIMAT": "NAAM TAMILAR KATCHI",
        "HCTAK RALIMAT MAAN": "NAAM TAMILAR KATCHI",  # Missing I at start
        "RALIMAT MAAN HCTAK": "NAAM TAMILAR KATCHI",
        # Word-order reversals
        "TAMILAR KATCHI NAAM": "NAAM TAMILAR KATCHI",
        "TAMIZHAR KATCHI NAAM": "NAAM TAMILAR KATCHI",
        "KATCHI TAMILAR NAAM": "NAAM TAMILAR KATCHI",
        "KATCHI TAMIZHAR NAAM": "NAAM TAMILAR KATCHI",
        "NAAM KATCHI TAMILAR": "NAAM TAMILAR KATCHI",
        "NAAM KATCHI TAMIZHAR": "NAAM TAMILAR KATCHI",
        
        # MAKKAL NAADAALUM KATCHI (for Column F in image)
        "MAKKAL NAADAALUM KATCHI": "MAKKAL NAADAALUM KATCHI",  # Already correct
        # Word-order reversals
        "KATCHI NAADAALUM MAKKAL": "MAKKAL NAADAALUM KATCHI",
        "NAADAALUM MAKKAL KATCHI": "MAKKAL NAADAALUM KATCHI",
        "KATCHI MAKKAL NAADAALUM": "MAKKAL NAADAALUM KATCHI",
        "NAADAALUM KATCHI MAKKAL": "MAKKAL NAADAALUM KATCHI",
        
        # INDEPENDENT variations
        "TNEDNEPEDNI": "INDEPENDENT",
        "TNEDNEPEDNI INDEPENDENT": "INDEPENDENT",  # Sometimes appears twice
        
        # NOTA
        "ATON": "NOTA",
        "NOTA ATON": "NOTA",
    }

    # Tamil party name keywords for pattern matching
    TAMIL_PARTY_KEYWORDS = [
        'DRAVIDA', 'MUNNETRA', 'KAZHAGAM', 'MAKKAL', 'AMMA',
        'BAHUJAN', 'SAMAJ', 'PARTY', 'JANAYAKA', 'KATCHI',
        'DRAVIDAR', 'ANNA', 'PATTALI', 'TAMILAR', 'TAMIZHAR', 'NAAM',
        'INDEPENDENT', 'INDIA', 'INDIYA', 'BHARATIYA', 'JANATA',
        'VIDUTHALAI', 'CHIRUTHAIGAL', 'NATIONAL', 'CONGRESS',
        'NAADAALUM'
    ]
    
    # Canonical party names (correct order)
    CANONICAL_PARTY_NAMES = [
        "DRAVIDA MUNNETRA KAZHAGAM",
        "ALL INDIA DRAVIDA MUNNETRA KAZHAGAM",  # Without ANNA
        "BHARATIYA JANATA PARTY",
        "INDIAN NATIONAL CONGRESS",
        "VIDUTHALAI CHIRUTHAIGAL KATCHI",
        "PATTALI MAKKAL KATCHI",
        "NAAM TAMILAR KATCHI",
        "INDIA JANAYAKA KATCHI",
        "BAHUJAN SAMAJ PARTY",
        "AMMA MAKKAL MUNNETRA KAZHAGAM",
        "MAKKAL NAADAALUM KATCHI",
        "INDEPENDENT",
        "NOTA",
    ]

    @classmethod
    def fix_reversed_party_name(cls, text: str) -> str:
        """
        Fix reversed party name using pattern matching and intelligent reversal detection.
        
        Args:
            text: Potentially reversed party name text
            
        Returns:
            Corrected party name, or original if no match found
        """
        if not text or len(text.strip()) < 3:
            return text
        
        text_upper = text.strip().upper()
        
        # Direct pattern match (exact match)
        if text_upper in cls.REVERSED_PARTY_PATTERNS:
            corrected = cls.REVERSED_PARTY_PATTERNS[text_upper]
            logger.debug(f"Fixed reversed party name (exact match): '{text}' -> '{corrected}'")
            return corrected
        
        # Try character-level reversal detection first (for cases like "RALIMAT IHCTAK MAAN")
        # Check if reversing each word individually and trying different word orders helps
        corrected = cls._try_character_reversal_fix(text)
        if corrected != text:
            logger.debug(f"Fixed reversed party name (character reversal): '{text}' -> '{corrected}'")
            return corrected
        
        # Try word-by-word reversal
        corrected = cls._fix_word_reversed_text(text)
        if corrected != text:
            logger.debug(f"Fixed reversed party name (word reversal): '{text}' -> '{corrected}'")
            return corrected
        
        # Try fuzzy matching (contains known reversed patterns)
        for reversed_pattern, correct_pattern in cls.REVERSED_PARTY_PATTERNS.items():
            if reversed_pattern in text_upper:
                # Replace the reversed pattern with correct pattern
                corrected = text_upper.replace(reversed_pattern, correct_pattern)
                if corrected != text_upper:
                    logger.debug(f"Fixed reversed party name (fuzzy match): '{text}' -> '{corrected}'")
                    return corrected
        
        return text
    
    @classmethod
    def _try_character_reversal_fix(cls, text: str) -> str:
        """
        Try to fix character-level reversals by reversing each word and checking against known patterns.
        
        This handles cases where each word is character-reversed (e.g., "RALIMAT" -> "TAMILAR")
        and the word order might also be different.
        
        Args:
            text: Text that may have character-level reversals
            
        Returns:
            Corrected text, or original if no match found
        """
        if not text or len(text.strip()) < 3:
            return text
        
        text_upper = text.strip().upper()
        words = text_upper.split()
        
        if len(words) < 2:
            return text
        
        # Generate all possible combinations:
        # 1. Reverse each word, keep word order
        reversed_words = [word[::-1] for word in words]
        candidate1 = ' '.join(reversed_words)
        
        # 2. Reverse each word, reverse word order
        candidate2 = ' '.join(reversed_words[::-1])
        
        # Check candidates 1 and 2 against known patterns first (most common cases)
        for candidate in [candidate1, candidate2]:
            # Check exact match in REVERSED_PARTY_PATTERNS first
            if candidate in cls.REVERSED_PARTY_PATTERNS:
                corrected = cls.REVERSED_PARTY_PATTERNS[candidate]
                logger.debug(f"Character reversal fix (pattern match): '{text}' -> '{corrected}'")
                return corrected
            # Check against known correct party names
            for correct_name in cls.REVERSED_PARTY_PATTERNS.values():
                if candidate == correct_name.upper():
                    logger.debug(f"Character reversal fix (exact match): '{text}' -> '{correct_name}'")
                    return correct_name
                # Also check if it's close (fuzzy match)
                if cls._is_similar_party_name(candidate, correct_name):
                    logger.debug(f"Character reversal fix (similar match): '{text}' -> '{correct_name}'")
                    return correct_name
        
        # 3. Try all permutations of word order with reversed characters (limit to reasonable number)
        # For efficiency, only try permutations if we have 4 or fewer words
        if len(reversed_words) <= 4:
            for perm in permutations(reversed_words):
                candidate = ' '.join(perm)
                # Check if this matches any known correct party name
                if candidate in cls.REVERSED_PARTY_PATTERNS:
                    corrected = cls.REVERSED_PARTY_PATTERNS[candidate]
                    logger.debug(f"Character reversal fix (permutation pattern): '{text}' -> '{corrected}'")
                    return corrected
                for correct_name in cls.REVERSED_PARTY_PATTERNS.values():
                    if candidate == correct_name.upper():
                        logger.debug(f"Character reversal fix (permutation exact): '{text}' -> '{correct_name}'")
                        return correct_name
                    # Also check if it's close (fuzzy match)
                    if cls._is_similar_party_name(candidate, correct_name):
                        logger.debug(f"Character reversal fix (permutation similar): '{text}' -> '{correct_name}'")
                        return correct_name
        
        return text
    
    @classmethod
    def _is_similar_party_name(cls, text1: str, text2: str) -> bool:
        """
        Check if two party names are similar (allowing for minor variations).
        
        Args:
            text1: First text to compare
            text2: Second text to compare
            
        Returns:
            True if texts are similar enough to be considered the same party
        """
        text1_upper = text1.upper().strip()
        text2_upper = text2.upper().strip()
        
        # Exact match
        if text1_upper == text2_upper:
            return True
        
        # Check if one contains the other (for partial matches)
        if text1_upper in text2_upper or text2_upper in text1_upper:
            return True
        
        # Check word overlap (at least 2 words in common)
        words1 = set(text1_upper.split())
        words2 = set(text2_upper.split())
        common_words = words1.intersection(words2)
        if len(common_words) >= 2:
            return True
        
        return False
    
    @classmethod
    def _fix_word_reversed_text(cls, text: str) -> str:
        """
        Fix text that is reversed word-by-word.
        
        For example:
        "LAKKAM ARTENNUM MAGAHZAK AMMA" -> "AMMA MAKKAL MUNNETRA KAZHAGAM"
        
        Strategy:
        1. Reverse each word individually
        2. Reverse the word order
        3. Check if result matches known party patterns
        
        Args:
            text: Text that may be word-reversed
            
        Returns:
            Corrected text, or original if no improvement
        """
        if not text or len(text.strip()) < 3:
            return text
        
        text_upper = text.strip().upper()
        
        # If text matches a known canonical party name, don't change it
        for canonical_name in cls.CANONICAL_PARTY_NAMES:
            if text_upper == canonical_name.upper():
                return text  # Already correct, don't reverse
        
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
        
        # Check which candidate matches known party patterns best
        candidates = [candidate1, candidate2, candidate3]
        best_match = text
        best_score = 0
        
        for candidate in candidates:
            candidate_upper = candidate.upper()
            score = 0
            
            # Check if it matches any known correct party name
            for correct_name in cls.REVERSED_PARTY_PATTERNS.values():
                if candidate_upper == correct_name.upper():
                    return correct_name  # Perfect match
                # Partial match score
                if correct_name.upper() in candidate_upper or candidate_upper in correct_name.upper():
                    score += 1
            
            # Check keyword matches
            for keyword in cls.TAMIL_PARTY_KEYWORDS:
                if keyword in candidate_upper:
                    score += 1
            
            if score > best_score:
                best_score = score
                best_match = candidate
        
        # Only return corrected version if it significantly improves the match
        # AND the original doesn't match a known correct name
        if best_score >= 2 and best_match != text:
            # Double-check: don't "fix" if original is already a known correct name
            original_is_correct = any(correct_name.upper() in text_upper or text_upper in correct_name.upper() 
                                     for correct_name in cls.CANONICAL_PARTY_NAMES)
            if not original_is_correct:
                return best_match
        
        return text
    
    @classmethod
    def is_likely_party_name(cls, text: str) -> bool:
        """
        Check if text is likely a party name (reversed or not).
        
        Args:
            text: Text to check
            
        Returns:
            True if text appears to be a party name
        """
        if not text or len(text.strip()) < 3:
            return False
        
        text_upper = text.strip().upper()
        
        # Check if contains party keywords
        keyword_count = sum(1 for keyword in cls.TAMIL_PARTY_KEYWORDS if keyword in text_upper)
        if keyword_count >= 2:
            return True
        
        # Check if matches known patterns (reversed or correct)
        all_patterns = list(cls.REVERSED_PARTY_PATTERNS.keys()) + list(cls.REVERSED_PARTY_PATTERNS.values())
        for pattern in all_patterns:
            if pattern in text_upper or text_upper in pattern:
                return True
        
        # Check for common party indicators
        party_indicators = ['PARTY', 'KATCHI', 'KAZHAGAM', 'SAMAJ', 'INDEPENDENT', 'NOTA']
        if any(indicator in text_upper for indicator in party_indicators):
            return True
        
        return False
    
    @classmethod
    def fix_header_with_party(cls, header: str) -> str:
        """
        Fix a header that may contain a party name.
        
        Handles formats like:
        - "NAME - PARTY NAME" (where party name may be reversed)
        - "PARTY NAME" (standalone party name)
        - "NAME (PARTY)" (party in parentheses)
        - "INDEPENDENT - NAME" (preserve this format)
        
        Args:
            header: Header text that may contain reversed party name
            
        Returns:
            Header with corrected party name
        """
        if not header:
            return header
        
        # Special case: "INDEPENDENT - NAME" format should be preserved
        if header.upper().startswith('INDEPENDENT - '):
            return header  # Don't change this format
        
        # Check if header contains party name patterns
        if not cls.is_likely_party_name(header):
            return header
        
        # Try to extract and fix party name from header
        # Pattern 1: "NAME - PARTY NAME"
        if ' - ' in header:
            parts = header.split(' - ', 1)
            if len(parts) == 2:
                name_part = parts[0].strip()
                party_part = parts[1].strip()
                
                # Don't fix if party part is "INDEPENDENT" - it's usually correct
                if party_part.upper() == 'INDEPENDENT':
                    return header
                
                fixed_party = cls.fix_reversed_party_name(party_part)
                if fixed_party != party_part:
                    return f"{name_part} - {fixed_party}"
        
        # Pattern 2: "NAME (PARTY)"
        match = re.search(r'\(([^)]+)\)', header)
        if match:
            party_in_parens = match.group(1)
            fixed_party = cls.fix_reversed_party_name(party_in_parens)
            if fixed_party != party_in_parens:
                return header.replace(f"({party_in_parens})", f"({fixed_party})")
        
        # Pattern 3: Standalone party name
        fixed = cls.fix_reversed_party_name(header)
        return fixed

