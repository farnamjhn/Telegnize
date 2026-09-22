import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from application.dtos.chat_dto import ChatDTO
from application.services.ingestion_service import IngestionService
from domain.repository.chat_repository import IChatRepository
from infrastructure.api.dependencies import (
    get_chat_repo,
    get_ingestion_service,
)

router = APIRouter(prefix="/chats", tags=["Chats"])


class ChatResponseSchema(BaseModel):
    id: int
    telegram_chat_id: int
    name: str
    type: str
    total_messages: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ImportLocalRequest(BaseModel):
    file_path: str
    override_name: Optional[str] = None


class ImportSummaryResponse(BaseModel):
    chat: ChatResponseSchema
    total_messages: int


@router.post("/upload", response_model=ImportSummaryResponse, status_code=status.HTTP_201_CREATED)
async def upload_chat_export(
    file: UploadFile = File(...),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
):
    """Streams and ingests a Telegram export JSON file using ijson and NLP normalizers."""
    if not file.filename.endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a JSON document.",
        )

    try:
        # file.file is a SpooledTemporaryFile / binary stream, compatible with ijson streaming
        result = ingestion_service.ingest_export(file.file, override_name=file.filename)
        return ImportSummaryResponse(
            chat=ChatResponseSchema.model_validate(result["chat"]),
            total_messages=result["total_messages"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stream and ingest export: {str(e)}",
        )


@router.post("/import-local", response_model=ImportSummaryResponse, status_code=status.HTTP_201_CREATED)
def import_local_export(
    payload: ImportLocalRequest,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
):
    """Streams and ingests a local Telegram export JSON file (e.g., example.json)."""
    if not os.path.exists(payload.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found at path: {payload.file_path}",
        )

    try:
        result = ingestion_service.ingest_export(
            payload.file_path,
            override_name=payload.override_name,
        )
        return ImportSummaryResponse(
            chat=ChatResponseSchema.model_validate(result["chat"]),
            total_messages=result["total_messages"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest local export: {str(e)}",
        )


@router.get("", response_model=List[ChatResponseSchema])
def list_chats(chat_repo: IChatRepository = Depends(get_chat_repo)):
    """Lists all imported chats."""
    chats = chat_repo.list_all()
    return [ChatResponseSchema.model_validate(c) for c in chats]


@router.get("/{chat_id}", response_model=ChatResponseSchema)
def get_chat(
    chat_id: int,
    chat_repo: IChatRepository = Depends(get_chat_repo),
):
    """Gets metadata for a specific chat."""
    chat = chat_repo.get_by_id(chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat with ID {chat_id} not found.",
        )
    return ChatResponseSchema.model_validate(chat)


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(
    chat_id: int,
    chat_repo: IChatRepository = Depends(get_chat_repo),
):
    """Deletes a chat and its stored messages."""
    success = chat_repo.delete(chat_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat with ID {chat_id} not found.",
        )
    return None
