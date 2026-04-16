"""
Serviço de busca semântica usando pgvector.

Faz busca por similaridade de cosseno entre a query do usuário
e os chunks armazenados no banco de dados.
"""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Document
from app.services.embedding_service import get_embedding_service


class SearchResult:
    """Resultado de uma busca semântica."""

    def __init__(self, chunk: Chunk, similarity: float):
        self.chunk_id = chunk.id
        self.document_id = chunk.document_id
        self.content = chunk.content
        self.chunk_index = chunk.chunk_index
        self.similarity = similarity
        # Populated later
        self.document_filename: str | None = None


class SearchService:
    """
    Busca semântica usando pgvector.

    O operador <=> faz distância de cosseno:
    - 0 = idêntico
    - 1 = completamente diferente
    - (1 - distância) = similaridade
    """

    @staticmethod
    async def search(
        db: AsyncSession,
        query: str,
        top_k: int = 5,
        document_id: UUID | None = None,
        min_similarity: float = 0.3,
    ) -> list[SearchResult]:
        """
        Busca chunks semanticamente similares à query.

        Args:
            db: Sessão do banco
            query: Pergunta ou texto para buscar
            top_k: Quantos resultados retornar
            document_id: Filtrar por documento específico (opcional)
            min_similarity: Similaridade mínima (0-1). Ignora resultados irrelevantes.

        Returns:
            Lista de SearchResult ordenados por similaridade (maior primeiro)
        """
        # 1. Gerar embedding da query
        embedding_service = get_embedding_service()
        query_vector = embedding_service.embed(query)

        # 2. Construir query SQL com pgvector
        # O operador <=> é a distância de cosseno
        # ORDER BY <=> = ordenar do mais similar ao menos similar
        if document_id:
            stmt = (
                select(
                    Chunk,
                    # Converte distância para similaridade: 1 - distância
                    (1 - Chunk.embedding.cosine_distance(query_vector)).label("similarity"),
                )
                .where(Chunk.document_id == document_id)
                .where(Chunk.embedding.is_not(None))
                .order_by(Chunk.embedding.cosine_distance(query_vector))
                .limit(top_k)
            )
        else:
            stmt = (
                select(
                    Chunk,
                    (1 - Chunk.embedding.cosine_distance(query_vector)).label("similarity"),
                )
                .where(Chunk.embedding.is_not(None))
                .order_by(Chunk.embedding.cosine_distance(query_vector))
                .limit(top_k)
            )

        result = await db.execute(stmt)
        rows = result.all()

        # 3. Filtrar por similaridade mínima e montar resultados
        results = []
        for chunk, similarity in rows:
            if similarity >= min_similarity:
                results.append(SearchResult(chunk=chunk, similarity=float(similarity)))

        # 4. Enriquecer com nome do documento
        if results:
            doc_ids = list({r.document_id for r in results})
            docs_stmt = select(Document).where(Document.id.in_(doc_ids))
            docs_result = await db.execute(docs_stmt)
            docs_map = {doc.id: doc.filename for doc in docs_result.scalars().all()}

            for r in results:
                r.document_filename = docs_map.get(r.document_id, "Desconhecido")

        return results
