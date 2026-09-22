from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from domain.models.chat import Chat


@dataclass
class ChatDTO:
    id: int
    telegram_chat_id: int
    name: str
    type: str
    total_messages: int
    created_at: Optional[datetime] = None

    @classmethod
    def from_domain(cls, chat: Chat) -> "ChatDTO":
        return cls(
            id=chat.id,
            telegram_chat_id=chat.telegram_chat_id,
            name=chat.name,
            type=chat.type,
            total_messages=chat.total_messages,
            created_at=chat.created_at,
        )
