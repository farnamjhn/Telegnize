from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from application.dtos.message_dto import MessageDTO
from domain.models.message import ContentType, Message, MessageId
from domain.repository.message_repository import IMessageRepository
from infrastructure.api.dependencies import get_message_repo
from infrastructure.parser.telegram_parser import TelegramJsonParser

router = APIRouter(prefix="/messages", tags=["Messages"])


class MessageDTOSchema(BaseModel):
    id: int
    chat_id: int
    sender_id: str
    sender_name: str
    timestamp: datetime
    text: str
    normalized_text: str
    language: str
    word_count: int
    is_question: bool
    content_type: str = "text"
    reply_to_msg_id: Optional[int] = None
    is_forwarded: bool = False
    is_cold_closure: bool = False

    class Config:
        from_attributes = True


class MessageCreateSchema(BaseModel):
    telegram_msg_id: int
    sender_id: str
    sender_name: str
    timestamp: datetime
    text: str
    chat_id: int = 1
    reply_to_msg_id: Optional[int] = None
    content_type: str = "text"
    is_forwarded: bool = False


class UploadSummaryResponse(BaseModel):
    parsed_count: int
    messages: List[MessageDTOSchema]


@router.get("", response_model=List[MessageDTOSchema])
def get_messages(
    chat_id: Optional[int] = Query(None, description="Optional chat ID filter"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sender_id: Optional[str] = Query(None),
    repo: IMessageRepository = Depends(get_message_repo),
):
    """Retrieves messages, optionally filtered by chat_id or sender_id."""
    if chat_id is not None:
        messages = repo.get_by_chat(chat_id=chat_id, limit=limit, offset=offset, sender_id=sender_id)
    else:
        messages = repo.get_all_ordered()
        messages = messages[offset : offset + limit]

    return [MessageDTOSchema.model_validate(MessageDTO.from_domain(m)) for m in messages]


@router.get("/{message_id}", response_model=MessageDTOSchema)
def get_message_by_id(
    message_id: int,
    repo: IMessageRepository = Depends(get_message_repo),
):
    """Retrieves a message by its internal database ID."""
    msg = repo.get_by_id(message_id)
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message with ID {message_id} not found.",
        )
    return MessageDTOSchema.model_validate(MessageDTO.from_domain(msg))


@router.get("/telegram/{telegram_msg_id}", response_model=MessageDTOSchema)
def get_message_by_telegram_id(
    telegram_msg_id: int,
    chat_id: Optional[int] = Query(None),
    repo: IMessageRepository = Depends(get_message_repo),
):
    """Retrieves a message by its Telegram message ID."""
    msg = repo.get_by_telegram_id(telegram_msg_id, chat_id=chat_id)
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message with Telegram ID {telegram_msg_id} not found.",
        )
    return MessageDTOSchema.model_validate(MessageDTO.from_domain(msg))


@router.post("", response_model=MessageDTOSchema, status_code=status.HTTP_201_CREATED)
def create_message(
    msg_in: MessageCreateSchema,
    repo: IMessageRepository = Depends(get_message_repo),
):
    """Creates and persists a single message entity."""
    try:
        content_type = ContentType(msg_in.content_type)
    except ValueError:
        content_type = ContentType.TEXT

    reply_to_id = (
        MessageId(msg_in.reply_to_msg_id)
        if msg_in.reply_to_msg_id is not None
        else None
    )

    parser = TelegramJsonParser()
    norm_text, lang = parser.normalizer.normalize(msg_in.text)

    msg = Message(
        id=0,
        telegram_msg_id=msg_in.telegram_msg_id,
        sender_id=msg_in.sender_id,
        sender_name=msg_in.sender_name,
        reply_to_msg_id=msg_in.reply_to_msg_id,
        timestamp=msg_in.timestamp,
        text=msg_in.text,
        content_type=content_type,
        reply_to_id=reply_to_id,
        is_forwarded=msg_in.is_forwarded,
        chat_id=msg_in.chat_id,
        raw_text=msg_in.text,
        normalized_text=norm_text,
        language=lang,
    )

    repo.save(msg)
    saved_msg = repo.get_by_telegram_id(msg_in.telegram_msg_id, chat_id=msg_in.chat_id)
    if not saved_msg:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve message after saving.",
        )
    return MessageDTOSchema.model_validate(MessageDTO.from_domain(saved_msg))


@router.post("/upload", response_model=UploadSummaryResponse, status_code=status.HTTP_201_CREATED)
async def upload_telegram_json(
    file: UploadFile = File(...),
    repo: IMessageRepository = Depends(get_message_repo),
):
    """Legacy compatibility endpoint: Uploads and parses Telegram JSON export."""
    try:
        contents = await file.read()
        json_str = contents.decode("utf-8")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {str(e)}",
        )

    parser = TelegramJsonParser()
    try:
        parsed_messages = parser.parse_json(json_str)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse Telegram JSON: {str(e)}",
        )

    if parsed_messages:
        repo.save_batch(parsed_messages)

    dtos = [MessageDTOSchema.model_validate(MessageDTO.from_domain(msg)) for msg in parsed_messages]
    return UploadSummaryResponse(parsed_count=len(dtos), messages=dtos)


@router.post("/parse", response_model=UploadSummaryResponse, status_code=status.HTTP_201_CREATED)
def parse_and_save_json_data(
    payload: Dict[str, Any],
    repo: IMessageRepository = Depends(get_message_repo),
):
    """Legacy compatibility endpoint: Parses JSON payload and saves messages."""
    parser = TelegramJsonParser()
    try:
        parsed_messages = parser.parse_data(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse data: {str(e)}",
        )

    if parsed_messages:
        repo.save_batch(parsed_messages)

    dtos = [MessageDTOSchema.model_validate(MessageDTO.from_domain(msg)) for msg in parsed_messages]
    return UploadSummaryResponse(parsed_count=len(dtos), messages=dtos)
