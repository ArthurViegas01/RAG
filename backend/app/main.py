"""
Entry point da aplicação FastAPI.
"""

import logging

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update

from app.api import documents_router, search_router, chat_router
from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.models import Document, DocumentStatus

logger = logging.getLogger(__name__)

app = FastAPI(
    title="RAG Pipeline API",
    description="API para upload de documentos, busca semântica e Q&A com RAG",
    version="0.1.0",
)

# CORS — origens configuradas via CORS_ORIGINS (separadas por vírgula)
_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra routers
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(chat_router)


@app.on_event("startup")
async def startup_event():
    """Executado ao iniciar a aplicação."""
    # Log da URL do banco (sem senha) para facilitar diagnóstico
    db_url = settings.async_database_url
    masked = db_url.split("@")[-1] if "@" in db_url else db_url
    logger.info("[Startup] Conectando ao banco: %s", masked)
    logger.info("[Startup] LLM provider: %s", settings.llm_provider)
    logger.info("[Startup] CORS origins: %s", settings.cors_origins)

    await init_db()
    await _reset_stuck_documents()


async def _reset_stuck_documents():
    """
    Ao reiniciar o servidor, documentos em PENDING ou PROCESSING ficam
    presos para sempre (a task Celery foi perdida). Marca-os como ERROR
    para o usuário saber que precisa reenviar.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(Document)
            .where(Document.status.in_([DocumentStatus.PENDING, DocumentStatus.PROCESSING]))
            .values(
                status=DocumentStatus.ERROR,
                error_message="Processamento interrompido pelo reinício do servidor. Envie o arquivo novamente.",
            )
            .returning(Document.id, Document.filename)
        )
        rows = result.fetchall()
        await db.commit()

    if rows:
        logger.warning(
            "[Startup] %d documento(s) travado(s) marcado(s) como ERROR: %s",
            len(rows),
            [r.filename for r in rows],
        )


@app.get("/health")
async def health_check():
    """
    Health check completo: verifica API, Ollama e modelos configurados.
    O frontend usa esse endpoint para saber se o Ollama está rodando.
    """
    ollama_ok = False
    ollama_error = None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception as exc:
        ollama_error = str(exc)

    return {
        "status": "healthy",
        "version": "0.1.0",
        "embedding_model": settings.embedding_model,
        "llm_model": settings.ollama_model,
        "ollama_url": settings.ollama_base_url,
        "ollama_reachable": ollama_ok,
        "ollama_error": ollama_error,
    }
