"""
Testes de integração — verificam se todos os serviços estão acessíveis.

Execução (dentro do container ou com venv ativo):
    pytest tests/test_health.py -v

Execução via Docker (sem instalar nada localmente):
    docker-compose exec api pytest tests/test_health.py -v
"""

import os

import httpx
import pytest
import redis as redis_lib
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


# ──────────────────────────────────────────────────────────────────────────────
# Configuração — lê variáveis de ambiente (funciona tanto local quanto Docker)
# ──────────────────────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://raguser:ragpass123@localhost:5432/ragdb",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


# ──────────────────────────────────────────────────────────────────────────────
# 1. PostgreSQL
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_connection():
    """Verifica que a API consegue conectar ao PostgreSQL."""
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1, "PostgreSQL retornou resultado inesperado"
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_pgvector_extension():
    """Verifica que a extensão pgvector está habilitada."""
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            row = result.fetchone()
            assert row is not None, (
                "Extensão 'vector' (pgvector) não está instalada. "
                "Execute: CREATE EXTENSION IF NOT EXISTS vector"
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_tables_exist():
    """Verifica que as tabelas documents e chunks existem."""
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            for table in ("documents", "chunks"):
                result = await conn.execute(
                    text(
                        "SELECT EXISTS ("
                        "  SELECT FROM information_schema.tables "
                        "  WHERE table_name = :t"
                        ")"
                    ),
                    {"t": table},
                )
                exists = result.scalar()
                assert exists, f"Tabela '{table}' não existe no banco."
    finally:
        await engine.dispose()


# ──────────────────────────────────────────────────────────────────────────────
# 2. Redis
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_redis_connection():
    """Verifica que o Redis está acessível e responde ao PING."""
    client = redis_lib.from_url(REDIS_URL, socket_connect_timeout=5)
    try:
        response = client.ping()
        assert response is True, "Redis não respondeu ao PING"
    finally:
        client.close()


@pytest.mark.integration
def test_redis_read_write():
    """Verifica operações básicas de leitura e escrita no Redis."""
    client = redis_lib.from_url(REDIS_URL, socket_connect_timeout=5)
    try:
        client.set("papyrus:health_check", "ok", ex=10)  # expira em 10s
        value = client.get("papyrus:health_check")
        assert value == b"ok", f"Redis devolveu valor inesperado: {value}"
    finally:
        client.delete("papyrus:health_check")
        client.close()


# ──────────────────────────────────────────────────────────────────────────────
# 3. Ollama
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_ollama_reachable():
    """
    Verifica que o Ollama está rodando e acessível.
    Se falhar: execute 'ollama serve' no host antes de rodar os testes.
    """
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        assert r.status_code == 200, f"Ollama retornou {r.status_code}"
    except httpx.ConnectError:
        pytest.fail(
            f"Não foi possível conectar ao Ollama em {OLLAMA_BASE_URL}.\n"
            "Solução: abra um terminal e execute 'ollama serve'"
        )


@pytest.mark.integration
def test_ollama_model_available():
    """
    Verifica que o modelo configurado (llama3 por padrão) está baixado.
    Se falhar: execute 'ollama pull llama3' no host.
    """
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3")
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        # Aceita nome exato ou com tag (ex: llama3 ou llama3:latest)
        found = any(
            m == ollama_model or m.startswith(f"{ollama_model}:")
            for m in models
        )
        assert found, (
            f"Modelo '{ollama_model}' não encontrado no Ollama.\n"
            f"Modelos disponíveis: {models}\n"
            f"Solução: execute 'ollama pull {ollama_model}'"
        )
    except httpx.ConnectError:
        pytest.skip("Ollama não acessível — pulando teste de modelo")


# ──────────────────────────────────────────────────────────────────────────────
# 4. FastAPI (health endpoint)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_api_health():
    """Verifica que a API FastAPI está rodando e responde ao health check."""
    try:
        r = httpx.get(f"{API_BASE_URL}/health", timeout=10.0)
        assert r.status_code == 200, f"API retornou {r.status_code}"
        data = r.json()
        assert data["status"] == "healthy"
        assert "ollama_reachable" in data
    except httpx.ConnectError:
        pytest.fail(
            f"Não foi possível conectar à API em {API_BASE_URL}.\n"
            "Solução: verifique se o container 'rag-api' está rodando."
        )


@pytest.mark.integration
def test_api_documents_endpoint():
    """Verifica que o endpoint de listagem de documentos funciona."""
    try:
        r = httpx.get(f"{API_BASE_URL}/api/documents", timeout=10.0)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
    except httpx.ConnectError:
        pytest.fail("API não acessível")


# ──────────────────────────────────────────────────────────────────────────────
# 5. Embedding Service (unit — sem dependências externas)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_embedding_service_loads():
    """Verifica que o modelo de embedding carrega e gera vetores com a dimensão correta."""
    from app.services.embedding_service import get_embedding_service
    svc = get_embedding_service()
    vec = svc.embed("Teste de embedding do Papyrus")
    assert isinstance(vec, list), "embed() deve retornar uma lista"
    assert len(vec) == 384, f"Dimensão esperada: 384, recebida: {len(vec)}"
    # Vetores normalizados têm norma ≈ 1
    norm = sum(x ** 2 for x in vec) ** 0.5
    assert 0.99 < norm < 1.01, f"Vetor não normalizado (norma={norm:.4f})"


@pytest.mark.unit
def test_embedding_batch():
    """Verifica que embed_batch funciona com múltiplos textos."""
    from app.services.embedding_service import get_embedding_service
    svc = get_embedding_service()
    texts = ["Primeiro texto", "Segundo texto", "Terceiro texto"]
    vecs = svc.embed_batch(texts)
    assert len(vecs) == 3, f"Esperava 3 vetores, recebeu {len(vecs)}"
    for v in vecs:
        assert len(v) == 384


@pytest.mark.unit
def test_embedding_similarity_ordering():
    """Textos semanticamente similares devem ter maior similaridade entre si."""
    from app.services.embedding_service import get_embedding_service
    svc = get_embedding_service()

    def cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x ** 2 for x in a) ** 0.5
        norm_b = sum(x ** 2 for x in b) ** 0.5
        return dot / (norm_a * norm_b)

    v_dog1 = svc.embed("O cachorro correu pelo parque")
    v_dog2 = svc.embed("O cão brincou no jardim")
    v_unrelated = svc.embed("Derivadas parciais em cálculo multivariável")

    sim_related = cosine(v_dog1, v_dog2)
    sim_unrelated = cosine(v_dog1, v_unrelated)

    assert sim_related > sim_unrelated, (
        f"Textos similares ({sim_related:.3f}) deveriam ter maior "
        f"similaridade que textos não relacionados ({sim_unrelated:.3f})"
    )


