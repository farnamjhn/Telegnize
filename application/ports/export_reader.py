"""Port for reading chat exports.

Telegram's JSON is one export format among several a user might have; keeping
the reader behind an interface means adding another format is a new adapter
rather than a change to the ingestion flow.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from domain.models.message import Message

#: A path to an export, or an already-open binary stream of one.
FileSource = str | Path | BinaryIO

DEFAULT_BATCH_SIZE = 500


class ExportFormatError(ValueError):
    """The source is not a readable export in this reader's format."""


@dataclass(frozen=True)
class ChatMetadata:
    """The header of an export: everything before the message array."""

    name: str = "Exported Chat"
    type: str = "personal_chat"
    telegram_chat_id: int = 0


class IExportReader(ABC):
    @abstractmethod
    def extract_metadata(self, source: FileSource) -> ChatMetadata:
        """Reads the export header without consuming the message array.

        Raises:
            ExportFormatError: if the source cannot be read as an export.
        """

    @abstractmethod
    def stream_messages(
        self,
        source: FileSource,
        chat_id: int = 1,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> Iterator[list[Message]]:
        """Yields batches of parsed messages, holding one batch at a time.

        Raises:
            ExportFormatError: if the source is malformed.
        """
