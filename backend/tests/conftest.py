"""
Fixtures compartilhadas para os testes do RAG.

O bloco de mocks no topo deste arquivo e executado antes de qualquer modulo
de teste ser importado. Isso permite rodar os testes unitarios sem instalar
as dependencias pesadas (sentence-transformers, asyncpg, pgvector).
"""

import sys
import os
from unittest.mock import MagicMock

import pytest


# ── Mock de bibliotecas pesadas / de infraestrutura ──────────────────────────
# Executado antes de qualquer import dos modulos da app.

def _stub(name, *submodules):
    """Registra um MagicMock em sys.modules para 'name' e seus submodulos."""
    if name not in sys.modules:
        sys.modules[name] = MagicMock()
    for sub in submodules:
        full = f"{name}.{sub}"
        if full not in sys.modules:
            sys.modules[full] = MagicMock()

# sentence-transformers (torch nao precisa ser instalado para unit tests)
_stub("sentence_transformers")

# asyncpg (driver PostgreSQL) — nao conecta de verdade nos unit tests
_stub("asyncpg", "exceptions", "pgproto", "pgproto.pgproto")

# pgvector SQLAlchemy integration
_stub("pgvector", "sqlalchemy")
_stub("pgvector.sqlalchemy")

# Configura o mock do sentence_transformers para retornar vetores realistas
import numpy as np  # noqa: E402 — numpy ja vem com langchain
_mock_st_model = MagicMock()
_mock_st_model.encode.return_value = [0.1] * 384
_mock_st_model.get_sentence_embedding_dimension.return_value = 384
sys.modules["sentence_transformers"].SentenceTransformer.return_value = _mock_st_model


# ── Configuracao de event loop ────────────────────────────────────────────────

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# ── Marcadores customizados ───────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line("markers", "unit: teste unitario rapido, sem dependencias externas")
    config.addinivalue_line("markers", "integration: teste de integracao que requer servicos externos")


# ── Helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def ollama_url():
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


@pytest.fixture(scope="session")
def api_url():
    return os.getenv("API_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def database_url():
    return os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://raguser:ragpass123@localhost:5432/ragdb",
    )


@pytest.fixture(scope="session")
def redis_url():
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")
