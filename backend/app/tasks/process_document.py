"""
Task Celery para processar documentos de forma assíncrona.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.celery_app import celery_app
from app.config import settings
from app.models import DocumentStatus
from app.services import (
    ChunkRepository,
    DocumentRepository,
    DocumentProcessingService,
)


# Session factory para tasks Celery
AsyncSessionLocal = sessionmaker(
    create_async_engine(settings.database_url),
    class_=AsyncSession,
    expire_on_commit=False,
)


@celery_app.task(name="process_document", bind=True)
def process_document(self, document_id: str):
    """
    Processa um documento: extrai texto, faz chunking e salva no banco.

    Esta é uma task Celery que roda em background via Redis.

    Args:
        document_id: UUID do documento a processar

    Returns:
        dict com resultado do processamento
    """
    import asyncio

    return asyncio.run(_process_document_async(UUID(document_id)))


async def _process_document_async(document_id: UUID) -> dict:
    """
    Implementação assíncrona da task.
    """
    async with AsyncSessionLocal() as db:
        try:
            # 1. Busca documento
            doc = await DocumentRepository.get_by_id(db, document_id)
            if not doc:
                raise ValueError(f"Documento não encontrado: {document_id}")

            # 2. Marcar como PROCESSING
            await DocumentRepository.update_status(
                db, document_id, DocumentStatus.PROCESSING
            )

            # 3. Processar arquivo (parse + chunking)
            processor = DocumentProcessingService()
            chunks_text = processor.process(doc.file_path)

            if not chunks_text:
                raise ValueError(f"Nenhum chunk foi gerado para: {doc.filename}")

            # 4. Salvar chunks no banco
            chunks = await ChunkRepository.create_many(db, document_id, chunks_text)

            # 5. Marcar como DONE
            await DocumentRepository.update_on_success(db, document_id, len(chunks))

            return {
                "status": "success",
                "document_id": str(document_id),
                "chunks_created": len(chunks),
                "filename": doc.filename,
            }

        except Exception as e:
            # Em caso de erro, marcar como ERROR e salvar mensagem
            error_msg = str(e)
            await DocumentRepository.update_on_error(db, document_id, error_msg)

            return {
                "status": "error",
                "document_id": str(document_id),
                "error": error_msg,
            }
