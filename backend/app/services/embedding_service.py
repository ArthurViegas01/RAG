"""
Serviço de embeddings usando sentence-transformers (local, gratuito).

Modelo: all-MiniLM-L6-v2
- 384 dimensões
- Boa qualidade para busca semântica
- ~80MB, roda em CPU sem problemas
- Download automático na primeira execução
"""

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import settings


class EmbeddingService:
    """
    Gera embeddings de texto usando sentence-transformers.

    O modelo é carregado uma única vez e reutilizado (singleton via lru_cache).
    Na primeira execução, o modelo é baixado automaticamente (~80MB).
    """

    def __init__(self, model_name: str = settings.embedding_model):
        """
        Args:
            model_name: Nome do modelo HuggingFace. Default: all-MiniLM-L6-v2
        """
        print(f"[EmbeddingService] Carregando modelo '{model_name}'...")
        self.model = SentenceTransformer(model_name)
        print(f"[EmbeddingService] Modelo carregado. Dimensão: {self.model.get_sentence_embedding_dimension()}")

    def embed(self, text: str) -> list[float]:
        """
        Gera embedding para um único texto.

        Args:
            text: Texto para gerar embedding

        Returns:
            Lista de floats com o vetor (384 dimensões)
        """
        vector = self.model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """
        Gera embeddings para uma lista de textos de forma eficiente.
        Processar em batch é muito mais rápido que processar um por um.

        Args:
            texts: Lista de textos
            batch_size: Quantos textos processar por vez

        Returns:
            Lista de vetores
        """
        vectors = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 50,  # Mostra progresso para batches grandes
        )
        return [v.tolist() for v in vectors]


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """
    Singleton do EmbeddingService.
    O modelo é carregado apenas uma vez durante a vida da aplicação.

    Returns:
        Instância compartilhada do EmbeddingService
    """
    return EmbeddingService()
