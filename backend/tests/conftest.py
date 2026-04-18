"""
Fixtures compartilhadas para os testes do Papyrus.
"""

import os

import pytest
import pytest_asyncio


# ── Configuração de event loop para testes async ───────────────────────────────

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# ── Marcadores customizados ────────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line("markers", "unit: teste unitário rápido, sem dependências externas")
    config.addinivalue_line("markers", "integration: teste de integração que requer serviços externos")


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
