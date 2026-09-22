from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from domain.models.message import Message


@dataclass
class MessageDTO:
    id: int
    sender_id: str
    sender_name: str
    timestamp: datetime
    text: str
    word_count: int
    is_question: bool
    chat_id: int = 1
    normalized_text: str = ""
    language: str = "unknown"
    content_type: str = "text"
    reply_to_msg_id: Optional[int] = None
    is_forwarded: bool = False
    is_cold_closure: bool = False

    @classmethod
    def from_domain(cls, message: Message) -> "MessageDTO":
        content_type_str = (
            message.content_type.value
            if hasattr(message.content_type, "value")
            else str(message.content_type)
        )
        return cls(
            id=message.id,
            chat_id=message.chat_id,
            sender_id=message.sender_id,
            sender_name=message.sender_name,
            timestamp=message.timestamp,
            text=message.text,
            normalized_text=message.normalized_text or message.text,
            language=message.language,
            word_count=message.word_count,
            is_question=message.is_question,
            content_type=content_type_str,
            reply_to_msg_id=message.reply_to_msg_id,
            is_forwarded=message.is_forwarded,
            is_cold_closure=message.is_cold_closure,
        )