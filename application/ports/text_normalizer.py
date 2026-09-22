"""Port for text normalization."""

from abc import ABC, abstractmethod

from domain.models.language import Language


class ITextNormalizer(ABC):
    @abstractmethod
    def normalize(self, text: str) -> tuple[str, Language]:
        """Returns the normalized text and the language it was detected as."""

    @abstractmethod
    def detect_language(self, text: str) -> Language:
        """Classifies text by the script it is dominantly written in."""
