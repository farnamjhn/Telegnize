from abc import ABC, abstractmethod
from typing import List, Optional

from domain.models.message import Message

class IMessageRepository(ABC):
    @abstractmethod
    def save(self, message: Message) -> None:
        """Saves a message"""
        pass

    @abstractmethod
    def save_batch(self, messages: List[Message]) -> None:
        """Saves a batch of messages"""
        pass

    @abstractmethod
    def get_by_id(self, message_id: int) -> Optional[Message]:
        """Gets the message with specified id"""
        pass

    @abstractmethod
    def get_by_telegram_id(self, message_telegram_id: int) -> Optional[Message]:
        """There is a field in Message data type
        that is named telegram_msg_id
        which is associated with each Json object
        exported from telegram, this method gets the message using that id"""
        pass

    @abstractmethod
    def get_all_orderd(self) -> List[Message]:
        """Gets all the messages from the database ordered by timestamp"""
        pass
