"""Streaming parser for Telegram's JSON chat exports.

Exports routinely run to hundreds of megabytes, so messages are pulled off the
file with ``ijson`` one at a time and handed on in batches; the whole document
is never held in memory.
"""

import json
import logging
from collections.abc import Iterator, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO

import ijson

from application.ports.export_reader import (
    DEFAULT_BATCH_SIZE,
    ChatMetadata,
    ExportFormatError,
    FileSource,
    IExportReader,
)
from domain.models.message import ContentType, Message
from infrastructure.nlp.normalizer import TextNormalizer, get_normalizer

logger = logging.getLogger(__name__)

_TIMESTAMP_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")

# Telegram's media_type values, mapped onto the content types Telegnize keeps.
_MEDIA_TYPES: dict[str, ContentType] = {
    "voice_message": ContentType.VOICE,
    "sticker": ContentType.STICKER,
    "photo": ContentType.PHOTO,
    "document": ContentType.DOCUMENT,
    "video_file": ContentType.DOCUMENT,
    "video_message": ContentType.DOCUMENT,
    "animation": ContentType.DOCUMENT,
    "audio_file": ContentType.DOCUMENT,
}


class TelegramJsonParser(IExportReader):
    """Turns Telegram export JSON into domain :class:`Message` entities."""

    def __init__(self, normalizer: TextNormalizer | None = None) -> None:
        self._normalizer = normalizer or get_normalizer()

    @property
    def normalizer(self) -> TextNormalizer:
        return self._normalizer

    # --- single messages --------------------------------------------------
    def parse_message(self, payload: dict[str, Any], chat_id: int = 1) -> Message | None:
        """Parses one exported message, or returns None if it is not one.

        Service entries (joins, title changes), malformed ids, and messages
        without a usable timestamp are skipped rather than guessed at.
        """
        if not isinstance(payload, dict) or payload.get("type") != "message":
            return None

        telegram_msg_id = _as_int(payload.get("id"))
        if telegram_msg_id is None:
            logger.debug("Skipping message with unusable id: %r", payload.get("id"))
            return None

        timestamp = self._parse_timestamp(payload)
        if timestamp is None:
            logger.debug("Skipping message %s with no parsable date.", telegram_msg_id)
            return None

        text = self._extract_text(payload.get("text", ""))
        normalized_text, language = self._normalizer.normalize(text)

        return Message(
            id=0,
            chat_id=chat_id,
            telegram_msg_id=telegram_msg_id,
            sender_id=self._extract_sender_id(payload),
            sender_name=str(payload.get("from") or payload.get("actor") or "Unknown"),
            timestamp=timestamp,
            text=text,
            normalized_text=normalized_text,
            language=language,
            content_type=self._content_type(payload),
            reply_to_msg_id=_as_int(
                payload.get("reply_to_message_id", payload.get("reply_to_msg_id"))
            ),
            is_forwarded=bool(
                payload.get("forwarded_from")
                or payload.get("forwarded_from_id")
                or payload.get("is_forwarded")
            ),
        )

    # --- whole documents (small inputs only) ------------------------------
    def parse_data(
        self,
        data: dict[str, Any] | Sequence[dict[str, Any]],
        chat_id: int = 1,
    ) -> list[Message]:
        """Parses an already-decoded export.

        Only for payloads small enough to hold in memory; use
        :meth:`stream_messages` for files.
        """
        if isinstance(data, dict):
            raw_messages = data.get("messages", [data])
        elif isinstance(data, (list, tuple)):
            raw_messages = data
        else:
            raise ValueError("Export data must be a mapping or a sequence.")

        parsed = (self.parse_message(item, chat_id) for item in raw_messages)
        return [message for message in parsed if message is not None]

    def parse_json(self, json_str: str, chat_id: int = 1) -> list[Message]:
        return self.parse_data(json.loads(json_str), chat_id=chat_id)

    def parse_file(self, path: str | Path, chat_id: int = 1) -> list[Message]:
        """Reads a whole export into memory; prefer :meth:`stream_messages`."""
        with open(path, encoding="utf-8") as handle:
            return self.parse_data(json.load(handle), chat_id=chat_id)

    # --- streaming --------------------------------------------------------
    def extract_metadata(self, source: FileSource) -> ChatMetadata:
        """Reads the export header without touching the message array."""
        with _as_binary_stream(source) as stream:
            fields: dict[str, Any] = {}
            try:
                for prefix, event, value in ijson.parse(stream):
                    if prefix == "messages":
                        break
                    if prefix in ("name", "type") and event == "string":
                        fields[prefix] = value
                    elif prefix == "id" and event == "number":
                        fields["telegram_chat_id"] = int(value)
            except ijson.JSONError as error:
                raise ExportFormatError(
                    f"Not a readable Telegram export: {error}"
                ) from error
        return ChatMetadata(**fields)

    def stream_messages(
        self,
        source: FileSource,
        chat_id: int = 1,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> Iterator[list[Message]]:
        """Yields batches of parsed messages, holding one batch at a time."""
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1.")

        with _as_binary_stream(source) as stream:
            batch: list[Message] = []
            try:
                for item in ijson.items(stream, "messages.item"):
                    message = self.parse_message(item, chat_id=chat_id)
                    if message is None:
                        continue
                    batch.append(message)
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
            except ijson.JSONError as error:
                raise ExportFormatError(f"Malformed Telegram export: {error}") from error
            if batch:
                yield batch

    # --- field extraction -------------------------------------------------
    @staticmethod
    def _extract_sender_id(payload: dict[str, Any]) -> str:
        for key in ("from_id", "actor_id", "from"):
            value = payload.get(key)
            if value is not None:
                return str(value)
        return "unknown"

    @staticmethod
    def _extract_text(value: Any) -> str:
        """Flattens Telegram's text field, which may be a string or entity list."""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "".join(
                part if isinstance(part, str) else str(part.get("text", ""))
                for part in value
                if isinstance(part, (str, dict))
            )
        return "" if value is None else str(value)

    @staticmethod
    def _parse_timestamp(payload: dict[str, Any]) -> datetime | None:
        """Reads ``date``, falling back to ``date_unixtime``.

        ``date`` is preferred because it is the local wall-clock time the
        conversation actually happened in, which is what hour-of-day analytics
        is about; ``date_unixtime`` is UTC and would shift those buckets.
        """
        raw_date = payload.get("date")
        if isinstance(raw_date, str) and raw_date:
            try:
                return datetime.fromisoformat(raw_date)
            except ValueError:
                pass
            for fmt in _TIMESTAMP_FORMATS:
                try:
                    return datetime.strptime(raw_date, fmt)
                except ValueError:
                    continue

        unixtime = _as_int(payload.get("date_unixtime"))
        if unixtime is not None:
            return datetime.fromtimestamp(unixtime)
        return None

    @staticmethod
    def _content_type(payload: dict[str, Any]) -> ContentType:
        media_type = payload.get("media_type")
        if media_type in _MEDIA_TYPES:
            return _MEDIA_TYPES[media_type]
        if "sticker_emoji" in payload:
            return ContentType.STICKER
        if "photo" in payload:
            return ContentType.PHOTO
        if "file" in payload:
            return ContentType.DOCUMENT
        return ContentType.TEXT


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class _as_binary_stream:
    """Opens ``source`` for binary reading, rewinding streams given to us.

    Closes the file only if it was opened here, so a caller's upload stream
    stays usable afterwards.
    """

    def __init__(self, source: FileSource) -> None:
        self._source = source
        self._opened: BinaryIO | None = None

    def __enter__(self) -> BinaryIO:
        if isinstance(self._source, (str, Path)):
            self._opened = open(self._source, "rb")
            return self._opened
        stream = self._source
        if hasattr(stream, "seek") and getattr(stream, "seekable", lambda: False)():
            stream.seek(0)
        return stream

    def __exit__(self, *exc_info) -> None:
        if self._opened is not None:
            self._opened.close()
            self._opened = None
