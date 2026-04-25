"""
Testes de validacao para o endpoint de upload: tipos invalidos e tamanho maximo.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
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
        yield AsyncMock()

    app.dependency_overrides[get_db] = fake_db
    with TestClient(app, raise_server_exceptions=False) as c:
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


def _upload(client, content=b"data", filename="doc.pdf",
            content_type="application/pdf"):
    return client.post(
        "/api/documents/upload",
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


# ── Invalid extension tests ───────────────────────────────────────────────────

class TestInvalidExtensions:
    @pytest.mark.parametrize("filename,content_type", [
        ("image.png", "image/png"),
        ("data.csv", "text/csv"),
        ("readme.txt", "text/plain"),
        ("malware.exe", "application/octet-stream"),
        ("sheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ])
    def test_invalid_extension_returns_400(self, client, filename, content_type):
        resp = _upload(client, filename=filename, content_type=content_type)
        assert resp.status_code == 400

    def test_valid_pdf_passes_validation(self, client):
        fake_doc = _make_doc()
        fake_task = MagicMock()
        fake_task.id = "v1"

        with patch("app.api.documents.DocumentRepository.count_by_filename", new_callable=AsyncMock, return_value=0), \
             patch("app.api.documents.DocumentRepository.create", new_callable=AsyncMock, return_value=fake_doc), \
             patch("app.api.documents._store_file"), \
             patch("app.api.documents.process_document") as mock_task:
            mock_task.delay.return_value = fake_task
            resp = _upload(client, filename="doc.pdf", content_type="application/pdf")

        assert resp.status_code == 201

    def test_valid_docx_passes_validation(self, client):
        fake_doc = _make_doc(filename="doc.docx")
        fake_task = MagicMock()
        fake_task.id = "v2"

        with patch("app.api.documents.DocumentRepository.count_by_filename", new_callable=AsyncMock, return_value=0), \
             patch("app.api.documents.DocumentRepository.create", new_callable=AsyncMock, return_value=fake_doc), \
             patch("app.api.documents._store_file"), \
             patch("app.api.documents.process_document") as mock_task:
            mock_task.delay.return_value = fake_task
            resp = _upload(
                client,
                filename="doc.docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        assert resp.status_code == 201


# ── File size validation ──────────────────────────────────────────────────────

class TestFileSizeValidation:
    def test_oversized_file_returns_413(self, client):
        """Arquivo maior que MAX_FILE_SIZE_MB deve retornar 413."""
        from app.config import settings
        max_bytes = settings.max_file_size_mb * 1024 * 1024
        oversized = b"x" * (max_bytes + 1)
        with patch("app.api.documents.DocumentRepository.count_by_filename",
                   new_callable=AsyncMock, return_value=0):
            resp = _upload(client, content=oversized, filename="big.pdf")
        assert resp.status_code == 413
