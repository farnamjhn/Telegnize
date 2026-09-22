"""The Message entity: a single Telegram message and its behavioural traits."""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from domain.models.language import Language
from domain.models.lexicons import (
    AFFECTION_TOKENS,
    APOLOGY_TOKENS,
    COLLECTIVE_REFERENCE_TOKENS,
    GRATITUDE_TOKENS,
    LOW_INVESTMENT_TOKENS,
    SELF_REFERENCE_TOKENS,
)

_WORD_PATTERN = re.compile(r"\w+", re.UNICODE)
_PUNCTUATION_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)

#: Question marks recognised across the languages Telegnize supports.
QUESTION_MARKS = ("?", "؟")
#: Exclamation marks recognised across the languages Telegnize supports.
EXCLAMATION_MARKS = ("!", "！")

# Emoji are counted per character, so a joined sequence such as a family emoji
# counts once per person in it. Variation selectors and skin-tone modifiers are
# deliberately outside these ranges: they dress an emoji rather than being one,
# and counting them made "❤️" score twice.
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001F3FA"  # pictographs (up to, not including, skin tones)
    "\U0001F400-\U0001FAFF"  # emoticons, transport, supplemental, extended
    "\U0001F000-\U0001F0FF"  # mahjong, dominoes, playing cards
    "\U0001F1E6-\U0001F1FF"  # regional indicators (flags)
    "\U00002600-\U000027BF"  # miscellaneous symbols and dingbats
    "\U00002B00-\U00002BFF"  # arrows, stars, geometric shapes
    "]"
)


@dataclass(frozen=True)
class MessageMarkers:
    """Counts of the expressive markers one message carries.

    Each count is an observation about wording, not a measurement of feeling —
    see :mod:`domain.models.lexicons` for what the lists do and do not claim.
    """

    exclamations: int = 0
    emoji: int = 0
    affection: int = 0
    apology: int = 0
    gratitude: int = 0
    self_reference: int = 0
    collective_reference: int = 0


class ContentType(StrEnum):
    TEXT = "text"
    PHOTO = "photo"
    VOICE = "voice_message"
    STICKER = "sticker"
    DOCUMENT = "document"

    @classmethod
    def coerce(cls, value: "str | ContentType | None") -> "ContentType":
        """Maps an arbitrary tag onto the closed set, defaulting to TEXT."""
        if isinstance(value, cls):
            return value
        if not value:
            return cls.TEXT
        try:
            return cls(str(value))
        except ValueError:
            return cls.TEXT


@dataclass
class Message:
    """A Telegram message.

    ``text`` is the text exactly as exported; ``normalized_text`` is the
    normalizer's output and is what analysis should read. Everything else on
    this class is derived, so the entity stays the single definition of what
    "a question" or "a cold closure" means.
    """

    id: int
    telegram_msg_id: int
    sender_id: str
    sender_name: str
    timestamp: datetime
    text: str = ""
    chat_id: int = 1
    normalized_text: str = ""
    language: Language = Language.UNKNOWN
    content_type: ContentType = ContentType.TEXT
    reply_to_msg_id: int | None = None
    is_forwarded: bool = False

    def __post_init__(self) -> None:
        self.language = Language.coerce(self.language)
        self.content_type = ContentType.coerce(self.content_type)
        if not self.normalized_text:
            self.normalized_text = self.text

    @property
    def analysis_text(self) -> str:
        """The text downstream analysis should read."""
        return self.normalized_text or self.text

    @property
    def is_natural_text(self) -> bool:
        """Forwarded messages and media captions behave differently psychologically."""
        return (
            self.content_type == ContentType.TEXT
            and not self.is_forwarded
            and bool(self.text.strip())
        )

    @property
    def word_count(self) -> int:
        return len(_WORD_PATTERN.findall(self.analysis_text))

    @property
    def char_count(self) -> int:
        return len(self.analysis_text)

    @property
    def is_question(self) -> bool:
        return any(mark in self.text for mark in QUESTION_MARKS)

    @property
    def markers(self) -> MessageMarkers:
        """Counts the expressive markers in this message.

        Computed on each access rather than cached, because the bulk path
        (persisting a batch) reads it exactly once per message.
        """
        text = self.analysis_text
        if not text:
            return MessageMarkers()

        tokens = [token.lower() for token in _WORD_PATTERN.findall(text)]

        def occurrences(vocabulary: frozenset[str]) -> int:
            return sum(1 for token in tokens if token in vocabulary)

        return MessageMarkers(
            exclamations=sum(text.count(mark) for mark in EXCLAMATION_MARKS),
            emoji=len(_EMOJI_PATTERN.findall(text)),
            affection=occurrences(AFFECTION_TOKENS),
            apology=occurrences(APOLOGY_TOKENS),
            gratitude=occurrences(GRATITUDE_TOKENS),
            self_reference=occurrences(SELF_REFERENCE_TOKENS),
            collective_reference=occurrences(COLLECTIVE_REFERENCE_TOKENS),
        )

    @property
    def is_cold_closure(self) -> bool:
        """Whether the whole message is a low-investment acknowledgement."""
        stripped = _PUNCTUATION_PATTERN.sub("", self.analysis_text.strip().lower())
        return stripped in LOW_INVESTMENT_TOKENS
