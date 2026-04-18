"""
API endpoints para upload e gerenciamento de documentos.
"""

import os
from uuid import UUID

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


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    """
    Upload de um documento (PDF ou DOCX).

    1. Valida arquivo
    2. Salva no filesystem
    3. Cria registro no banco
    4. Enfileira task Celery para processamento

    Args:
        file: Arquivo (PDF ou DOCX)
        db: Sessão do banco

    Returns:
        DocumentResponse com dados do documento criado
    """
    # Validação de tipo de arquivo
    allowed_extensions = {".pdf", ".docx"}
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de arquivo não suportado. Aceitos: {allowed_extensions}",
        )

    # Verificar duplicata (não bloqueia, apenas avisa via header)
    existing_count = await DocumentRepository.count_by_filename(db, file.filename)
    if existing_count > 0 and response is not None:
        response.headers["X-Duplicate-Warning"] = (
            f"Já existe {existing_count} documento(s) com este nome."
        )

    # Criar pasta de uploads se não existir
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Salvar arquivo no filesystem
    file_content = await file.read()
    file_size_bytes = len(file_content)

    # Validar tamanho
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if file_size_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_PAYLOAD_TOO_LARGE,
            detail=f"Arquivo muito grande. Máximo: {settings.max_file_size_mb}MB",
        )

    # Salvar arquivo (com UUID no nome para evitar colisões)
    from uuid import uuid4
    unique_filename = f"{uuid4()}{file_ext}"
    file_path = os.path.join(settings.upload_dir, unique_filename)

    with open(file_path, "wb") as f:
        f.write(file_content)

    # Criar documento no banco
    doc = await DocumentRepository.create(
        db=db,
        filename=file.filename,
        file_path=file_path,
        file_size_bytes=file_size_bytes,
    )

    # Enfileirar task Celery para processar em background
    task = process_document.delay(str(doc.id))

    # Salva o task_id para permitir cancelamento posterior
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
    """
    Lista documentos com paginação.

    Args:
        skip: Quantos documentos pular
        limit: Quantos documentos retornar
        db: Sessão do banco

    Returns:
        Lista de DocumentResponse
    """
    docs = await DocumentRepository.list_all(db, limit=limit, offset=skip)
    return [DocumentResponse.model_validate(doc) for doc in docs]


@router.get("/{doc_id}", response_model=DocumentDetailResponse)
async def get_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Busca um documento com seus chunks.

    Args:
        doc_id: UUID do documento
        db: Sessão do banco

    Returns:
        DocumentDetailResponse (com chunks)

    Raises:
        HTTPException: 404 se documento não encontrado
    """
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
    """
    Obtém o status do processamento de um documento.

    Útil para o frontend verificar quando um documento terminou de ser processado.

    Args:
        doc_id: UUID do documento
        db: Sessão do banco

    Returns:
        dict com status, total_chunks, e error_message (se houver erro)

    Raises:
        HTTPException: 404 se documento não encontrado
    """
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
    """
    Reprocessa um documento que falhou (status = error).
    Remove chunks existentes, reseta o status e reenfileira a task.

    Raises:
        HTTPException: 404 se não encontrado, 409 se já estiver processando/pronto
    """
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

    if not os.path.exists(doc.file_path):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Arquivo original não encontrado. Envie o documento novamente.",
        )

    # Remove chunks parciais do processamento anterior
    from sqlalchemy import delete as sql_delete
    from app.models import Chunk
    await db.execute(sql_delete(Chunk).where(Chunk.document_id == doc_id))

    # Reseta o documento
    doc.status = DocumentStatus.PENDING
    doc.error_message = None
    doc.total_chunks = 0
    await db.commit()
    await db.refresh(doc)

    # Reenfileira a task
    task = process_document.delay(str(doc.id))
    doc.celery_task_id = task.id
    await db.commit()
    await db.refresh(doc)

    return DocumentResponse.model_validate(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Deleta um documento e todos os seus chunks.
    Remove também o arquivo do filesystem.

    Raises:
        HTTPException: 404 se documento não encontrado
    """
    doc = await DocumentRepository.get_by_id(db, doc_id)

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento não encontrado: {doc_id}",
        )

    # Tenta revogar a task Celery (caso ainda esteja em execução)
    if doc.celery_task_id:
        try:
            celery_app.control.revoke(doc.celery_task_id, terminate=True, signal="SIGTERM")
        except Exception:
            pass  # Não falha o delete se a revogação não funcionar

    # Remove o arquivo do disco
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    # Remove do banco (cascade deleta os chunks automaticamente)
    await db.delete(doc)
    await db.commit()
