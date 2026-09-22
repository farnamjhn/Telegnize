from abc import ABC, abstractmethod
from typing import List, Optional

from domain.models.chat import Chat


class IChatRepository(ABC):
    @abstractmethod
    def save(self, chat: Chat) -> Chat:
        """Saves or updates a chat."""
        pass

    @abstractmethod
    def get_by_id(self, chat_id: int) -> Optional[Chat]:
        """Gets a chat by internal ID."""
        pass

    @abstractmethod
    def get_by_telegram_id(self, telegram_chat_id: int) -> Optional[Chat]:
        """Gets a chat by Telegram chat ID."""
        pass

    @abstractmethod
    def list_all(self) -> List[Chat]:
        """Lists all stored chats."""
        pass

    @abstractmethod
    def update_message_count(self, chat_id: int, count: int) -> None:
        """Updates total message count for a chat."""
        pass

    @abstractmethod
    def delete(self, chat_id: int) -> bool:
        """Deletes a chat and associated data."""
        pass
