"""
Endpoint de Q&A com RAG.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    document_id: UUID | None = None   # None = busca em todos os documentos
    top_k: int = 5                    # Quantos chunks usar como contexto


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
async def ask(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Responde uma pergunta usando o pipeline RAG completo.

    Pipeline interno:
      1. Embedding da pergunta
      2. Busca semântica nos chunks (pgvector)
      3. Monta prompt com os chunks mais relevantes
      4. Envia para Ollama (llama3)
      5. Retorna resposta + citações

    Args:
        request.question: Pergunta em linguagem natural
        request.document_id: Filtrar contexto por documento (opcional)
        request.top_k: Quantos chunks usar (padrão: 5)

    Returns:
        ChatResponse com answer, citations, e a question original

    Raises:
        400: Se a pergunta estiver vazia
        503: Se o Ollama não estiver acessível
    """
    if not request.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pergunta não pode ser vazia.",
        )

    try:
        result = await ChatService.ask(
            db=db,
            question=request.question,
            document_id=request.document_id,
            top_k=request.top_k,
        )
    except RuntimeError as e:
        # Erros de conexão com Ollama
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )

    return ChatResponse(
        answer=result.answer,
        citations=[CitationResponse(**c) for c in result.citations],
        question=request.question,
    )
