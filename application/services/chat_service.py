"""Reads and removes imported chats."""


from application.dtos.chat_dto import ChatDTO
from domain.errors import ChatNotFoundError
from domain.repository.chat_repository import IChatRepository


class ChatService:
    def __init__(self, chat_repo: IChatRepository) -> None:
        self._chats = chat_repo

    def list_chats(self) -> list[ChatDTO]:
        return [ChatDTO.from_domain(chat) for chat in self._chats.list_all()]

    def get_chat(self, chat_id: int) -> ChatDTO:
        """Raises ChatNotFoundError if the chat has not been imported."""
        chat = self._chats.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundError(chat_id)
        return ChatDTO.from_domain(chat)

    def delete_chat(self, chat_id: int) -> None:
        """Deletes a chat and its messages.

        Raises:
            ChatNotFoundError: if the chat has not been imported.
        """
        if not self._chats.delete(chat_id):
            raise ChatNotFoundError(chat_id)
