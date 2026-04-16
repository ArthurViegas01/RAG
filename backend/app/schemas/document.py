"""
Schemas Pydantic para validação de requests/responses da API.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models import DocumentStatus


class ChunkResponse(BaseModel):
    """Chunk para resposta da API."""
    id: UUID
    document_id: UUID
    content: str
    chunk_index: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentCreate(BaseModel):
    """Não precisa de schema create — upload é multipart/form-data."""
    pass


class DocumentResponse(BaseModel):
    """Documento para resposta da API."""
    id: UUID
    filename: str
    status: DocumentStatus
    total_chunks: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentDetailResponse(DocumentResponse):
    """Documento com chunks inclusos."""
    chunks: list[ChunkResponse] = []
