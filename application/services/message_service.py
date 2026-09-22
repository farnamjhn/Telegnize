"""Reads and writes individual messages.

Routers used to build domain entities and call repositories directly; this
keeps that work in one place so the HTTP layer only translates.
"""

import logging

from application.dtos.message_dto import MessageCreateDTO, MessageDTO
from application.ports.text_normalizer import ITextNormalizer
from domain.errors import MessageNotFoundError
from domain.models.message import Message
from domain.repository.message_repository import IMessageRepository

logger = logging.getLogger(__name__)


class MessageService:
    def __init__(
        self, message_repo: IMessageRepository, normalizer: ITextNormalizer
    ) -> None:
        self._messages = message_repo
        self._normalizer = normalizer

    def list_messages(
        self,
        chat_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
        sender_id: str | None = None,
    ) -> list[MessageDTO]:
        messages = self._messages.list_messages(
            chat_id=chat_id, limit=limit, offset=offset, sender_id=sender_id
        )
        return [MessageDTO.from_domain(message) for message in messages]

    def get_message(self, message_id: int) -> MessageDTO:
        """Raises MessageNotFoundError if the message does not exist."""
        message = self._messages.get_by_id(message_id)
        if message is None:
            raise MessageNotFoundError(message_id)
        return MessageDTO.from_domain(message)

    def get_by_telegram_id(
        self, telegram_msg_id: int, chat_id: int | None = None
    ) -> MessageDTO:
        """Raises MessageNotFoundError if the message does not exist."""
        message = self._messages.get_by_telegram_id(telegram_msg_id, chat_id=chat_id)
        if message is None:
            raise MessageNotFoundError(telegram_msg_id)
        return MessageDTO.from_domain(message)

    def create_message(self, payload: MessageCreateDTO) -> MessageDTO:
        """Stores a single message, normalizing its text on the way in."""
        normalized_text, language = self._normalizer.normalize(payload.text)
        message = Message(
            id=0,
            chat_id=payload.chat_id,
            telegram_msg_id=payload.telegram_msg_id,
            sender_id=payload.sender_id,
            sender_name=payload.sender_name,
            timestamp=payload.timestamp,
            text=payload.text,
            normalized_text=normalized_text,
            language=language,
            content_type=payload.content_type,
            reply_to_msg_id=payload.reply_to_msg_id,
            is_forwarded=payload.is_forwarded,
        )
        self._messages.save(message)
        return self.get_by_telegram_id(
            payload.telegram_msg_id, chat_id=payload.chat_id
        )
