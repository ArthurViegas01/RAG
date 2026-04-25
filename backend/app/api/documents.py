"""
API endpoints para upload e gerenciamento de documentos.
"""

import os
from uuid import UUID, uuid4

import redis as redis_lib
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.config import settings
from app.database import get_db
from app.models import DocumentStatus
from app.schemas import DocumentDetailResponse, DocumentResponse
from app.services import DocumentRepository
from app.tasks import process_document

router = APIRouter(prefix="/api/documents", tags=["documents"])

# TTL de 7 dias — tempo suficiente para reprocessamento manual
_FILE_TTL = 7 * 24 * 3600
_redis_client = None


def _get_redis() -> redis_lib.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_lib.from_url(settings.redis_url, decode_responses=False)
    return _redis_client


def _file_key(doc_id: str) -> str:
    return f"doc_file:{doc_id}"


def _store_file(doc_id: str, content: bytes) -> None:
    _get_redis().setex(_file_key(doc_id), _FILE_TTL, content)


def _load_file(doc_id: str) -> bytes | None:
    return _get_redis().get(_file_key(doc_id))


def _delete_file(doc_id: str) -> None:
    _get_redis().delete(_file_key(doc_id))


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    allowed_extensions = {".pdf", ".docx"}
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de arquivo não suportado. Aceitos: {allowed_extensions}",
        )

    existing_count = await DocumentRepository.count_by_filename(db, file.filename)
    if existing_count > 0 and response is not None:
        response.headers["X-Duplicate-Warning"] = (
            f"Duplicate: {existing_count} document(s) with this name already exist."
        )

    file_content = await file.read()
    file_size_bytes = len(file_content)

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if file_size_bytes > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum: {settings.max_file_size_mb}MB",
        )

    doc = await DocumentRepository.create(
        db=db,
        filename=file.filename,
        file_path=file.filename,
        file_size_bytes=file_size_bytes,
    )

    # Armazena o conteúdo no Redis — compartilhado entre API e worker sem depender
    # de filesystem local (containers isolados em prod/Railway)
    _store_file(str(doc.id), file_content)

    task = process_document.delay(str(doc.id), file_ext)
    doc.celery_task_id = task.id
    await db.commit()
    await db.refresh(doc)

    return DocumentResponse.model_validate(doc)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    docs = await DocumentRepository.list_all(db, limit=limit, offset=skip)
    return [DocumentResponse.model_validate(doc) for doc in docs]


@router.get("/{doc_id}", response_model=DocumentDetailResponse)
async def get_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    doc = await DocumentRepository.get_by_id_with_chunks(db, doc_id)

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento não encontrado: {doc_id}",
        )

    return DocumentDetailResponse.model_validate(doc)


@router.get("/{doc_id}/status", response_model=dict)
async def get_document_status(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    doc = await DocumentRepository.get_by_id(db, doc_id)

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento não encontrado: {doc_id}",
        )

    return {
        "document_id": str(doc.id),
        "filename": doc.filename,
        "status": doc.status.value,
        "total_chunks": doc.total_chunks,
        "error_message": doc.error_message,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }


@router.post("/{doc_id}/reprocess", response_model=DocumentResponse)
async def reprocess_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    doc = await DocumentRepository.get_by_id(db, doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento não encontrado: {doc_id}",
        )

    if doc.status in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Documento já está sendo processado.",
        )

    if _load_file(str(doc_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Conteúdo original expirou. Envie o documento novamente.",
        )

    file_ext = os.path.splitext(doc.filename)[1].lower()

    from sqlalchemy import delete as sql_delete
    from app.models import Chunk
    await db.execute(sql_delete(Chunk).where(Chunk.document_id == doc_id))

    doc.status = DocumentStatus.PENDING
    doc.error_message = None
    doc.total_chunks = 0
    await db.commit()
    await db.refresh(doc)

    task = process_document.delay(str(doc.id), file_ext)
    doc.celery_task_id = task.id
    await db.commit()
    await db.refresh(doc)

    return DocumentResponse.model_validate(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    doc = await DocumentRepository.get_by_id(db, doc_id)

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento não encontrado: {doc_id}",
        )

    if doc.celery_task_id:
        try:
            celery_app.control.revoke(doc.celery_task_id, terminate=True, signal="SIGTERM")
        except Exception:
            pass

    _delete_file(str(doc_id))

    await db.delete(doc)
    await db.commit()
