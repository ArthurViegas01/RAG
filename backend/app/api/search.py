"""
Endpoint de busca semântica.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.database import get_db
from app.services.search_service import SearchService

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    document_id: UUID | None = None
    top_k: int = Field(5, ge=1, le=20)
    min_similarity: float = 0.3


class SearchResultResponse(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_filename: str | None
    content: str
    chunk_index: int
    similarity: float


@router.post("", response_model=list[SearchResultResponse])
async def semantic_search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Busca semântica por chunks relevantes à query.

    Args:
        request.query: Texto ou pergunta para buscar
        request.document_id: Filtrar por documento (opcional)
        request.top_k: Quantos resultados retornar (1-20)
        request.min_similarity: Similaridade mínima (0-1)

    Returns:
        Lista de chunks ordenados por relevância
    """
    if not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query não pode ser vazia",
        )

    results = await SearchService.search(
        db=db,
        query=request.query,
        top_k=request.top_k,
        document_id=request.document_id,
        min_similarity=request.min_similarity,
        user_id=user_id,
    )

    return [
        SearchResultResponse(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            document_filename=r.document_filename,
            content=r.content,
            chunk_index=r.chunk_index,
            similarity=r.similarity,
        )
        for r in results
    ]
