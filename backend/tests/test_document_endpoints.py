"""
Testes unitarios para endpoints de documentos: list, get, status, delete.

DB mockado — nenhum servico externo necessario.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


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
        yield AsyncMock()

    app.dependency_overrides[get_db] = fake_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


def _make_doc(doc_id=None, filename="relatorio.pdf", status=None, chunks=None):
    from app.models import DocumentStatus
    doc = MagicMock()
    doc.id = doc_id or uuid4()
    doc.filename = filename
    doc.celery_task_id = None
    doc.status = status or DocumentStatus.DONE
    doc.total_chunks = len(chunks) if chunks else 3
    doc.error_message = None
    doc.created_at = _NOW
    doc.updated_at = _NOW
    doc.chunks = chunks or []
    return doc


# ── GET /api/documents ────────────────────────────────────────────────────────

class TestListDocuments:
    def test_returns_200(self, client):
        with patch("app.api.documents.DocumentRepository.list_all",
                   new_callable=AsyncMock, return_value=[]):
            resp = client.get("/api/documents")
        assert resp.status_code == 200

    def test_returns_list(self, client):
        docs = [_make_doc(), _make_doc()]
        with patch("app.api.documents.DocumentRepository.list_all",
                   new_callable=AsyncMock, return_value=docs):
            data = client.get("/api/documents").json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_empty_list(self, client):
        with patch("app.api.documents.DocumentRepository.list_all",
                   new_callable=AsyncMock, return_value=[]):
            data = client.get("/api/documents").json()
        assert data == []

    def test_response_has_required_fields(self, client):
        with patch("app.api.documents.DocumentRepository.list_all",
                   new_callable=AsyncMock, return_value=[_make_doc()]):
            data = client.get("/api/documents").json()
        item = data[0]
        assert "id" in item
        assert "filename" in item
        assert "status" in item
        assert "total_chunks" in item


# ── GET /api/documents/{id} ───────────────────────────────────────────────────

class TestGetDocument:
    def test_returns_200_when_found(self, client):
        doc = _make_doc()
        with patch("app.api.documents.DocumentRepository.get_by_id_with_chunks",
                   new_callable=AsyncMock, return_value=doc):
            resp = client.get(f"/api/documents/{doc.id}")
        assert resp.status_code == 200

    def test_returns_404_when_not_found(self, client):
        with patch("app.api.documents.DocumentRepository.get_by_id_with_chunks",
                   new_callable=AsyncMock, return_value=None):
            resp = client.get(f"/api/documents/{uuid4()}")
        assert resp.status_code == 404

    def test_response_has_chunks_field(self, client):
        doc = _make_doc()
        with patch("app.api.documents.DocumentRepository.get_by_id_with_chunks",
                   new_callable=AsyncMock, return_value=doc):
            data = client.get(f"/api/documents/{doc.id}").json()
        assert "chunks" in data

    def test_invalid_uuid_returns_422(self, client):
        resp = client.get("/api/documents/nao-e-uuid")
        assert resp.status_code == 422


# ── GET /api/documents/{id}/status ───────────────────────────────────────────

class TestGetDocumentStatus:
    def test_returns_200_when_found(self, client):
        doc = _make_doc()
        with patch("app.api.documents.DocumentRepository.get_by_id",
                   new_callable=AsyncMock, return_value=doc):
            resp = client.get(f"/api/documents/{doc.id}/status")
        assert resp.status_code == 200

    def test_returns_404_when_not_found(self, client):
        with patch("app.api.documents.DocumentRepository.get_by_id",
                   new_callable=AsyncMock, return_value=None):
            resp = client.get(f"/api/documents/{uuid4()}/status")
        assert resp.status_code == 404

    def test_response_contains_status_field(self, client):
        doc = _make_doc()
        with patch("app.api.documents.DocumentRepository.get_by_id",
                   new_callable=AsyncMock, return_value=doc):
            data = client.get(f"/api/documents/{doc.id}/status").json()
        assert "status" in data
        assert "total_chunks" in data


# ── DELETE /api/documents/{id} ────────────────────────────────────────────────

class TestDeleteDocument:
    def test_returns_204_when_found(self, client):
        doc = _make_doc()
        doc.celery_task_id = None
        with patch("app.api.documents.DocumentRepository.get_by_id",
                   new_callable=AsyncMock, return_value=doc), \
             patch("app.api.documents._delete_file"):
            resp = client.delete(f"/api/documents/{doc.id}")
        assert resp.status_code == 204

    def test_returns_404_when_not_found(self, client):
        with patch("app.api.documents.DocumentRepository.get_by_id",
                   new_callable=AsyncMock, return_value=None):
            resp = client.delete(f"/api/documents/{uuid4()}")
        assert resp.status_code == 404

    def test_invalid_uuid_returns_422(self, client):
        resp = client.delete("/api/documents/nao-e-uuid")
        assert resp.status_code == 422


# ── POST /api/chat ─────────────────────────────────────────────────────────────

class TestChatEndpoint:
    def test_empty_question_returns_400(self, client):
        resp = client.post("/api/chat", json={"question": ""})
        assert resp.status_code == 400

    def test_whitespace_question_returns_400(self, client):
        resp = client.post("/api/chat", json={"question": "   "})
        assert resp.status_code == 400

    def test_missing_question_returns_422(self, client):
        resp = client.post("/api/chat", json={"top_k": 5})
        assert resp.status_code == 422

    def test_ollama_unavailable_returns_503(self, client):
        with patch("app.api.chat.ChatService.ask",
                   new_callable=AsyncMock,
                   side_effect=RuntimeError("Ollama offline")):
            resp = client.post("/api/chat", json={"question": "O que e RAG?"})
        assert resp.status_code == 503

    def test_valid_question_returns_200(self, client):
        result = MagicMock()
        result.answer = "RAG combina busca e geracao."
        result.citations = []
        with patch("app.api.chat.ChatService.ask",
                   new_callable=AsyncMock, return_value=result):
            resp = client.post("/api/chat", json={"question": "O que e RAG?"})
        assert resp.status_code == 200

    def test_response_has_required_fields(self, client):
        result = MagicMock()
        result.answer = "Resposta."
        result.citations = []
        with patch("app.api.chat.ChatService.ask",
                   new_callable=AsyncMock, return_value=result):
            data = client.post("/api/chat", json={"question": "pergunta"}).json()
        assert "answer" in data
        assert "citations" in data
        assert "question" in data


# ── GET /health ────────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_response_has_status_field(self, client):
        data = client.get("/health").json()
        assert data["status"] == "healthy"

    def test_response_has_version(self, client):
        data = client.get("/health").json()
        assert "version" in data
