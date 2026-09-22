"""Message-shaped payloads."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from domain.models.language import Language
from domain.models.message import ContentType, Message


class MessageDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    telegram_msg_id: int
    sender_id: str
    sender_name: str
    timestamp: datetime
    text: str
    normalized_text: str
    language: Language
    content_type: ContentType
    reply_to_msg_id: int | None = None
    is_forwarded: bool = False
    # Derived on the entity; surfaced here so clients need not recompute them.
    word_count: int
    char_count: int
    is_question: bool
    is_cold_closure: bool

    @classmethod
    def from_domain(cls, message: Message) -> "MessageDTO":
        return cls.model_validate(message)


class MessageCreateDTO(BaseModel):
    """A message submitted directly rather than imported from an export."""

    telegram_msg_id: int
    sender_id: str
    sender_name: str
    timestamp: datetime
    text: str = ""
    chat_id: int = 1
    reply_to_msg_id: int | None = None
    content_type: ContentType = ContentType.TEXT
    is_forwarded: bool = False
