"""
Testes unitarios para o pipeline de chunking e parsing de documentos.

Nenhum servico externo necessario — fitz e python-docx sao mockados.
sentence_transformers e mockado via conftest.py.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# Pre-importa o modulo para que o patch por caminho de string funcione
import app.services.document_processor  # noqa: F401


# ---------------------------------------------------------------------------
# DocumentChunker
# ---------------------------------------------------------------------------

class TestDocumentChunker:
    """Testa o chunking com RecursiveCharacterTextSplitter (sem mocks)."""

    @pytest.fixture
    def chunker(self):
        from app.services.document_processor import DocumentChunker
        return DocumentChunker(chunk_size=100, chunk_overlap=20)

    def test_short_text_produces_chunks(self, chunker):
        chunks = chunker.chunk("Texto curto de exemplo.")
        assert isinstance(chunks, list)
        assert len(chunks) >= 1

    def test_long_text_is_split_into_multiple_chunks(self, chunker):
        text = "Palavra " * 200  # ~1600 chars
        chunks = chunker.chunk(text)
        assert len(chunks) > 1

    def test_chunks_are_non_empty_strings(self, chunker):
        text = "Este e um documento de teste. " * 20
        chunks = chunker.chunk(text)
        for chunk in chunks:
            assert isinstance(chunk, str)
            assert chunk.strip() != ""

    def test_chunk_size_respected(self, chunker):
        text = "a" * 1000
        chunks = chunker.chunk(text)
        for chunk in chunks:
            assert len(chunk) <= 150  # margem razoavel

    def test_custom_chunk_size(self):
        from app.services.document_processor import DocumentChunker
        chunker = DocumentChunker(chunk_size=50, chunk_overlap=5)
        text = "Frase exemplo. " * 50
        chunks = chunker.chunk(text)
        assert len(chunks) > 1

    def test_uses_settings_defaults(self):
        from app.services.document_processor import DocumentChunker
        chunker = DocumentChunker()
        chunks = chunker.chunk("Texto. " * 500)
        assert len(chunks) >= 1

    def test_empty_string_returns_list(self, chunker):
        chunks = chunker.chunk("")
        assert isinstance(chunks, list)


# ---------------------------------------------------------------------------
# DocumentParser — PDF
# ---------------------------------------------------------------------------

def _make_mock_pdf(pages_text: list[str]) -> MagicMock:
    """Cria um mock de fitz.Document com page_count e iteracao configurados."""
    pages = []
    for t in pages_text:
        p = MagicMock()
        p.get_text.return_value = t
        pages.append(p)
    mock_pdf = MagicMock()
    mock_pdf.page_count = len(pages)
    mock_pdf.__iter__ = MagicMock(return_value=iter(pages))
    mock_pdf.close = MagicMock()
    return mock_pdf


class TestDocumentParserPDF:
    """Testa parse de PDF com fitz mockado."""

    def test_parse_pdf_returns_text(self):
        from app.services.document_processor import DocumentParser

        mock_pdf = _make_mock_pdf(["Conteudo da pagina PDF."])
        with patch("fitz.open", return_value=mock_pdf):
            result = DocumentParser.parse_pdf("fake.pdf")

        assert "Conteudo da pagina PDF." in result

    def test_parse_pdf_multiple_pages(self):
        from app.services.document_processor import DocumentParser

        mock_pdf = _make_mock_pdf(["Pagina 1.", "Pagina 2."])
        with patch("fitz.open", return_value=mock_pdf):
            result = DocumentParser.parse_pdf("fake.pdf")

        assert "Pagina 1." in result
        assert "Pagina 2." in result

    def test_parse_pdf_joins_pages_with_newline(self):
        from app.services.document_processor import DocumentParser

        mock_pdf = _make_mock_pdf(["A", "B"])
        with patch("fitz.open", return_value=mock_pdf):
            result = DocumentParser.parse_pdf("fake.pdf")

        assert result == "A\nB"

    def test_parse_pdf_raises_if_too_many_pages(self):
        from app.services.document_processor import DocumentParser
        from app.config import settings

        mock_pdf = MagicMock()
        mock_pdf.page_count = settings.max_pdf_pages + 1
        mock_pdf.close = MagicMock()
        with patch("fitz.open", return_value=mock_pdf):
            with pytest.raises(ValueError, match="limite"):
                DocumentParser.parse_pdf("gigante.pdf")


# ---------------------------------------------------------------------------
# DocumentParser — DOCX
# ---------------------------------------------------------------------------

def _mock_zipfile(uncompressed_bytes: int = 100):
    """Retorna um context manager mock para zipfile.ZipFile."""
    mock_info = MagicMock()
    mock_info.file_size = uncompressed_bytes
    mock_zf = MagicMock()
    mock_zf.__enter__ = MagicMock(return_value=mock_zf)
    mock_zf.__exit__ = MagicMock(return_value=False)
    mock_zf.infolist.return_value = [mock_info]
    return mock_zf


class TestDocumentParserDOCX:
    """Testa parse de DOCX com python-docx mockado."""

    def test_parse_docx_returns_text(self):
        from app.services.document_processor import DocumentParser

        para1 = MagicMock()
        para1.text = "Paragrafo um."
        para2 = MagicMock()
        para2.text = "Paragrafo dois."
        mock_doc = MagicMock()
        mock_doc.paragraphs = [para1, para2]

        with patch("app.services.document_processor.zipfile.ZipFile", return_value=_mock_zipfile()), \
             patch("app.services.document_processor.DocxDocument", return_value=mock_doc):
            result = DocumentParser.parse_docx("fake.docx")

        assert "Paragrafo um." in result
        assert "Paragrafo dois." in result

    def test_parse_docx_joins_paragraphs(self):
        from app.services.document_processor import DocumentParser

        para1 = MagicMock()
        para1.text = "X"
        para2 = MagicMock()
        para2.text = "Y"
        mock_doc = MagicMock()
        mock_doc.paragraphs = [para1, para2]

        with patch("app.services.document_processor.zipfile.ZipFile", return_value=_mock_zipfile()), \
             patch("app.services.document_processor.DocxDocument", return_value=mock_doc):
            result = DocumentParser.parse_docx("fake.docx")

        assert result == "X\nY"

    def test_parse_docx_raises_if_zip_bomb(self):
        from app.services.document_processor import DocumentParser
        from app.config import settings

        huge = settings.max_uncompressed_bytes + 1
        with patch("app.services.document_processor.zipfile.ZipFile", return_value=_mock_zipfile(huge)):
            with pytest.raises(ValueError, match="limite"):
                DocumentParser.parse_docx("bomb.docx")


# ---------------------------------------------------------------------------
# DocumentParser — roteamento por extensao
# ---------------------------------------------------------------------------

class TestDocumentParserRouter:
    """Testa DocumentParser.parse() — roteamento por extensao."""

    def test_parse_routes_pdf(self):
        from app.services.document_processor import DocumentParser
        with patch.object(DocumentParser, "parse_pdf", return_value="PDF text"):
            result = DocumentParser.parse("documento.pdf")
        assert result == "PDF text"

    def test_parse_routes_docx(self):
        from app.services.document_processor import DocumentParser
        with patch.object(DocumentParser, "parse_docx", return_value="DOCX text"):
            result = DocumentParser.parse("documento.docx")
        assert result == "DOCX text"

    def test_parse_raises_for_unsupported_extension(self):
        from app.services.document_processor import DocumentParser
        with pytest.raises(ValueError, match="suportado"):
            DocumentParser.parse("arquivo.txt")

    def test_parse_raises_for_png(self):
        from app.services.document_processor import DocumentParser
        with pytest.raises(ValueError):
            DocumentParser.parse("imagem.png")


# ---------------------------------------------------------------------------
# DocumentProcessingService
# ---------------------------------------------------------------------------

class TestDocumentProcessingService:
    """Testa a orquestracao de parse + chunking."""

    def test_process_returns_chunks(self, tmp_path):
        from app.services.document_processor import DocumentProcessingService

        fake_file = tmp_path / "doc.pdf"
        fake_file.write_bytes(b"%PDF-1.4 fake")

        with patch("app.services.document_processor.DocumentParser.parse", return_value="Texto extraido."), \
             patch("app.services.document_processor.DocumentChunker.chunk", return_value=["Chunk 1", "Chunk 2"]):
            svc = DocumentProcessingService()
            chunks = svc.process(str(fake_file))

        assert chunks == ["Chunk 1", "Chunk 2"]

    def test_process_raises_if_file_not_found(self):
        from app.services.document_processor import DocumentProcessingService
        svc = DocumentProcessingService()
        with pytest.raises(ValueError, match="existe"):
            svc.process("/caminho/inexistente/arquivo.pdf")

    def test_process_raises_if_text_is_empty(self, tmp_path):
        from app.services.document_processor import DocumentProcessingService

        fake_file = tmp_path / "vazio.pdf"
        fake_file.write_bytes(b"%PDF-1.4 fake")

        with patch("app.services.document_processor.DocumentParser.parse", return_value="   "):
            svc = DocumentProcessingService()
            with pytest.raises(ValueError, match="Nenhum texto"):
                svc.process(str(fake_file))
