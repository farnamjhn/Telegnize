"""Port for chat storage."""

from abc import ABC, abstractmethod

from domain.models.chat import Chat


class IChatRepository(ABC):
    @abstractmethod
    def save(self, chat: Chat) -> Chat:
        """Inserts or updates a chat and returns it with its assigned id."""

    @abstractmethod
    def get_by_id(self, chat_id: int) -> Chat | None:
        """Gets a chat by its Telegnize identifier."""

    @abstractmethod
    def get_by_telegram_id(self, telegram_chat_id: int) -> Chat | None:
        """Gets a chat by the identifier carried in the export file."""

    @abstractmethod
    def list_all(self) -> list[Chat]:
        """Lists every imported chat, most recent first."""

    @abstractmethod
    def update_message_count(self, chat_id: int, count: int) -> None:
        """Records how many messages a chat holds."""

    @abstractmethod
    def delete(self, chat_id: int) -> bool:
        """Deletes a chat and, by cascade, its messages and decisions."""
