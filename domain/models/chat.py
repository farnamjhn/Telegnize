"""The Chat entity: one imported Telegram conversation."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Chat:
    """An imported Telegram conversation.

    ``id`` is Telegnize's own identifier and is 0 until the chat is persisted;
    ``telegram_chat_id`` is the identifier carried by the export file.
    """

    id: int
    telegram_chat_id: int
    name: str
    type: str = "personal_chat"
    total_messages: int = 0
    created_at: datetime | None = None

    @property
    def is_persisted(self) -> bool:
        return self.id > 0
