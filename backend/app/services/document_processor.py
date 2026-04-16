"""
Serviço para processar documentos: extração de texto e chunking.
"""

import os
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

        Args:
            file_path: Caminho para o arquivo PDF

        Returns:
            Texto completo extraído do PDF
        """
        text = []
        pdf = fitz.open(file_path)
        for page in pdf:
            text.append(page.get_text())
        pdf.close()
        return "\n".join(text)

    @staticmethod
    def parse_docx(file_path: str) -> str:
        """
        Extrai texto de um arquivo DOCX.

        Args:
            file_path: Caminho para o arquivo DOCX

        Returns:
            Texto completo extraído do DOCX
        """
        doc = DocxDocument(file_path)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])

    @staticmethod
    def parse(file_path: str) -> str:
        """
        Parser automático baseado na extensão do arquivo.

        Args:
            file_path: Caminho do arquivo

        Returns:
            Texto extraído

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
        """
        Args:
            chunk_size: Tamanho máximo de cada chunk (tokens/caracteres)
            chunk_overlap: Sobreposição entre chunks para manter contexto
        """
        # RecursiveCharacterTextSplitter tenta manter sentenças/parágrafos juntos
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            # Tenta quebrar nesta ordem de preferência
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def chunk(self, text: str) -> list[str]:
        """
        Divide texto em chunks.

        Args:
            text: Texto para dividir

        Returns:
            Lista de chunks
        """
        return self.splitter.split_text(text)


class DocumentProcessingService:
    """Orquestra parsing + chunking."""

    def __init__(self):
        self.parser = DocumentParser()
        self.chunker = DocumentChunker()

    def process(self, file_path: str) -> list[str]:
        """
        Processa um arquivo: extrai texto e faz chunking.

        Args:
            file_path: Caminho do arquivo

        Returns:
            Lista de chunks de texto

        Raises:
            ValueError: Se arquivo não existe ou tipo não suportado
        """
        if not os.path.exists(file_path):
            raise ValueError(f"Arquivo não existe: {file_path}")

        # Parse
        text = self.parser.parse(file_path)

        if not text.strip():
            raise ValueError(f"Nenhum texto extraído do arquivo: {file_path}")

        # Chunking
        chunks = self.chunker.chunk(text)

        return chunks
