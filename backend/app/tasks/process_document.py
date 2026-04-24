"""
Task Celery para processar documentos — implementação 100% síncrona.

Por que síncrona?
  Celery workers são processos síncronos. Usar asyncio.run() dentro de um
  worker Celery causa conflitos de event loop com asyncpg ("Future attached
  to a different loop"). A solução correta é usar psycopg2 (driver síncrono)
  nas tasks, reservando asyncpg apenas para a API FastAPI.
"""

import logging
import os
import tempfile
import time
from uuid import UUID

import redis as redis_lib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

from app.celery_app import celery_app
from app.config import settings
from app.models import Base, Chunk, Document, DocumentStatus
from app.services.document_processor import DocumentProcessingService
from app.services.embedding_service import get_embedding_service

SYNC_DATABASE_URL = settings.sync_database_url

_sync_engine = None
_SyncSession = None
_redis_client = None


def _get_session_factory():
    global _sync_engine, _SyncSession
    if _SyncSession is None:
        _sync_engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True)
        _SyncSession = sessionmaker(bind=_sync_engine)
    return _SyncSession


def _get_redis() -> redis_lib.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_lib.from_url(settings.redis_url, decode_responses=False)
    return _redis_client


def _load_file(doc_id: str) -> bytes | None:
    return _get_redis().get(f"doc_file:{doc_id}")


TASK_TIMEOUT = 600  # 10 minutos


@celery_app.task(
    name="process_document",
    bind=True,
    time_limit=TASK_TIMEOUT,
    soft_time_limit=TASK_TIMEOUT - 30,
)
def process_document(self, document_id: str, file_ext: str):
    """
    Processa um documento: lê conteúdo do Redis → parse → chunking → embeddings → salva no banco.
    """
    doc_uuid = UUID(document_id)
    SyncSession = _get_session_factory()
    t0 = time.time()

    with SyncSession() as db:
        doc = db.get(Document, doc_uuid)
        if not doc:
            logger.warning("[Task] Documento não encontrado: %s (provavelmente deletado)", document_id)
            return {"status": "error", "error": f"Documento não encontrado: {document_id}"}

        filename = doc.filename
        logger.info("[Task] ▶ Iniciando processamento de '%s' (id=%s)", filename, document_id)

        try:
            doc.status = DocumentStatus.PROCESSING
            db.commit()

            # Lê conteúdo do Redis — funciona em qualquer ambiente sem filesystem compartilhado
            file_content = _load_file(document_id)
            if not file_content:
                raise ValueError(f"Conteúdo do arquivo não encontrado no Redis para doc {document_id}")

            # Escreve em arquivo temporário para o parser (pymupdf/docx exigem arquivo em disco)
            with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
                tmp.write(file_content)
                tmp_path = tmp.name

            try:
                logger.info("[Task] 📄 Fazendo parse do arquivo '%s'...", filename)
                t_parse = time.time()
                processor = DocumentProcessingService()
                chunks_text = processor.process(tmp_path)
            finally:
                os.unlink(tmp_path)

            if not chunks_text:
                raise ValueError(f"Nenhum texto extraído de: {filename}")

            logger.info(
                "[Task] ✂  Chunking concluído em %.1fs — %d chunks extraídos de '%s'",
                time.time() - t_parse, len(chunks_text), filename,
            )

            total_raw = len(chunks_text)
            if total_raw > settings.max_chunks_per_doc:
                step = total_raw / settings.max_chunks_per_doc
                indices = [int(i * step) for i in range(settings.max_chunks_per_doc)]
                chunks_text = [chunks_text[i] for i in indices]
                logger.warning(
                    "[Task] ⚠  '%s': %d chunks → amostrados %d distribuídos uniformemente.",
                    filename, total_raw, settings.max_chunks_per_doc,
                )

            logger.info("[Task] 💾 Salvando %d chunks de '%s' no banco...", len(chunks_text), filename)
            chunks = [
                Chunk(document_id=doc_uuid, content=text, chunk_index=i)
                for i, text in enumerate(chunks_text)
            ]
            db.add_all(chunks)
            db.flush()

            n = len(chunks_text)
            logger.info("[Task] 🧠 Gerando embeddings para %d chunks de '%s'...", n, filename)
            t_emb = time.time()
            embedding_svc = get_embedding_service()

            batch_size = 64
            all_vectors = []
            for start in range(0, n, batch_size):
                batch = chunks_text[start : start + batch_size]
                vectors = embedding_svc.embed_batch(batch, batch_size=batch_size)
                all_vectors.extend(vectors)
                pct = min(100, round((start + len(batch)) / n * 100))
                logger.info(
                    "[Task] 🧠   %d/%d chunks embedados (%d%%) — '%s'",
                    start + len(batch), n, pct, filename,
                )

            logger.info(
                "[Task] 🧠 Embeddings concluídos em %.1fs para '%s'",
                time.time() - t_emb, filename,
            )

            for chunk, vector in zip(chunks, all_vectors):
                chunk.embedding = vector

            doc.status = DocumentStatus.DONE
            doc.total_chunks = len(chunks)
            db.commit()

            elapsed = time.time() - t0
            logger.info(
                "[Task] ✅ '%s' indexado com %d chunks em %.1fs.",
                filename, len(chunks), elapsed,
            )
            return {
                "status": "success",
                "document_id": document_id,
                "chunks_created": len(chunks),
                "chunks_truncated": total_raw > settings.max_chunks_per_doc,
                "filename": filename,
                "elapsed_seconds": round(elapsed, 1),
            }

        except Exception as e:
            db.rollback()
            error_msg = str(e)
            logger.error("[Task] ❌ Erro ao processar '%s': %s", filename, error_msg, exc_info=True)

            doc = db.get(Document, doc_uuid)
            if doc:
                doc.status = DocumentStatus.ERROR
                doc.error_message = error_msg[:500]
                db.commit()

            return {
                "status": "error",
                "document_id": document_id,
                "error": error_msg,
            }
