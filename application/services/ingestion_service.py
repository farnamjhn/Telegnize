"""Imports Telegram exports into storage."""

import logging

from application.dtos.chat_dto import (
    ChatDTO,
    ImportSummaryDTO,
    RederiveSummaryDTO,
)
from application.ports.export_reader import (
    DEFAULT_BATCH_SIZE,
    ExportFormatError,
    FileSource,
    IExportReader,
)
from domain.errors import ChatNotFoundError, InvalidExportError
from domain.models.chat import Chat
from domain.repository.chat_repository import IChatRepository
from domain.repository.message_repository import IMessageRepository

logger = logging.getLogger(__name__)


class IngestionService:
    """Streams an export into the database one batch at a time.

    Memory use is bounded by ``batch_size`` regardless of how large the export
    is, so a multi-gigabyte file imports in the same footprint as a small one.
    """

    def __init__(
        self,
        chat_repo: IChatRepository,
        message_repo: IMessageRepository,
        reader: IExportReader,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._chats = chat_repo
        self._messages = message_repo
        self._reader = reader
        self._batch_size = batch_size

    def ingest_export(
        self,
        source: FileSource,
        override_name: str | None = None,
        batch_size: int | None = None,
    ) -> ImportSummaryDTO:
        """Imports one export and returns what was written.

        Raises:
            InvalidExportError: if the file is not readable Telegram JSON.
        """
        try:
            metadata = self._reader.extract_metadata(source)
        except ExportFormatError as error:
            raise InvalidExportError(str(error)) from error

        chat = self._chats.save(
            Chat(
                id=0,
                telegram_chat_id=metadata.telegram_chat_id,
                name=override_name or metadata.name,
                type=metadata.type,
            )
        )

        total = 0
        try:
            batches = self._reader.stream_messages(
                source,
                chat_id=chat.id,
                batch_size=batch_size or self._batch_size,
            )
            for batch in batches:
                total += self._messages.save_batch(batch)
        except ExportFormatError as error:
            raise InvalidExportError(str(error)) from error

        # The export is the source of truth for the chat's size, so recount
        # rather than adding to whatever a previous import left behind.
        total_in_chat = self._messages.count_by_chat(chat.id)
        self._chats.update_message_count(chat.id, total_in_chat)
        chat.total_messages = total_in_chat

        logger.info("Imported %d messages into chat %s.", total, chat.id)
        return ImportSummaryDTO(chat=ChatDTO.from_domain(chat), total_messages=total)

    def rederive(self, chat_id: int, batch_size: int | None = None) -> RederiveSummaryDTO:
        """Recomputes every derived column from the text already stored.

        Word counts, markers and the whole-message readings are written at
        ingest, so a chat imported before a marker existed carries a zero for
        it — not because the wording was absent but because nothing looked.
        Every one of them is a pure function of text this database already
        holds, so they can be derived again in place; re-importing the export
        is not needed and neither is the export.

        The one thing this cannot recover is a voice note's length, which is
        in the export rather than in the text, and so needs a fresh import.

        Raises:
            ChatNotFoundError: if the chat has not been imported.
        """
        if self._chats.get_by_id(chat_id) is None:
            raise ChatNotFoundError(chat_id)

        size = batch_size or self._batch_size
        rewritten = 0
        batch: list = []
        # save_batch upserts on (chat_id, telegram_msg_id) and recomputes every
        # derived column from the entity, so a round trip through it is the
        # whole re-derivation. Batched so a large chat stays bounded in memory.
        for message in self._messages.iter_chat_timeline(chat_id):
            batch.append(message)
            if len(batch) >= size:
                rewritten += self._messages.save_batch(batch)
                batch = []
        if batch:
            rewritten += self._messages.save_batch(batch)

        logger.info("Re-derived %d messages in chat %s.", rewritten, chat_id)
        return RederiveSummaryDTO(chat_id=chat_id, messages_rewritten=rewritten)
