"""Multilingual text normalization.

Persian goes through ``hazm`` (ZWNJ/half-space handling, Arabic-to-Persian
character harmonisation); everything else goes through case folding and shared
regex cleanup. The normalizer is stateless apart from the compiled patterns and
the hazm instance, which is why a single shared instance is enough.
"""

import re

import hazm

from application.ports.text_normalizer import ITextNormalizer
from domain.models.language import Language

_PERSIAN_SCRIPT = re.compile(r"[؀-ۿﭐ-﷿ﹰ-﻿]")
_LATIN_SCRIPT = re.compile(r"[a-zA-Z]")
_WHITESPACE = re.compile(r"\s+")
_REPEATED_CHARS = re.compile(r"(.)\1{2,}")
_WORDS = re.compile(r"\w+", re.UNICODE)

#: A script is treated as dominant when it outnumbers the other this many times.
_DOMINANCE_RATIO = 2

#: Question marks recognised across supported languages.
QUESTION_MARKS = ("?", "؟")


class TextNormalizer(ITextNormalizer):
    """Normalizes message text and reports the script it is written in."""

    def __init__(self) -> None:
        self._hazm = hazm.Normalizer()

    # --- detection --------------------------------------------------------
    def detect_language(self, text: str) -> Language:
        """Classifies text by the script it is dominantly written in."""
        if not text or not text.strip():
            return Language.UNKNOWN

        persian = len(_PERSIAN_SCRIPT.findall(text))
        latin = len(_LATIN_SCRIPT.findall(text))

        if persian and latin:
            if persian > latin * _DOMINANCE_RATIO:
                return Language.PERSIAN
            if latin > persian * _DOMINANCE_RATIO:
                return Language.ENGLISH
            return Language.MIXED
        if persian:
            return Language.PERSIAN
        if latin:
            return Language.ENGLISH
        return Language.OTHER

    # --- normalization ----------------------------------------------------
    def clean(self, text: str) -> str:
        """Collapses whitespace and runs of three or more repeated characters."""
        if not text:
            return ""
        collapsed = _WHITESPACE.sub(" ", text).strip()
        return _REPEATED_CHARS.sub(r"\1\1", collapsed)

    def normalize_persian(self, text: str) -> str:
        return self.clean(self._hazm.normalize(text)) if text else ""

    def normalize_english(self, text: str) -> str:
        return self.clean(text.lower()) if text else ""

    def normalize(self, text: str) -> tuple[str, Language]:
        """Returns the normalized text and the language it was detected as."""
        if not text or not text.strip():
            return "", Language.UNKNOWN

        language = self.detect_language(text)
        if language is Language.PERSIAN:
            return self.normalize_persian(text), language
        if language is Language.ENGLISH:
            return self.normalize_english(text), language
        if language is Language.MIXED:
            # hazm fixes Persian glyphs and leaves Latin runs intact, so it is
            # safe to apply to mixed text; case is left alone to keep the two
            # halves consistent with each other.
            return self.clean(self._hazm.normalize(text)), language
        return self.clean(text), language

    # --- metrics ----------------------------------------------------------
    @staticmethod
    def word_count(text: str) -> int:
        """Counts words, treating Persian and Latin word characters alike."""
        return len(_WORDS.findall(text)) if text else 0

    @staticmethod
    def is_question(text: str) -> bool:
        """Whether the text carries an ASCII or Persian question mark."""
        return bool(text) and any(mark in text for mark in QUESTION_MARKS)


_shared_normalizer: TextNormalizer | None = None


def get_normalizer() -> TextNormalizer:
    """Returns the process-wide normalizer, building it on first use.

    ``hazm.Normalizer()`` loads word lists, so it is built once and reused.
    """
    global _shared_normalizer
    if _shared_normalizer is None:
        _shared_normalizer = TextNormalizer()
    return _shared_normalizer
