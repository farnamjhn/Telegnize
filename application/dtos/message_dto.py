from dataclasses import dataclass
from datetime import datetime

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

    @classmethod
    def from_domain(cls, message: Message) -> "MessageDTO":
        return cls(
            id=message.id,
            sender_id=message.sender_id,
            sender_name=message.sender_name,
            timestamp=message.timestamp,
            text=message.text,
            word_count=message.word_count,
            is_question=message.is_question,
        )