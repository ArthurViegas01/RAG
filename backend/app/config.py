"""
Configurações centralizadas da aplicação.
Usa pydantic-settings para carregar variáveis do .env automaticamente.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://raguser:ragpass123@localhost:5432/ragdb"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Ollama (LLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 50

    # Upload
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton — importar de qualquer lugar
settings = Settings()
