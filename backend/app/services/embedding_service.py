"""
Serviço de embeddings usando fastembed (ONNX Runtime, local, gratuito).

Troca sentence-transformers + PyTorch por fastembed para reduzir uso de memória:
  - sentence-transformers + torch CPU: ~350-450 MB em RAM
  - fastembed (ONNX):                  ~80-120 MB em RAM

Modelo: sentence-transformers/all-MiniLM-L6-v2
- 384 dimensões (idêntico ao anterior — sem necessidade de reindexar)
- Boa qualidade para busca semântica
- ~80MB, roda em CPU sem problemas
- Download automático na primeira execução
"""

from functools import lru_cache

from fastembed import TextEmbedding

from app.config import settings

# fastembed usa o prefixo "sentence-transformers/" para modelos do HuggingFace Hub
_FASTEMBED_MODEL_NAME = f"sentence-transformers/{settings.embedding_model}"


class EmbeddingService:
    """
    Gera embeddings de texto usando fastembed (ONNX Runtime).

    O modelo é carregado uma única vez e reutilizado (singleton via lru_cache).
    Na primeira execução, o modelo é baixado automaticamente (~80MB).
    """

    def __init__(self, model_name: str = _FASTEMBED_MODEL_NAME):
        """
        Args:
            model_name: Nome do modelo no formato fastembed. Default: sentence-transformers/all-MiniLM-L6-v2
        """
        print(f"[EmbeddingService] Carregando modelo '{model_name}' via fastembed (ONNX)...")
        self.model = TextEmbedding(model_name=model_name)
        print(f"[EmbeddingService] Modelo carregado.")

    def embed(self, text: str) -> list[float]:
        """
        Gera embedding para um único texto.

        Args:
            text: Texto para gerar embedding

        Returns:
            Lista de floats com o vetor (384 dimensões)
        """
        # fastembed.embed() retorna um generator — pegamos o primeiro (e único) item
        return next(self.model.embed([text])).tolist()

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """
        Gera embeddings para uma lista de textos de forma eficiente.

        Args:
            texts: Lista de textos
            batch_size: Quantos textos processar por vez (passado para fastembed)

        Returns:
            Lista de vetores
        """
        # fastembed.embed() retorna um generator; batch_size controla o tamanho interno
        return [v.tolist() for v in self.model.embed(texts, batch_size=batch_size)]


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """
    Singleton do EmbeddingService.
    O modelo é carregado apenas uma vez durante a vida da aplicação.

    Returns:
        Instância compartilhada do EmbeddingService
    """
    return EmbeddingService()
