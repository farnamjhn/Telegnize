"""Message query and single-message write endpoints.

Bulk import lives under ``/chats`` — it is an operation on a conversation, and
routing it through here meant a second, non-streaming copy of the same flow.
"""


from fastapi import APIRouter, Query, status

from application.dtos.message_dto import MessageCreateDTO, MessageDTO
from infrastructure.api.dependencies import MessageServiceDep, SettingsDep

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.get("", response_model=list[MessageDTO], summary="List messages")
def list_messages(
    message_service: MessageServiceDep,
    settings: SettingsDep,
    chat_id: int | None = Query(None, description="Restrict to one chat"),
    sender_id: str | None = Query(None, description="Restrict to one sender"),
    limit: int = Query(100, ge=1),
    offset: int = Query(0, ge=0),
) -> list[MessageDTO]:
    return message_service.list_messages(
        chat_id=chat_id,
        limit=min(limit, settings.max_page_size),
        offset=offset,
        sender_id=sender_id,
    )


@router.post(
    "",
    response_model=MessageDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Store a single message",
)
def create_message(
    payload: MessageCreateDTO, message_service: MessageServiceDep
) -> MessageDTO:
    return message_service.create_message(payload)


@router.get(
    "/telegram/{telegram_msg_id}",
    response_model=MessageDTO,
    summary="Get a message by its Telegram id",
)
def get_message_by_telegram_id(
    telegram_msg_id: int,
    message_service: MessageServiceDep,
    chat_id: int | None = Query(None),
) -> MessageDTO:
    return message_service.get_by_telegram_id(telegram_msg_id, chat_id=chat_id)


@router.get("/{message_id}", response_model=MessageDTO, summary="Get a message")
def get_message(message_id: int, message_service: MessageServiceDep) -> MessageDTO:
    return message_service.get_message(message_id)
