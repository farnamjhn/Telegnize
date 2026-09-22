"""Chat-shaped payloads."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from domain.models.chat import Chat


class ChatDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_chat_id: int
    name: str
    type: str
    total_messages: int
    created_at: datetime | None = None

    @classmethod
    def from_domain(cls, chat: Chat) -> "ChatDTO":
        return cls.model_validate(chat)


class ImportSummaryDTO(BaseModel):
    """What an ingestion run produced."""

    chat: ChatDTO
    total_messages: int
