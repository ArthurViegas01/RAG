"""
Entry point da aplicação FastAPI.
"""

import logging

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

# CORS — permite o frontend React se conectar
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
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
    Health check simples.
    Útil para Docker, load balancers, e para validar que a API está rodando.
    """
    return {
        "status": "healthy",
        "version": "0.1.0",
        "embedding_model": settings.embedding_model,
        "llm_model": settings.ollama_model,
    }
