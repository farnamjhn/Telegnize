from abc import ABC, abstractmethod
from typing import List, Optional

from domain.models.message import Message
from domain.models.analysis import LayaDecisionResult


class IMessageRepository(ABC):
    @abstractmethod
    def save(self, message: Message) -> None:
        """Saves a message."""
        pass

    @abstractmethod
    def save_batch(self, messages: List[Message]) -> None:
        """Saves a batch of messages."""
        pass

    @abstractmethod
    def get_by_id(self, message_id: int) -> Optional[Message]:
        """Gets the message with specified id."""
        pass

    @abstractmethod
    def get_by_telegram_id(self, message_telegram_id: int, chat_id: Optional[int] = None) -> Optional[Message]:
        """Gets the message using telegram_msg_id and optional chat_id."""
        pass

    @abstractmethod
    def get_all_orderd(self) -> List[Message]:
        """Gets all the messages from the database ordered by timestamp."""
        pass

    @abstractmethod
    def get_all_ordered(self) -> List[Message]:
        """Alias for get_all_orderd."""
        pass

    @abstractmethod
    def get_by_chat(
        self,
        chat_id: int,
        limit: int = 100,
        offset: int = 0,
        sender_id: Optional[str] = None,
    ) -> List[Message]:
        """Gets messages for a given chat with pagination and optional sender filter."""
        pass

    @abstractmethod
    def count_by_chat(self, chat_id: int) -> int:
        """Counts total messages in a chat."""
        pass

    @abstractmethod
    def get_chat_timeline(self, chat_id: int) -> List[Message]:
        """Gets all messages for a chat ordered chronologically."""
        pass

    @abstractmethod
    def save_laya_decision(self, decision: LayaDecisionResult) -> None:
        """Saves or updates a Laya schematic decision result."""
        pass

    @abstractmethod
    def get_laya_decisions(self, target_type: str, target_id: int) -> List[LayaDecisionResult]:
        """Gets saved Laya decisions for a given target ('message' or 'chat')."""
        pass
