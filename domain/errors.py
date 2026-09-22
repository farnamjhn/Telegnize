"""Errors the application raises, independent of any transport.

Routers translate these into HTTP status codes, so services never have to
reach for ``HTTPException`` and stay usable outside a web request.
"""


class TelegnizeError(Exception):
    """Base class for every error Telegnize raises deliberately."""


class NotFoundError(TelegnizeError):
    """A requested record does not exist."""


class ChatNotFoundError(NotFoundError):
    def __init__(self, chat_id: int) -> None:
        super().__init__(f"Chat {chat_id} not found.")
        self.chat_id = chat_id


class MessageNotFoundError(NotFoundError):
    def __init__(self, message_id: int) -> None:
        super().__init__(f"Message {message_id} not found.")
        self.message_id = message_id


class InvalidExportError(TelegnizeError):
    """The supplied file is not a readable Telegram export."""
