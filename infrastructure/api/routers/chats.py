"""Chat import and management endpoints."""

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from application.dtos.chat_dto import (
    ChatDTO,
    ImportSummaryDTO,
    RederiveSummaryDTO,
)
from domain.errors import InvalidExportError
from infrastructure.api.dependencies import ChatServiceDep, IngestionServiceDep

router = APIRouter(prefix="/chats", tags=["Chats"])


class ImportLocalRequest(BaseModel):
    file_path: str
    override_name: str | None = None


@router.post(
    "/upload",
    response_model=ImportSummaryDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Import an uploaded Telegram export",
)
def upload_chat_export(
    ingestion_service: IngestionServiceDep,
    file: UploadFile = File(...),
) -> ImportSummaryDTO:
    """Streams an uploaded export into storage.

    Declared ``def`` rather than ``async def`` on purpose: ingestion is
    blocking work, so FastAPI runs it in a worker thread instead of stalling
    the event loop for the length of the import.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".json"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Uploaded file must be a Telegram JSON export.",
        )
    return ingestion_service.ingest_export(file.file, override_name=Path(filename).stem)


@router.post(
    "/import-local",
    response_model=ImportSummaryDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Import an export already on the server",
)
def import_local_export(
    payload: ImportLocalRequest,
    ingestion_service: IngestionServiceDep,
) -> ImportSummaryDTO:
    path = Path(payload.file_path)
    if not path.is_file():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"No file at path: {payload.file_path}"
        )
    try:
        return ingestion_service.ingest_export(
            path, override_name=payload.override_name
        )
    except OSError as error:
        raise InvalidExportError(f"Could not read {path}: {error}") from error


@router.get("", response_model=list[ChatDTO], summary="List imported chats")
def list_chats(chat_service: ChatServiceDep) -> list[ChatDTO]:
    return chat_service.list_chats()


@router.get("/{chat_id}", response_model=ChatDTO, summary="Get one chat")
def get_chat(chat_id: int, chat_service: ChatServiceDep) -> ChatDTO:
    return chat_service.get_chat(chat_id)


@router.delete(
    "/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat and its messages",
)
def delete_chat(chat_id: int, chat_service: ChatServiceDep) -> None:
    chat_service.delete_chat(chat_id)


@router.post(
    "/{chat_id}/rederive",
    response_model=RederiveSummaryDTO,
    summary="Recompute derived columns from the text already stored",
)
def rederive_chat(
    chat_id: int, ingestion_service: IngestionServiceDep
) -> RederiveSummaryDTO:
    """Brings a chat imported by an older version up to the current metrics.

    Counts and markers are written at ingest, so a chat imported before a
    metric existed reads as zero for it. They are all functions of text this
    database already holds, so this recomputes them in place — no export
    needed. A voice note's length is the exception: it lives in the export
    rather than in the text, so it takes a fresh import.

    Declared ``def`` rather than ``async def``: it rewrites every row in the
    chat, which belongs in a worker thread rather than on the event loop.
    """
    return ingestion_service.rederive(chat_id)
