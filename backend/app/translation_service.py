"""
Translation Service for translating text using Google Translate.

This service uses the deep-translator library (Google Translate API) for translation.

Supported languages:
- Tamil (ta)
- Hindi (hi)
- English (en)

Preserves:
- Numbers (pure and formatted)
- IDs and codes
- Phone numbers, pin codes
- Percentages, dates
- URLs, emails
- Already translated text
"""

import re
import logging
import hashlib
from typing import Dict, List, Optional, Callable

logger = logging.getLogger(__name__)

# Global translator instance to reuse
_translator = None


class TranslationAPIError(Exception):
    """Raised when translation has an unrecoverable error."""

    def __init__(self, message: str, error_type: str = "translation_error"):
        self.message = message
        self.error_type = error_type
        super().__init__(self.message)


class TranslationService:
    """Service for translating text using Google Translate."""

    # Regex patterns for content that should NOT be translated
    PRESERVE_PATTERNS = [
        r"^\d+$",  # Pure numbers
        r"^\d{1,3}(,\d{3})*(\.\d+)?$",  # Formatted numbers (1,234.56)
        r"^[A-Z]{1,5}\d+[A-Z0-9]*$",  # IDs like ABC123, PS001, A1B2C3
        r"^\d{10,12}$",  # Phone numbers
        r"^\d{6}$",  # Indian pin codes
        r"^\d+(\.\d+)?%$",  # Percentages (20%, 45.5%)
        r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$",  # Dates (12/02/2026, 12-02-26)
        r"^\d{4}[/-]\d{1,2}[/-]\d{1,2}$",  # Dates (2026/02/12)
        r"^https?://\S+$",  # URLs
        r"^[\w\.\-]+@[\w\.\-]+\.\w+$",  # Email addresses
        r"^S\.?\s*No\.?$",  # S.No, S No, SNo
        r"^Sr\.?\s*No\.?$",  # Sr.No, Sr No
        r"^No\.?$",  # No., No
        r"^-+$",  # Dashes only
        r"^\s*$",  # Empty or whitespace
    ]

    # Known party abbreviations that should NOT be translated (case-sensitive)
    KNOWN_PARTY_ABBREVIATIONS = {
        "DMK", "BJP", "AIADMK", "NOTA", "INC", "CPI", "CPM", "CPI(M)",
        "AIMIM", "TMC", "BSP", "SP", "RJD", "JDU", "NCP", "SAD",
        "TDP", "YSRCP", "TRS", "BJD", "SHS", "RLD", "JDS", "IUML",
        "VCK", "PMK", "MDMK", "DMDK", "NTK", "MNM", "MNMK"
    }

    # Tamil Unicode range
    TAMIL_RANGE = (0x0B80, 0x0BFF)
    # Hindi Unicode range (Devanagari)
    HINDI_RANGE = (0x0900, 0x097F)

    # Common election-related translations for consistency
    COMMON_TRANSLATIONS = {
        "tamil": {
            "Polling Station": "வாக்குச்சாவடி",
            "Booth": "வாக்குச்சாவடி",
            "Booth No": "வாக்குச்சாவடி எண்",
            "Constituency": "தொகுதி",
            "Candidate": "வேட்பாளர்",
            "Voter": "வாக்காளர்",
            "Total": "மொத்தம்",
            "Valid Votes": "செல்லுபடியான வாக்குகள்",
            "Invalid Votes": "செல்லாத வாக்குகள்",
            "Rejected Votes": "நிராகரிக்கப்பட்ட வாக்குகள்",
            "Serial No": "வரிசை எண்",
            "S.No": "வ.எண்",
            "Name": "பெயர்",
            "Address": "முகவரி",
            "Location": "இடம்",
            "Building": "கட்டிடம்",
            "Assembly": "சட்டமன்றம்",
            "Parliamentary": "நாடாளுமன்ற",
            "Party": "கட்சி",
            "Votes Polled": "பதிவான வாக்குகள்",
            "Total Votes": "மொத்த வாக்குகள்",
            "Percentage": "சதவீதம்",
            "District": "மாவட்டம்",
            "Taluk": "வட்டம்",
            "Ward": "வார்டு",
            "Village": "கிராமம்",
            "Town": "நகரம்",
            "City": "நகரம்",
            "Male": "ஆண்",
            "Female": "பெண்",
            "Others": "மற்றவர்கள்",
            "NOTA": "நோட்டா",
            "Winner": "வெற்றியாளர்",
            "Result": "முடிவு",
        },
        "hindi": {
            "Polling Station": "मतदान केंद्र",
            "Booth": "बूथ",
            "Booth No": "बूथ नंबर",
            "Constituency": "निर्वाचन क्षेत्र",
            "Candidate": "उम्मीदवार",
            "Voter": "मतदाता",
            "Total": "कुल",
            "Valid Votes": "वैध मत",
            "Invalid Votes": "अमान्य मत",
            "Rejected Votes": "खारिज मत",
            "Serial No": "क्रम संख्या",
            "S.No": "क्र.सं.",
            "Name": "नाम",
            "Address": "पता",
            "Location": "स्थान",
            "Building": "भवन",
            "Assembly": "विधानसभा",
            "Parliamentary": "संसदीय",
            "Party": "पार्टी",
            "Votes Polled": "डाले गए मत",
            "Total Votes": "कुल मत",
            "Percentage": "प्रतिशत",
            "District": "जिला",
            "Taluk": "तालुका",
            "Ward": "वार्ड",
            "Village": "गांव",
            "Town": "शहर",
            "City": "शहर",
            "Male": "पुरुष",
            "Female": "महिला",
            "Others": "अन्य",
            "NOTA": "नोटा",
            "Winner": "विजेता",
            "Result": "परिणाम",
        },
    }

    # Language codes for Google Translate
    LANGUAGE_CODES = {
        "tamil": "ta",
        "hindi": "hi",
        "english": "en",
    }

    def __init__(self):
        """Initialize TranslationService with Google Translate."""
        self.enabled = False
        self._cache: Dict[str, str] = {}
        self._translator = None

        logger.info("TranslationService initialized with Google Translate")
        self._load_translator()

    def _load_translator(self):
        """Load Google Translate translator."""
        global _translator

        if _translator is not None:
            self._translator = _translator
            self.enabled = True
            logger.info("Using cached Google Translate instance")
            return

        try:
            from deep_translator import GoogleTranslator
            # deep_translator doesn't need initialization with a translator object
            # We'll create translators on-demand per translation
            self._translator = GoogleTranslator  # Store the class
            _translator = self._translator
            self.enabled = True
            logger.info("Google Translate (deep-translator) loaded successfully")
        except ImportError as e:
            logger.error(f"deep-translator not installed: {e}")
            logger.error("Install with: pip install deep-translator==1.11.4")
            raise TranslationAPIError(
                "Missing deep-translator library. Install with: pip install deep-translator==1.11.4",
                error_type="missing_dependency",
            )
        except Exception as e:
            logger.error(f"Failed to load Google Translate: {e}")
            raise TranslationAPIError(f"Failed to initialize Google Translate: {e}")

    def _get_cache_key(self, text: str, target_lang: str) -> str:
        """Generate a cache key for translation."""
        content = f"{target_lang}:{text}"
        return hashlib.md5(content.encode()).hexdigest()

    def _contains_language(self, text: str, unicode_range: tuple) -> bool:
        """Check if text contains characters from specified Unicode range."""
        for char in text:
            code_point = ord(char)
            if unicode_range[0] <= code_point <= unicode_range[1]:
                return True
        return False

    def _is_mostly_language(self, text: str, unicode_range: tuple, threshold: float = 0.8) -> bool:
        """Check if text is mostly in specified language (>threshold% characters)."""
        if not text.strip():
            return False

        lang_count = 0
        letter_count = 0

        for char in text:
            if char.isalpha():
                letter_count += 1
                code_point = ord(char)
                if unicode_range[0] <= code_point <= unicode_range[1]:
                    lang_count += 1

        if letter_count == 0:
            return False

        return (lang_count / letter_count) > threshold

    def should_translate(self, text: str, target_lang: str) -> bool:
        """
        Determine if text should be translated.

        Args:
            text: Text to check
            target_lang: Target language (tamil, hindi, english)

        Returns:
            True if text should be translated, False otherwise
        """
        if not text or not isinstance(text, str):
            return False

        text = text.strip()

        # Empty text
        if not text:
            return False

        # Check against preserve patterns (case-insensitive)
        for pattern in self.PRESERVE_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                return False

        # Check if it's a known party abbreviation (case-sensitive, exact match)
        if text in self.KNOWN_PARTY_ABBREVIATIONS:
            return False

        # Check if already in target language
        if target_lang == "tamil" and self._is_mostly_language(text, self.TAMIL_RANGE):
            return False
        elif target_lang == "hindi" and self._is_mostly_language(text, self.HINDI_RANGE):
            return False

        # Check if it's only special characters and numbers
        alphanumeric_only = re.sub(r"[^a-zA-Z\u0B80-\u0BFF\u0900-\u097F]", "", text)
        if not alphanumeric_only:
            return False

        return True

    def translate_text(self, text: str, target_lang: str = "tamil", source_lang: str = "auto") -> str:
        """
        Translate a single text string.

        Args:
            text: Text to translate
            target_lang: Target language (tamil, hindi, english)
            source_lang: Source language (auto for auto-detect)

        Returns:
            Translated text
        """
        if not self.enabled:
            logger.warning("Translation service not enabled, returning original text")
            return text

        if not text or not isinstance(text, str):
            return text or ""

        text = text.strip()

        # Check if translation is needed
        if not self.should_translate(text, target_lang):
            return text

        # Check cache
        cache_key = self._get_cache_key(text, target_lang)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Check common translations first
        if target_lang in self.COMMON_TRANSLATIONS:
            if text in self.COMMON_TRANSLATIONS[target_lang]:
                result = self.COMMON_TRANSLATIONS[target_lang][text]
                self._cache[cache_key] = result
                return result

        # Translate with Google Translate
        try:
            target_code = self.LANGUAGE_CODES.get(target_lang, "ta")

            # Detect source language if not specified or auto
            if source_lang == "auto":
                # Simple detection based on Unicode ranges
                if self._contains_language(text, self.TAMIL_RANGE):
                    source_code = "ta"
                elif self._contains_language(text, self.HINDI_RANGE):
                    source_code = "hi"
                else:
                    source_code = "en"
            else:
                source_code = self.LANGUAGE_CODES.get(source_lang, "en")

            # Don't translate if source and target are the same
            if source_code == target_code:
                return text

            # Create translator for this specific language pair
            # deep_translator uses class methods, not instances
            translator = self._translator(source=source_code, target=target_code)
            result = translator.translate(text).strip()

            self._cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"Translation error for '{text}': {e}")
            return text  # Return original on error

    async def translate_batch(
        self,
        texts: List[str],
        target_lang: str = "tamil",
        source_lang: str = "auto",
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[str]:
        """
        Batch translate multiple texts.

        Args:
            texts: List of texts to translate
            target_lang: Target language (tamil, hindi, english)
            source_lang: Source language (auto for auto-detect)
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            List of translated texts
        """
        if not self.enabled:
            logger.warning("Translation service not enabled, returning original texts")
            return texts

        results = []
        total = len(texts)

        for i, text in enumerate(texts):
            translated = self.translate_text(text, target_lang, source_lang)
            results.append(translated)

            if progress_callback and i % 10 == 0:
                progress_callback(i + 1, total)

        if progress_callback:
            progress_callback(total, total)

        return results

    def clear_cache(self):
        """Clear the translation cache."""
        self._cache.clear()
        logger.info("Translation cache cleared")

    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages."""
        return ["tamil", "hindi", "english"]

    def get_model_info(self) -> Dict[str, str]:
        """Get information about the translation service."""
        return {
            "status": "loaded" if self.enabled else "not_loaded",
            "engine": "Google Translate",
            "supported_languages": ", ".join(self.get_supported_languages()),
        }
