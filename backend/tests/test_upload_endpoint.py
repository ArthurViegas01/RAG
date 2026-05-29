"""
Testes unitarios para o endpoint de upload de documentos.

Celery, DB e Redis sao todos mockados — nenhum servico externo necessario.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True, scope="module")
def mock_startup():
    """Impede que o startup event tente conectar ao banco de dados."""
    with patch("app.main.init_db", new_callable=AsyncMock), \
         patch("app.main._reset_stuck_documents", new_callable=AsyncMock):
        yield


@pytest.fixture(scope="module")
def client(mock_startup):
    """TestClient com startup mockado e get_db substituido."""
    from app.main import app
    from app.database import get_db

    async def fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = fake_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_doc(filename="relatorio.pdf"):
    from app.models import DocumentStatus
    doc = MagicMock()
    doc.id = uuid4()
    doc.filename = filename
    doc.celery_task_id = None
    doc.status = DocumentStatus.PENDING
    doc.total_chunks = 0
    doc.error_message = None
    doc.created_at = _NOW
    doc.updated_at = _NOW
    return doc


def _upload(client, content=b"PDF simulado", filename="relatorio.pdf",
            content_type="application/pdf"):
    return client.post(
        "/api/documents/upload",
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


# ── Happy path ────────────────────────────────────────────────────────────────

class TestUploadHappyPath:
    def test_returns_201(self, client):
        fake_doc = _make_doc()
        fake_task = MagicMock()
        fake_task.id = "celery-task-xyz"

        with patch("app.api.documents.DocumentRepository.count_by_filename", new_callable=AsyncMock, return_value=0), \
             patch("app.api.documents.DocumentRepository.create", new_callable=AsyncMock, return_value=fake_doc), \
             patch("app.api.documents._store_file"), \
             patch("app.api.documents.process_document") as mock_task:
            mock_task.delay.return_value = fake_task
            resp = _upload(client)

        assert resp.status_code == 201

    def test_response_contains_document_id(self, client):
        fake_doc = _make_doc()
        fake_doc.id = UUID("12345678-1234-5678-1234-567812345678")
        fake_task = MagicMock()
        fake_task.id = "t1"

        with patch("app.api.documents.DocumentRepository.count_by_filename", new_callable=AsyncMock, return_value=0), \
             patch("app.api.documents.DocumentRepository.create", new_callable=AsyncMock, return_value=fake_doc), \
             patch("app.api.documents._store_file"), \
             patch("app.api.documents.process_document") as mock_task:
            mock_task.delay.return_value = fake_task
            data = _upload(client).json()

        assert data["id"] == "12345678-1234-5678-1234-567812345678"

    def test_celery_task_dispatched_once(self, client):
        fake_doc = _make_doc()
        fake_task = MagicMock()
        fake_task.id = "t2"

        with patch("app.api.documents.DocumentRepository.count_by_filename", new_callable=AsyncMock, return_value=0), \
             patch("app.api.documents.DocumentRepository.create", new_callable=AsyncMock, return_value=fake_doc), \
             patch("app.api.documents._store_file"), \
             patch("app.api.documents.process_document") as mock_task:
            mock_task.delay.return_value = fake_task
            _upload(client)

        mock_task.delay.assert_called_once()

    def test_celery_task_receives_doc_id(self, client):
        fake_doc = _make_doc()
        fake_doc.id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        fake_task = MagicMock()
        fake_task.id = "t3"

        with patch("app.api.documents.DocumentRepository.count_by_filename", new_callable=AsyncMock, return_value=0), \
             patch("app.api.documents.DocumentRepository.create", new_callable=AsyncMock, return_value=fake_doc), \
             patch("app.api.documents._store_file"), \
             patch("app.api.documents.process_document") as mock_task:
            mock_task.delay.return_value = fake_task
            _upload(client)

        assert mock_task.delay.call_args[0][0] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def test_celery_task_receives_file_extension(self, client):
        fake_doc = _make_doc(filename="doc.docx")
        fake_task = MagicMock()
        fake_task.id = "t4"

        with patch("app.api.documents.DocumentRepository.count_by_filename", new_callable=AsyncMock, return_value=0), \
             patch("app.api.documents.DocumentRepository.create", new_callable=AsyncMock, return_value=fake_doc), \
             patch("app.api.documents._store_file"), \
             patch("app.api.documents.process_document") as mock_task:
            mock_task.delay.return_value = fake_task
            _upload(client, filename="doc.docx",
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        assert mock_task.delay.call_args[0][1] == ".docx"

    def test_file_stored_in_redis(self, client):
        fake_doc = _make_doc()
        fake_task = MagicMock()
        fake_task.id = "t5"

        with patch("app.api.documents.DocumentRepository.count_by_filename", new_callable=AsyncMock, return_value=0), \
             patch("app.api.documents.DocumentRepository.create", new_callable=AsyncMock, return_value=fake_doc), \
             patch("app.api.documents._store_file") as mock_store, \
             patch("app.api.documents.process_document") as mock_task:
            mock_task.delay.return_value = fake_task
            _upload(client, content=b"conteudo do pdf")

        mock_store.assert_called_once()
        assert mock_store.call_args[0][1] == b"conteudo do pdf"

    def test_docx_upload_returns_201(self, client):
        fake_doc = _make_doc(filename="relatorio.docx")
        fake_task = MagicMock()
        fake_task.id = "t6"

        with patch("app.api.documents.DocumentRepository.count_by_filename", new_callable=AsyncMock, return_value=0), \
             patch("app.api.documents.DocumentRepository.create", new_callable=AsyncMock, return_value=fake_doc), \
             patch("app.api.documents._store_file"), \
             patch("app.api.documents.process_document") as mock_task:
            mock_task.delay.return_value = fake_task
            resp = _upload(client, filename="relatorio.docx",
                           content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        assert resp.status_code == 201


# ── Duplicate detection ───────────────────────────────────────────────────────

class TestDuplicateDetection:
    def test_duplicate_sets_warning_header(self, client):
        fake_doc = _make_doc()
        fake_task = MagicMock()
        fake_task.id = "t7"

        with patch("app.api.documents.DocumentRepository.count_by_filename", new_callable=AsyncMock, return_value=2), \
             patch("app.api.documents.DocumentRepository.create", new_callable=AsyncMock, return_value=fake_doc), \
             patch("app.api.documents._store_file"), \
             patch("app.api.documents.process_document") as mock_task:
            mock_task.delay.return_value = fake_task
            resp = _upload(client)

        assert "X-Duplicate-Warning" in resp.headers

    def test_no_duplicate_no_warning_header(self, client):
        fake_doc = _make_doc()
        fake_task = MagicMock()
        fake_task.id = "t8"

        with patch("app.api.documents.DocumentRepository.count_by_filename", new_callable=AsyncMock, return_value=0), \
             patch("app.api.documents.DocumentRepository.create", new_callable=AsyncMock, return_value=fake_doc), \
             patch("app.api.documents._store_file"), \
             patch("app.api.documents.process_document") as mock_task:
            mock_task.delay.return_value = fake_task
            resp = _upload(client)

        assert "X-Duplicate-Warning" not in resp.headers
