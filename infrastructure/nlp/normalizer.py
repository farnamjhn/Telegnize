import re
from typing import Optional, Tuple
import hazm
import nltk


class TextNormalizer:
    """Multilingual text normalization engine using Hazm (Persian), NLTK (English), and Regex."""

    _instance: Optional["TextNormalizer"] = None

    def __init__(self):
        self._hazm_normalizer = hazm.Normalizer()
        # Regex patterns
        self._persian_pattern = re.compile(r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]")
        self._latin_pattern = re.compile(r"[a-zA-Z]")
        self._url_pattern = re.compile(r"https?://\S+|www\.\S+")
        self._whitespace_pattern = re.compile(r"\s+")
        self._repeated_chars_pattern = re.compile(r"(.)\1{2,}")

    @classmethod
    def get_instance(cls) -> "TextNormalizer":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def detect_language(self, text: str) -> str:
        """Detects language script of text: 'fa', 'en', 'mixed', or 'other'."""
        if not text or not text.strip():
            return "unknown"

        persian_count = len(self._persian_pattern.findall(text))
        latin_count = len(self._latin_pattern.findall(text))

        if persian_count > 0 and latin_count > 0:
            if persian_count > latin_count * 2:
                return "fa"
            elif latin_count > persian_count * 2:
                return "en"
            return "mixed"
        elif persian_count > 0:
            return "fa"
        elif latin_count > 0:
            return "en"
        return "other"

    def clean_general(self, text: str) -> str:
        """Performs general regex cleaning (whitespace, repeated punctuation)."""
        if not text:
            return ""
        # Collapse multiple spaces and linebreaks to single space
        cleaned = self._whitespace_pattern.sub(" ", text).strip()
        # Collapse 3+ repeated characters to at most 2 (e.g. "سللللام" -> "سلام")
        cleaned = self._repeated_chars_pattern.sub(r"\1\1", cleaned)
        return cleaned

    def normalize_persian(self, text: str) -> str:
        """Normalizes Persian text using Hazm and custom character refinements."""
        if not text:
            return ""
        # Hazm handles ZWNJ (half-space), Yeh/Kaf harmonization, and basic formatting
        hazm_normalized = self._hazm_normalizer.normalize(text)
        return self.clean_general(hazm_normalized)

    def normalize_english(self, text: str) -> str:
        """Normalizes English text using lowercase and general cleanup."""
        if not text:
            return ""
        cleaned = text.lower()
        return self.clean_general(cleaned)

    def normalize(self, text: str) -> Tuple[str, str]:
        """Detects language and returns (normalized_text, detected_language)."""
        if not text or not text.strip():
            return "", "unknown"

        lang = self.detect_language(text)

        if lang == "fa":
            norm_text = self.normalize_persian(text)
        elif lang == "en":
            norm_text = self.normalize_english(text)
        elif lang == "mixed":
            # For mixed, apply Hazm first (as it preserves English while fixing Persian glyphs), then general cleanup
            norm_text = self.clean_general(self._hazm_normalizer.normalize(text))
        else:
            norm_text = self.clean_general(text)

        return norm_text, lang

    def word_count(self, text: str) -> int:
        """Counts words using unicode-aware regex."""
        if not text:
            return 0
        return len(re.findall(r"[\w]+", text))

    def is_question(self, text: str) -> bool:
        """Checks if text contains English '?' or Persian '؟'."""
        if not text:
            return False
        return "?" in text or "؟" in text


def get_normalizer() -> TextNormalizer:
    return TextNormalizer.get_instance()
