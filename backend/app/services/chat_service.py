"""
Serviço de chat usando RAG (Retrieval-Augmented Generation).

Pipeline:
  1. Recebe pergunta do usuário
  2. Gera embedding da pergunta
  3. Busca chunks relevantes no pgvector
  4. Monta prompt com os chunks como contexto
  5. Envia para o LLM (Ollama local ou Groq/OpenAI em produção)
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
    chunks_text = []
    for i, r in enumerate(results, 1):
        chunks_text.append(
            f"[Trecho {i} — {r.document_filename}, posição {r.chunk_index + 1}]\n{r.content}"
        )
    context = "\n\n".join(chunks_text)
    return CONTEXT_TEMPLATE.format(context_chunks=context, user_query=query)


# ── LLM Clients ───────────────────────────────────────────────────────────────

async def call_ollama(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    url = f"{settings.ollama_base_url}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 1024},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]
        except httpx.ConnectError:
            raise RuntimeError(
                "Não foi possível conectar ao Ollama. "
                "Verifique se o Ollama está rodando: 'ollama serve'"
            )
        except httpx.TimeoutException:
            raise RuntimeError(
                f"O modelo '{settings.ollama_model}' demorou demais (timeout: 120s)."
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise RuntimeError(
                    f"Modelo '{settings.ollama_model}' não encontrado. "
                    f"Execute: 'ollama pull {settings.ollama_model}'"
                )
            raise RuntimeError(
                f"Ollama retornou erro {exc.response.status_code}: {exc.response.text[:200]}"
            )
        except KeyError:
            raise RuntimeError(f"Resposta inesperada do Ollama: {locals().get('data')}")


async def _call_openai_compatible(
    prompt: str,
    system: str,
    base_url: str,
    api_key: str,
    model: str,
    provider_name: str,
) -> str:
    """
    Cliente genérico para APIs compatíveis com OpenAI (Groq, OpenAI, etc.).
    """
    if not api_key:
        raise RuntimeError(
            f"{provider_name}_API_KEY não configurada. "
            f"Adicione a variável de ambiente e faça redeploy."
        )

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except httpx.ConnectError:
            raise RuntimeError(f"Não foi possível conectar ao {provider_name}.")
        except httpx.TimeoutException:
            raise RuntimeError(f"{provider_name} demorou demais para responder (timeout: 60s).")
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"{provider_name} retornou erro {exc.response.status_code}: "
                f"{exc.response.text[:300]}"
            )
        except (KeyError, IndexError):
            raise RuntimeError(f"Resposta inesperada do {provider_name}.")


async def call_groq(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    return await _call_openai_compatible(
        prompt=prompt,
        system=system,
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        provider_name="Groq",
    )


async def call_openai(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    return await _call_openai_compatible(
        prompt=prompt,
        system=system,
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        provider_name="OpenAI",
    )


async def call_llm(prompt: str) -> str:
    """
    Despacha para o provedor de LLM configurado via LLM_PROVIDER.
      - "ollama"  → Ollama local (padrão para dev)
      - "groq"    → Groq API (recomendado para produção — gratuito)
      - "openai"  → OpenAI API
    """
    provider = settings.llm_provider.lower()
    if provider == "groq":
        return await call_groq(prompt)
    elif provider == "openai":
        return await call_openai(prompt)
    else:
        return await call_ollama(prompt)


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
        results = await SearchService.search(
            db=db,
            query=question,
            top_k=top_k,
            document_id=document_id,
            min_similarity=settings.min_similarity,
        )

        if not results:
            return ChatResult(
                answer=(
                    "Não encontrei trechos relevantes nos documentos carregados para responder essa pergunta. "
                    "Tente reformular ou verifique se o documento foi processado corretamente."
                ),
                sources=[],
            )

        prompt = build_prompt(question, results)
        answer = await call_llm(prompt)
        return ChatResult(answer=answer, sources=results)
