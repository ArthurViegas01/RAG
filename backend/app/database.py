"""
Configuração de conexão com PostgreSQL usando SQLAlchemy async.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import Base

# Engine assíncrono para PostgreSQL
engine = create_async_engine(
    settings.database_url,
    echo=False,  # Mude para True para ver SQL queries (debug)
    pool_pre_ping=True,  # Valida conexões antes de usar
)

# Session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db():
    """
    Dependency injection para FastAPI.
    Fornece uma sessão de banco de dados para cada requisição.

    Usage:
        @app.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """
    Habilita a extensão pgvector e cria todas as tabelas.
    Deve ser chamado na startup da aplicação.
    """
    async with engine.begin() as conn:
        # Habilita pgvector — necessário antes de criar colunas do tipo vector
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

        # Adiciona colunas novas de forma idempotente (não recria a tabela)
        await conn.execute(text(
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS celery_task_id VARCHAR(255)"
        ))

        # Índice B-tree para filtrar chunks por documento (muito usado em buscas)
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_chunks_document_id "
            "ON chunks (document_id)"
        ))

        # Índice HNSW para buscas vetoriais rápidas com distância de cosseno.
        # HNSW é muito mais rápido que o scan sequencial padrão em tabelas grandes.
        # m=16, ef_construction=64 são bons valores de partida para este workload.
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw "
            "ON chunks USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        ))


async def drop_db():
    """
    CUIDADO: Remove todas as tabelas.
    Use apenas em testes ou reset completo.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
