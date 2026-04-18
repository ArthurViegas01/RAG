"""
Repository para operações de banco de dados relacionadas a documentos e chunks.
Abstrai a lógica de database do resto da aplicação.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Chunk, Document, DocumentStatus


class DocumentRepository:
    """CRUD + queries customizadas para Document."""

    @staticmethod
    async def create(
        db: AsyncSession,
        filename: str,
        file_path: str,
        file_size_bytes: int,
    ) -> Document:
        """Cria um novo documento com status PENDING."""
        doc = Document(
            filename=filename,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            status=DocumentStatus.PENDING,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return doc

    @staticmethod
    async def get_by_id(db: AsyncSession, doc_id: UUID) -> Document | None:
        """Busca documento por ID."""
        stmt = select(Document).where(Document.id == doc_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id_with_chunks(db: AsyncSession, doc_id: UUID) -> Document | None:
        """Busca documento com seus chunks."""
        stmt = (
            select(Document)
            .where(Document.id == doc_id)
            .options(selectinload(Document.chunks))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def count_by_filename(db: AsyncSession, filename: str) -> int:
        """Conta quantos documentos com o mesmo nome de arquivo já existem."""
        stmt = select(func.count()).where(Document.filename == filename)
        result = await db.execute(stmt)
        return result.scalar_one()

    @staticmethod
    async def list_all(db: AsyncSession, limit: int = 100, offset: int = 0) -> list[Document]:
        """Lista todos os documentos com paginação."""
        stmt = select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def update_status(db: AsyncSession, doc_id: UUID, status: DocumentStatus) -> Document:
        """Atualiza o status de um documento."""
        doc = await DocumentRepository.get_by_id(db, doc_id)
        if not doc:
            raise ValueError(f"Documento não encontrado: {doc_id}")
        doc.status = status
        await db.commit()
        await db.refresh(doc)
        return doc

    @staticmethod
    async def update_on_success(
        db: AsyncSession,
        doc_id: UUID,
        total_chunks: int,
    ) -> Document:
        """Marca documento como DONE e atualiza total_chunks."""
        doc = await DocumentRepository.get_by_id(db, doc_id)
        if not doc:
            raise ValueError(f"Documento não encontrado: {doc_id}")
        doc.status = DocumentStatus.DONE
        doc.total_chunks = total_chunks
        await db.commit()
        await db.refresh(doc)
        return doc

    @staticmethod
    async def update_on_error(db: AsyncSession, doc_id: UUID, error_message: str) -> Document:
        """Marca documento como ERROR."""
        doc = await DocumentRepository.get_by_id(db, doc_id)
        if not doc:
            raise ValueError(f"Documento não encontrado: {doc_id}")
        doc.status = DocumentStatus.ERROR
        doc.error_message = error_message
        await db.commit()
        await db.refresh(doc)
        return doc


class ChunkRepository:
    """CRUD + queries para Chunk."""

    @staticmethod
    async def create_many(
        db: AsyncSession,
        document_id: UUID,
        chunks_text: list[str],
    ) -> list[Chunk]:
        """
        Cria múltiplos chunks para um documento.

        Args:
            db: Sessão do banco
            document_id: ID do documento
            chunks_text: Lista de textos para criar chunks

        Returns:
            Lista de chunks criados
        """
        chunks = [
            Chunk(
                document_id=document_id,
                content=text,
                chunk_index=i,
            )
            for i, text in enumerate(chunks_text)
        ]
        db.add_all(chunks)
        await db.commit()
        # Refresh para pegar IDs gerados
        for chunk in chunks:
            await db.refresh(chunk)
        return chunks

    @staticmethod
    async def get_by_document(db: AsyncSession, document_id: UUID) -> list[Chunk]:
        """Busca todos os chunks de um documento."""
        stmt = (
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_by_id(db: AsyncSession, chunk_id: UUID) -> Chunk | None:
        """Busca um chunk por ID."""
        stmt = select(Chunk).where(Chunk.id == chunk_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_embedding(db: AsyncSession, chunk_id: UUID, embedding: list[float]):
        """Atualiza o embedding de um chunk."""
        chunk = await ChunkRepository.get_by_id(db, chunk_id)
        if not chunk:
            raise ValueError(f"Chunk não encontrado: {chunk_id}")
        chunk.embedding = embedding
        await db.commit()
