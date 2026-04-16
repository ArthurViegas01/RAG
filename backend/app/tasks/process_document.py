"""
Task Celery para processar documentos — implementação 100% síncrona.

Por que síncrona?
  Celery workers são processos síncronos. Usar asyncio.run() dentro de um
  worker Celery causa conflitos de event loop com asyncpg ("Future attached
  to a different loop"). A solução correta é usar psycopg2 (driver síncrono)
  nas tasks, reservando asyncpg apenas para a API FastAPI.
"""

import logging
import time
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

from app.celery_app import celery_app
from app.config import settings
from app.models import Base, Chunk, Document, DocumentStatus
from app.services.document_processor import DocumentProcessingService
from app.services.embedding_service import get_embedding_service

# URL síncrona: troca asyncpg por psycopg2
SYNC_DATABASE_URL = settings.database_url.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)

# Engine e session factory criados lazily (na primeira task executada),
# evitando falha no import caso psycopg2 ainda não esteja disponível.
_sync_engine = None
_SyncSession = None


def _get_session_factory():
    """Inicializa o engine síncrono na primeira chamada (lazy)."""
    global _sync_engine, _SyncSession
    if _SyncSession is None:
        _sync_engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True)
        _SyncSession = sessionmaker(bind=_sync_engine)
    return _SyncSession

TASK_TIMEOUT = 600  # 10 minutos


@celery_app.task(
    name="process_document",
    bind=True,
    time_limit=TASK_TIMEOUT,
    soft_time_limit=TASK_TIMEOUT - 30,
)
def process_document(self, document_id: str):
    """
    Processa um documento: parse → chunking → embeddings → salva no banco.

    Completamente síncrono — sem asyncio, sem conflitos de event loop.
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
            # 1. Marcar como PROCESSING
            doc.status = DocumentStatus.PROCESSING
            db.commit()

            # 2. Parse + chunking
            logger.info("[Task] 📄 Fazendo parse do arquivo '%s'...", filename)
            t_parse = time.time()
            processor = DocumentProcessingService()
            chunks_text = processor.process(doc.file_path)

            if not chunks_text:
                raise ValueError(f"Nenhum texto extraído de: {filename}")

            logger.info(
                "[Task] ✂  Chunking concluído em %.1fs — %d chunks extraídos de '%s'",
                time.time() - t_parse, len(chunks_text), filename,
            )

            # 3. Limitar chunks (evita travamento em PDFs gigantes)
            total_raw = len(chunks_text)
            if total_raw > settings.max_chunks_per_doc:
                logger.warning(
                    "[Task] ⚠  '%s': %d chunks → limitando a %d (máx configurado).",
                    filename, total_raw, settings.max_chunks_per_doc,
                )
                chunks_text = chunks_text[: settings.max_chunks_per_doc]

            # 4. Criar objetos Chunk e salvar
            logger.info("[Task] 💾 Salvando %d chunks de '%s' no banco...", len(chunks_text), filename)
            chunks = [
                Chunk(document_id=doc_uuid, content=text, chunk_index=i)
                for i, text in enumerate(chunks_text)
            ]
            db.add_all(chunks)
            db.flush()  # flush para gerar os IDs sem fechar a transação

            # 5. Gerar embeddings em batch com progresso
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

            # 6. Atribuir embeddings aos chunks
            for chunk, vector in zip(chunks, all_vectors):
                chunk.embedding = vector

            # 7. Marcar como DONE e salvar tudo em um único commit
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

            # Busca o doc novamente após rollback para atualizar status
            doc = db.get(Document, doc_uuid)
            if doc:
                doc.status = DocumentStatus.ERROR
                doc.error_message = error_msg[:500]  # trunca mensagem longa
                db.commit()

            return {
                "status": "error",
                "document_id": document_id,
                "error": error_msg,
            }