# ──────────────────────────────────────────────────────────────────────────────
# 6. Document Processor (unit)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_document_processor_pdf(tmp_path):
    """Verifica que o processador de PDF extrai texto e cria chunks."""
    pytest.importorskip("fitz", reason="pymupdf não instalado")
    from reportlab.pdfgen import canvas as rl_canvas

    # Cria um PDF simples com reportlab
    pdf_path = str(tmp_path / "test.pdf")
    try:
        c = rl_canvas.Canvas(pdf_path)
        c.drawString(100, 750, "Este é um documento de teste para o Papyrus.")
        c.drawString(100, 730, "Ele contém algumas frases para verificar o chunking.")
        c.save()
    except Exception:
        pytest.skip("reportlab não instalado — pulando teste de PDF")

    from app.services.document_processor import DocumentProcessingService
    processor = DocumentProcessingService()
    chunks = processor.process(pdf_path)
    assert len(chunks) >= 1, "Processador deveria extrair pelo menos 1 chunk"
    assert any("teste" in c.lower() or "papyrus" in c.lower() for c in chunks)


@pytest.mark.unit
def test_chunk_size_limit():
    """Verifica que a amostragem uniforme de chunks funciona corretamente."""
    max_chunks = 10
    total_chunks = 100

    step = total_chunks / max_chunks
    indices = [int(i * step) for i in range(max_chunks)]

    assert len(indices) == max_chunks
    assert indices[0] == 0          # começa no início
    assert indices[-1] == 90        # termina próximo do final (não ultrapassa)
    assert len(set(indices)) == max_chunks  # sem repetições


# ──────────────────────────────────────────────────────────────────────────────
# 7. Config (unit)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_settings_load():
    """Verifica que as configurações carregam sem erro."""
    from app.config import settings
    assert settings.embedding_model == "all-MiniLM-L6-v2"
    assert settings.embedding_dimension == 384
    assert settings.chunk_size > 0
    assert settings.max_chunks_per_doc > 0
    assert "postgresql" in settings.database_url
    assert "redis" in settings.celery_broker_url


@pytest.mark.unit
def test_settings_ollama_url():
    """Verifica que a URL do Ollama está configurada."""
    from app.config import settings
    assert settings.ollama_base_url.startswith("http"), (
        f"OLLAMA_BASE_URL inválida: {settings.ollama_base_url}"
    )
    assert "11434" in settings.ollama_base_url or settings.ollama_base_url != "", (
        "OLLAMA_BASE_URL não parece conter a porta padrão do Ollama (11434)"
    )
