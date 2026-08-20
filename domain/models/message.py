from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from enum import Enum
from domain.models.dict.lexicons import LOW_INVESTMENT_TOKENS
import re

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
    reply_to_msg_id: int
    timestamp: datetime
    text: str
    content_type: ContentType = ContentType.TEXT
    reply_to_id: Optional[MessageId] = None
    is_forwarded: bool = False

    @property
    def is_natural_text(self) -> bool:
        """Forwarded messages and media captions behave differently psychologically."""
        return self.content_type == ContentType.TEXT and not self.is_forwarded and bool(self.text.strip())

    @property
    def word_count(self) -> int:
        if not self.text:
            return 0
        return len(re.findall(r"\b\w+\b", self.text))
    
    @property
    def char_count(self):
        return len(self.text)

    @property
    def is_question(self):
        return "?" in self.text

    @property
    def exclamation_count(self):
        return self.text.count("!")

    @property
    def is_cold_closure(self) -> bool:
        clean = re.sub(r"[^\w\s]", "", self.text.strip().lower())
        return clean in LOW_INVESTMENT_TOKENS