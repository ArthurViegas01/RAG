"""
Serviço para processar documentos: extração de texto e chunking.
"""

import os
import zipfile
from pathlib import Path

import fitz  # PyMuPDF para PDF
from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings


class DocumentParser:
    """Parser genérico de documentos."""

    @staticmethod
    def parse_pdf(file_path: str) -> str:
        """
        Extrai texto de um arquivo PDF.

        Levanta ValueError se o PDF exceder o limite de páginas configurado
        (proteção contra PDFs degenerados / DoS de ingestão).
        """
        pdf = fitz.open(file_path)
        if pdf.page_count > settings.max_pdf_pages:
            pdf.close()
            raise ValueError(
                f"PDF excede o limite de {settings.max_pdf_pages} páginas "
                f"({pdf.page_count} encontradas)."
            )
        text = []
        total_chars = 0
        for page in pdf:
            page_text = page.get_text()
            total_chars += len(page_text)
            if total_chars > settings.max_uncompressed_bytes:
                pdf.close()
                raise ValueError(
                    f"Texto extraído do PDF excede o limite de "
                    f"{settings.max_uncompressed_bytes // (1024 * 1024)} MB."
                )
            text.append(page_text)
        pdf.close()
        return "\n".join(text)

    @staticmethod
    def parse_docx(file_path: str) -> str:
        """
        Extrai texto de um arquivo DOCX.

        Inspeciona o zip antes de descomprimir para detectar zip bombs.
        Levanta ValueError se o tamanho descomprimido exceder o limite.
        """
        with zipfile.ZipFile(file_path) as z:
            total_uncompressed = sum(info.file_size for info in z.infolist())
            if total_uncompressed > settings.max_uncompressed_bytes:
                raise ValueError(
                    f"DOCX descomprimido ({total_uncompressed // (1024 * 1024)} MB) "
                    f"excede o limite de "
                    f"{settings.max_uncompressed_bytes // (1024 * 1024)} MB."
                )
        doc = DocxDocument(file_path)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])

    @staticmethod
    def parse(file_path: str) -> str:
        """
        Parser automático baseado na extensão do arquivo.

        Raises:
            ValueError: Se tipo de arquivo não é suportado
        """
        ext = Path(file_path).suffix.lower()

        if ext == ".pdf":
            return DocumentParser.parse_pdf(file_path)
        elif ext == ".docx":
            return DocumentParser.parse_docx(file_path)
        else:
            raise ValueError(f"Formato de arquivo não suportado: {ext}")


class DocumentChunker:
    """Faz chunking inteligente de texto."""

    def __init__(
        self,
        chunk_size: int = settings.chunk_size,
        chunk_overlap: int = settings.chunk_overlap,
    ):
        # RecursiveCharacterTextSplitter tenta manter sentenças/parágrafos juntos
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def chunk(self, text: str) -> list[str]:
        return self.splitter.split_text(text)


class DocumentProcessingService:
    """Orquestra parsing + chunking."""

    def __init__(self):
        self.parser = DocumentParser()
        self.chunker = DocumentChunker()

    def process(self, file_path: str) -> list[str]:
        """
        Processa um arquivo: extrai texto e faz chunking.

        Raises:
            ValueError: Se arquivo não existe, tipo não suportado, ou excede limites
        """
        if not os.path.exists(file_path):
            raise ValueError(f"Arquivo não existe: {file_path}")

        text = self.parser.parse(file_path)

        if not text.strip():
            raise ValueError(f"Nenhum texto extraído do arquivo: {file_path}")

        chunks = self.chunker.chunk(text)

        return chunks
