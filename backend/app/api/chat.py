"""
Endpoint de Q&A com RAG.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.config import settings
from app.database import get_db
from app.rate_limit import limiter
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    document_id: UUID | None = None
    top_k: int = Field(default=settings.default_top_k, ge=1, le=20)


class CitationResponse(BaseModel):
    chunk_id: str
    source: str
    chunk_index: int
    content: str
    similarity: float


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
    question: str


@router.post("", response_model=ChatResponse)
@limiter.limit("10/minute")
async def ask(
    request: Request,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Responde uma pergunta usando o pipeline RAG completo.

    Pipeline interno:
      1. Embedding da pergunta
      2. Busca semântica nos chunks (pgvector) filtrada pelo tenant autenticado
      3. Monta prompt com os chunks mais relevantes
      4. Envia para o LLM configurado
      5. Retorna resposta + citações

    Args:
        body.question: Pergunta em linguagem natural
        body.document_id: Filtrar contexto por documento (opcional)
        body.top_k: Quantos chunks usar (1-20)

    Returns:
        ChatResponse com answer, citations, e a question original

    Raises:
        400: Se a pergunta estiver vazia
        401: Sem token válido
        429: Rate limit excedido
        503: Se o LLM não estiver acessível
    """
    if not body.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pergunta não pode ser vazia.",
        )

    try:
        result = await ChatService.ask(
            db=db,
            question=body.question,
            document_id=body.document_id,
            top_k=body.top_k,
            user_id=user_id,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )

    return ChatResponse(
        answer=result.answer,
        citations=[CitationResponse(**c) for c in result.citations],
        question=body.question,
    )
