"""
Serviço de chat usando RAG (Retrieval-Augmented Generation).

Pipeline:
  1. Recebe pergunta do usuário
  2. Gera embedding da pergunta
  3. Busca chunks relevantes no pgvector
  4. Monta prompt com os chunks como contexto
  5. Envia para Ollama (LLM local)
  6. Retorna resposta + citações das fontes
"""

from uuid import UUID

import httpx

from app.config import settings
from app.services.search_service import SearchResult, SearchService  # noqa: F401


# ── Prompt Templates ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Você é o Context, um assistente especialista em analisar documentos.

Responda perguntas baseando-se ESTRITAMENTE nos trechos fornecidos. Nunca invente informações.

REGRAS CRÍTICAS DE RACIOCÍNIO:

1. NUMERAÇÃO DOS TRECHOS vs NUMERAÇÃO DO CONTEÚDO:
   Os trechos são numerados apenas para organização (Trecho 1, Trecho 2...).
   Isso NÃO corresponde à numeração do conteúdo (Lei 1, Lei 2...).
   "Trecho 1" NÃO é a "Lei 1". Leia SEMPRE o conteúdo para identificar qual lei/capítulo é.

2. ORDINAIS E SEQUÊNCIAS:
   - "Primeira lei" = Lei número 1. Procure "Lei 1" ou "LEI 1" no conteúdo.
   - "Primeiras 3 leis" = Lei 1, Lei 2 e Lei 3. Procure cada uma no conteúdo dos trechos.
   - Não confunda ordem dos trechos com números das leis.

3. QUANDO PEDIREM AS "PRIMEIRAS N LEIS":
   - Identifique nos trechos as leis com os menores números (Lei 1, Lei 2, Lei 3...).
   - Se nem todas estiverem disponíveis nos trechos, explique quais encontrou e quais não estão nos trechos recuperados.

4. NÃO ENCONTRADO: Se a informação não aparecer nos trechos, diga:
   "Não encontrei essa informação nos trechos recuperados. O documento pode ser longo e
   esse trecho específico pode não ter sido indexado."
   Nunca diga que algo não existe no livro se apenas não apareceu nos trechos.

5. CITAÇÃO: Cite o conteúdo real dos trechos. Mencione o número do trecho apenas como referência.

6. Responda sempre em Português do Brasil.
"""

CONTEXT_TEMPLATE = """---
TRECHOS RECUPERADOS DO DOCUMENTO (numeração abaixo é apenas organizacional, não corresponde ao número das leis/capítulos):

{context_chunks}
---

PERGUNTA DO USUÁRIO: {user_query}

INSTRUÇÃO: Baseie-se SOMENTE no conteúdo acima. Leia o texto de cada trecho para identificar qual lei/capítulo ele contém — não use o número do trecho como referência de conteúdo.

RESPOSTA:"""


def build_prompt(query: str, results: list[SearchResult]) -> str:
    """
    Monta o prompt completo com os chunks como contexto.

    Args:
        query: Pergunta do usuário
        results: Chunks recuperados pela busca semântica

    Returns:
        Prompt formatado para o LLM
    """
    # Formata cada chunk com metadados
    chunks_text = []
    for i, r in enumerate(results, 1):
        chunks_text.append(
            f"[Trecho {i} — {r.document_filename}, posição {r.chunk_index + 1}]\n{r.content}"
        )

    context = "\n\n".join(chunks_text)

    return CONTEXT_TEMPLATE.format(
        context_chunks=context,
        user_query=query,
    )


# ── Ollama Client ─────────────────────────────────────────────────────────────

async def call_ollama(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    """
    Envia prompt para o Ollama e retorna a resposta.

    Usa a API /api/chat do Ollama com formato de mensagens.

    Args:
        prompt: Mensagem do usuário (com contexto)
        system: System prompt

    Returns:
        Texto da resposta gerada pelo LLM

    Raises:
        RuntimeError: Se Ollama não estiver acessível
    """
    url = f"{settings.ollama_base_url}/api/chat"

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "stream": False,  # Resposta completa de uma vez (sem streaming por enquanto)
        "options": {
            "temperature": 0.2,    # Baixo = mais factual, menos criativo
            "num_predict": 1024,   # Máximo de tokens na resposta
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()  # lança HTTPStatusError em 4xx/5xx
            data = response.json()
            return data["message"]["content"]
        except httpx.ConnectError:
            raise RuntimeError(
                "Não foi possível conectar ao Ollama. "
                "Verifique se o Ollama está rodando: 'ollama serve'"
            )
        except httpx.TimeoutException:
            raise RuntimeError(
                f"O modelo '{settings.ollama_model}' demorou demais para responder (timeout: 120s). "
                "Tente uma pergunta mais curta, um modelo menor, ou aumente o timeout."
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise RuntimeError(
                    f"Modelo '{settings.ollama_model}' não encontrado no Ollama. "
                    f"Execute: 'ollama pull {settings.ollama_model}'"
                )
            raise RuntimeError(
                f"Ollama retornou erro {exc.response.status_code}: {exc.response.text[:200]}"
            )
        except KeyError:
            raise RuntimeError(f"Resposta inesperada do Ollama: {data}")


# ── Chat Service ──────────────────────────────────────────────────────────────

class ChatResult:
    """Resultado de uma pergunta RAG."""

    def __init__(self, answer: str, sources: list[SearchResult]):
        self.answer = answer
        self.citations = [
            {
                "chunk_id":    str(r.chunk_id),
                "source":      r.document_filename or "Desconhecido",
                "chunk_index": r.chunk_index,
                "content":     r.content[:200] + "..." if len(r.content) > 200 else r.content,
                "similarity":  round(r.similarity, 3),
            }
            for r in sources
        ]


class ChatService:
    """Orquestra o pipeline RAG completo."""

    @staticmethod
    async def ask(
        db,
        question: str,
        document_id: UUID | None = None,
        top_k: int = 5,
    ) -> ChatResult:
        """
        Responde uma pergunta usando RAG.

        Pipeline:
          pergunta → embedding → busca chunks → prompt → Ollama → resposta + citações

        Args:
            db: Sessão do banco de dados
            question: Pergunta em linguagem natural
            document_id: Filtrar por documento específico (opcional)
            top_k: Quantos chunks usar como contexto

        Returns:
            ChatResult com answer e citations
        """
        # 1. Busca híbrida (semântica + keyword) — encontra chunks relevantes
        results = await SearchService.search(
            db=db,
            query=question,
            top_k=top_k,
            document_id=document_id,
            min_similarity=settings.min_similarity,
        )

        # 2. Nenhum chunk encontrado
        if not results:
            return ChatResult(
                answer=(
                    "Não encontrei trechos relevantes nos documentos carregados para responder essa pergunta. "
                    "Tente reformular ou verifique se o documento foi processado corretamente."
                ),
                sources=[],
            )

        # 3. Monta prompt com os chunks
        prompt = build_prompt(question, results)

        # 4. Chama o LLM
        answer = await call_ollama(prompt)

        return ChatResult(answer=answer, sources=results)
