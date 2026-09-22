from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from enum import Enum
import re

from domain.models.dict.lexicons import LOW_INVESTMENT_TOKENS


class ContentType(Enum):
    TEXT = "text"
    PHOTO = "photo"
    VOICE = "voice_message"
    STICKER = "sticker"
    DOCUMENT = "document"


@dataclass(frozen=True)
class MessageId:
    """Telegram Message ID."""
    value: int


@dataclass
class Message:
    id: int
    telegram_msg_id: int
    sender_id: str
    sender_name: str
    reply_to_msg_id: Optional[int]
    timestamp: datetime
    text: str
    content_type: ContentType = ContentType.TEXT
    reply_to_id: Optional[MessageId] = None
    is_forwarded: bool = False
    chat_id: int = 0
    raw_text: str = ""
    normalized_text: str = ""
    language: str = "unknown"

    def __post_init__(self):
        if not self.raw_text and self.text:
            self.raw_text = self.text
        if not self.normalized_text and self.text:
            self.normalized_text = self.text
        if not self.text and self.raw_text:
            self.text = self.raw_text

    @property
    def is_natural_text(self) -> bool:
        """Forwarded messages and media captions behave differently psychologically."""
        return self.content_type == ContentType.TEXT and not self.is_forwarded and bool(self.text.strip())

    @property
    def word_count(self) -> int:
        target = self.normalized_text or self.text
        if not target:
            return 0
        return len(re.findall(r"[\w]+", target))

    @property
    def char_count(self) -> int:
        target = self.normalized_text or self.text
        return len(target)

    @property
    def is_question(self) -> bool:
        target = self.text or self.raw_text
        return "?" in target or "؟" in target

    @property
    def exclamation_count(self) -> int:
        target = self.text or self.raw_text
        return target.count("!") + target.count("！")

    @property
    def is_cold_closure(self) -> bool:
        target = self.normalized_text or self.text
        clean = re.sub(r"[^\w\s]", "", target.strip().lower())
        return clean in LOW_INVESTMENT_TOKENS