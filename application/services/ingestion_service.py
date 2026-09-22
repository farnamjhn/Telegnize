from pathlib import Path
from typing import Any, BinaryIO, Dict, Optional, Union

from application.dtos.chat_dto import ChatDTO
from domain.models.chat import Chat
from domain.repository.chat_repository import IChatRepository
from domain.repository.message_repository import IMessageRepository
from infrastructure.parser.telegram_parser import TelegramJsonParser


class IngestionService:
    """Orchestrates streaming ingestion of Telegram JSON exports using ijson and NLP normalizers."""

    def __init__(
        self,
        chat_repo: IChatRepository,
        message_repo: IMessageRepository,
        parser: Optional[TelegramJsonParser] = None,
    ):
        self.chat_repo = chat_repo
        self.message_repo = message_repo
        self.parser = parser or TelegramJsonParser()

    def ingest_export(
        self,
        file_input: Union[str, Path, BinaryIO],
        override_name: Optional[str] = None,
        batch_size: int = 500,
    ) -> Dict[str, Any]:
        """Streams, normalizes, and persists a Telegram chat export."""
        # 1. Extract chat metadata without loading full file
        meta = self.parser.extract_chat_metadata(file_input)
        telegram_chat_id = meta.get("id", 0)
        chat_name = override_name or meta.get("name", "Imported Chat")
        chat_type = meta.get("type", "personal_chat")

        # 2. Persist or retrieve Chat record
        chat = Chat(
            id=0,
            telegram_chat_id=telegram_chat_id,
            name=chat_name,
            type=chat_type,
            total_messages=0,
        )
        saved_chat = self.chat_repo.save(chat)

        # 3. Stream messages in batches
        # If file_input is a stream, seek(0) if supported
        if hasattr(file_input, "seek"):
            try:
                file_input.seek(0)
            except Exception:
                pass

        total_imported = 0
        for batch in self.parser.stream_messages(file_input, chat_id=saved_chat.id, batch_size=batch_size):
            self.message_repo.save_batch(batch)
            total_imported += len(batch)

        # 4. Update total message count on chat
        self.chat_repo.update_message_count(saved_chat.id, total_imported)
        saved_chat.total_messages = total_imported

        return {
            "chat": ChatDTO.from_domain(saved_chat),
            "total_messages": total_imported,
        }
