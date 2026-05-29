"""
Testes unitarios para o endpoint de busca semantica.

DB e EmbeddingService sao mockados — nenhum servico externo necessario.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True, scope="module")
def mock_startup():
    with patch("app.main.init_db", new_callable=AsyncMock), \
         patch("app.main._reset_stuck_documents", new_callable=AsyncMock):
        yield


@pytest.fixture(scope="module")
def client(mock_startup):
    from app.main import app
    from app.database import get_db

    async def fake_db():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = fake_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


def _make_result(content="Trecho relevante do documento."):
    r = MagicMock()
    r.chunk_id = uuid4()
    r.document_id = uuid4()
    r.document_filename = "documento.pdf"
    r.content = content
    r.chunk_index = 0
    r.similarity = 0.87
    return r


def _search(client, query="O que e machine learning?", top_k=5, document_id=None):
    body = {"query": query, "top_k": top_k, "min_similarity": 0.3}
    if document_id:
        body["document_id"] = str(document_id)
    return client.post("/api/search", json=body)


# ── Happy path ────────────────────────────────────────────────────────────────

class TestSearchHappyPath:
    def test_returns_200(self, client):
        with patch("app.services.search_service.SearchService.search", new_callable=AsyncMock,
                   return_value=[_make_result()]):
            resp = _search(client)
        assert resp.status_code == 200

    def test_returns_list(self, client):
        results = [_make_result("Texto A"), _make_result("Texto B")]
        with patch("app.services.search_service.SearchService.search", new_callable=AsyncMock,
                   return_value=results):
            data = _search(client).json()
        assert isinstance(data, list)

    def test_returns_correct_number_of_results(self, client):
        results = [_make_result(f"Chunk {i}") for i in range(3)]
        with patch("app.services.search_service.SearchService.search", new_callable=AsyncMock,
                   return_value=results):
            data = _search(client).json()
        assert len(data) == 3

    def test_result_contains_expected_fields(self, client):
        with patch("app.services.search_service.SearchService.search", new_callable=AsyncMock,
                   return_value=[_make_result()]):
            data = _search(client).json()
        item = data[0]
        assert "chunk_id" in item
        assert "document_id" in item
        assert "content" in item
        assert "similarity" in item
        assert "chunk_index" in item

    def test_empty_results_returns_empty_list(self, client):
        with patch("app.services.search_service.SearchService.search", new_callable=AsyncMock,
                   return_value=[]):
            data = _search(client).json()
        assert data == []

    def test_search_called_with_query(self, client):
        query = "Quais sao os direitos fundamentais?"
        with patch("app.services.search_service.SearchService.search", new_callable=AsyncMock,
                   return_value=[]) as mock_search:
            _search(client, query=query)
        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs.get("query") == query

    def test_top_k_forwarded(self, client):
        with patch("app.services.search_service.SearchService.search", new_callable=AsyncMock,
                   return_value=[]) as mock_search:
            _search(client, top_k=3)
        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs.get("top_k") == 3

    def test_document_id_filter_forwarded(self, client):
        doc_id = uuid4()
        with patch("app.services.search_service.SearchService.search", new_callable=AsyncMock,
                   return_value=[]) as mock_search:
            _search(client, document_id=doc_id)
        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs.get("document_id") == doc_id


# ── Validacao ─────────────────────────────────────────────────────────────────

class TestSearchValidation:
    def test_empty_query_returns_400(self, client):
        resp = _search(client, query="")
        assert resp.status_code == 400

    def test_whitespace_query_returns_400(self, client):
        resp = _search(client, query="   ")
        assert resp.status_code == 400

    def test_missing_query_field_returns_422(self, client):
        resp = client.post("/api/search", json={"top_k": 5})
        assert resp.status_code == 422
