"""
Entry point da aplicação FastAPI.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import update

from app.api import auth_router, documents_router, search_router, chat_router
from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.models import Document, DocumentStatus
from app.rate_limit import limiter

logger = logging.getLogger(__name__)


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_url = settings.async_database_url
    masked = db_url.split("@")[-1] if "@" in db_url else db_url
    logger.info("[Startup] Conectando ao banco: %s", masked)
    logger.info("[Startup] LLM provider: %s", settings.llm_provider)
    logger.info("[Startup] CORS origins: %s", settings.cors_origins)
    await init_db()
    await _reset_stuck_documents()
    yield


app = FastAPI(
    title="RAG Pipeline API",
    description="API para upload de documentos, busca semântica e Q&A com RAG",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

if "*" in _cors_origins:
    raise RuntimeError(
        "CORS_ORIGINS='*' com allow_credentials=True e inseguro: "
        "o Starlette refletiria qualquer Origin, permitindo roubo de sessao. "
        "Defina origens explicitas (ex: https://meuapp.netlify.app)."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(chat_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
