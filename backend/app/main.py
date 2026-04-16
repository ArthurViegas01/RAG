"""
Entry point da aplicação FastAPI.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import documents_router, search_router, chat_router
from app.config import settings
from app.database import init_db

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
    # Cria as tabelas no banco de dados se não existirem
    await init_db()


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
