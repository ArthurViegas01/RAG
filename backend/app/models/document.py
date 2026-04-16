"""
Modelos SQLAlchemy para documentos e chunks.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class DocumentStatus(str, Enum):
    """Estados possíveis de um documento durante o processamento."""
    PENDING = "pending"        # Aceito, aguardando processamento
    PROCESSING = "processing"  # Sendo processado (chunking + embeddings)
    DONE = "done"              # Pronto, chunks e embeddings salvos
    ERROR = "error"            # Erro durante processamento


class Document(Base):
    """
    Modelo para documentos enviados pelo usuário.
    Rastreia o status, localização e metadados do arquivo.
    """
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)

    # Status do processamento
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False)

    # Metadata de processamento
    total_chunks = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relacionamento
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document(id={self.id}, filename={self.filename}, status={self.status})>"


class Chunk(Base):
    """
    Modelo para fragmentos de texto extraído de um documento.
    Cada chunk é armazenado com seu embedding (vector).
    """
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)

    # Conteúdo e posição
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)  # Ordem dentro do documento

    # Embedding (vetor 384 dimensões para all-MiniLM-L6-v2)
    # pgvector permite queries por similaridade (cosine distance, etc)
    embedding = Column(Vector(384), nullable=True)  # None até Fase 3

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relacionamento
    document = relationship("Document", back_populates="chunks")

    def __repr__(self):
        return f"<Chunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"
