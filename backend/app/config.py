"""
Configurações centralizadas da aplicação.
Usa pydantic-settings para carregar variáveis do .env automaticamente.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    # Railway injeta DATABASE_URL como "postgresql://..." — convertemos para asyncpg automaticamente
    database_url: str = "postgresql+asyncpg://raguser:ragpass123@localhost:5432/ragdb"

    @property
    def async_database_url(self) -> str:
        """Garante que a URL use o driver asyncpg, independente do formato injetado.
        Railway e outros clouds exigem SSL — adiciona automaticamente quando não é localhost.
        """
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)

        # Adiciona ssl=require para ambientes cloud (Railway, Render, etc.)
        # Não aplica em localhost/127.0.0.1 para não quebrar dev local
        is_local = "localhost" in url or "127.0.0.1" in url
        if not is_local and "ssl" not in url:
            sep = "&" if "?" in url else "?"
            url += f"{sep}ssl=require"

        return url

    @property
    def sync_database_url(self) -> str:
        """URL com driver psycopg2 para uso síncrono no Celery worker.
        Railway exige SSL — adiciona sslmode=require automaticamente quando não é localhost.
        """
        url = self.database_url
        # Normaliza qualquer variante para postgresql:// (psycopg2 padrão)
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        elif url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql://", 1)

        # psycopg2 usa sslmode (não ssl) como parâmetro de URL
        is_local = "localhost" in url or "127.0.0.1" in url
        if not is_local and "sslmode" not in url:
            sep = "&" if "?" in url else "?"
            url += f"{sep}sslmode=require"

        return url

    # Redis / Celery
    # Railway injeta REDIS_URL automaticamente — celery_broker_url e result_backend
    # são derivados de redis_url para simplificar a configuração de produção.
    redis_url: str = "redis://localhost:6379/0"

    @property
    def celery_broker_url(self) -> str:
        """URL do broker Celery — usa REDIS_URL se celery_broker_url não estiver setado."""
        return self.redis_url

    @property
    def celery_result_backend(self) -> str:
        """URL do backend de resultados Celery — mesmo Redis, database 1."""
        url = self.redis_url
        # Troca /0 por /1 para separar resultados do broker
        if url.endswith("/0"):
            url = url[:-2] + "/1"
        return url

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # LLM Provider: "ollama" (local) | "groq" | "openai"
    llm_provider: str = "ollama"

    # Ollama (local dev)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # Groq (produção — gratuito, https://console.groq.com)
    groq_api_key: str = ""
    groq_model: str = "llama3-8b-8192"

    # OpenAI (alternativa)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    # CORS — separar múltiplas origens por vírgula
    # Ex: "http://localhost:5173,https://contextrag.netlify.app"
    cors_origins: str = "http://localhost:5173"

    # Chunking
    chunk_size: int = 800           # Maior = mais contexto por chunk (melhor para livros)
    chunk_overlap: int = 150        # Overlap maior = não perde info entre chunks
    max_chunks_per_doc: int = 2000  # 2000 chunks cobre ~80% de um livro de 750 págs

    # Search / RAG
    default_top_k: int = 8          # Mais chunks = mais contexto para o LLM
    min_similarity: float = 0.15    # Limiar mais baixo = busca semântica mais abrangente

    # Upload
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton — importar de qualquer lugar
settings = Settings()
