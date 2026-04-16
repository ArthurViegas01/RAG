# Papyrus — Documentação Técnica

## O que é

**Papyrus** é uma aplicação de Q&A sobre documentos usando **RAG (Retrieval-Augmented Generation)**. O usuário faz upload de PDFs ou DOCXs, o sistema indexa o conteúdo, e responde perguntas em linguagem natural citando os trechos originais.

---

## Arquitetura Geral

```
┌─────────────────────────────────────────────────────────────┐
│                        USUÁRIO                               │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP (React → FastAPI)
┌──────────────────────────▼──────────────────────────────────┐
│                    FRONTEND (React + Vite)                   │
│  DocumentUpload │ DocumentList │ ChatInterface               │
│  localhost:5173                                              │
└──────────────────────────┬──────────────────────────────────┘
                           │ /api/* (proxy Vite)
┌──────────────────────────▼──────────────────────────────────┐
│                    BACKEND (FastAPI)                         │
│  POST /api/documents/upload                                  │
│  GET  /api/documents                                         │
│  GET  /api/documents/{id}/status                             │
│  POST /api/search                                            │
│  POST /api/chat                  ← Fase 4                    │
│  localhost:8000                                              │
└───────┬───────────────────────────────────┬─────────────────┘
        │ enfileira task                    │ consulta
        ▼                                   ▼
┌───────────────────┐           ┌───────────────────────────┐
│  Redis (broker)   │           │  PostgreSQL + pgvector     │
│  porta 6379       │           │  tabelas: documents, chunks│
└───────┬───────────┘           │  porta 5432                │
        │ consome task           └───────────────────────────┘
        ▼
┌───────────────────┐
│  Celery Worker    │
│  1. Parse PDF/DOCX│
│  2. Chunking      │
│  3. Embeddings    │
│  4. Salva no DB   │
└───────────────────┘
         │ sentence-transformers (local)
         │ all-MiniLM-L6-v2 (384 dims)
         ▼
┌───────────────────┐
│  Ollama (LLM)     │  ← Fase 4
│  llama3 / mistral │
│  porta 11434      │
└───────────────────┘
```

---

## Stack

| Camada | Tecnologia | Versão | Por quê |
|--------|-----------|--------|---------|
| Frontend | React + Vite | 18 / 5 | SPA moderna, HMR rápido |
| Backend API | FastAPI | 0.115 | Async nativo, Swagger automático |
| ORM | SQLAlchemy (async) | 2.0 | Type-safe, async com asyncpg |
| Vector DB | PostgreSQL + pgvector | 16 | Reutiliza infra existente, sem serviço extra |
| Message Broker | Redis | 7 | Leve, rápido, padrão com Celery |
| Task Queue | Celery | 5.4 | Processamento background em Python |
| Embeddings | sentence-transformers | 3.3 | Gratuito, local, boa qualidade |
| Modelo embedding | all-MiniLM-L6-v2 | — | 384 dims, ~80MB, CPU-friendly |
| LLM | Ollama (llama3) | — | Gratuito, local, sem API key |
| Chunking | LangChain TextSplitters | 0.3 | Respeita sentenças e parágrafos |
| Containers | Docker Compose | — | Orquestra Postgres + Redis |

---

## Fluxo: Upload de Documento

```
1. Usuário seleciona PDF/DOCX no frontend
2. Frontend → POST /api/documents/upload (multipart/form-data)
3. FastAPI valida tipo e tamanho do arquivo
4. FastAPI salva o arquivo em backend/uploads/
5. FastAPI cria registro na tabela `documents` (status: PENDING)
6. FastAPI enfileira task `process_document` no Redis
7. FastAPI retorna { id, filename, status: "pending" } imediatamente
8. [Background] Celery Worker pega a task do Redis:
   a. Marca documento como PROCESSING
   b. Extrai texto (PyMuPDF para PDF, python-docx para DOCX)
   c. Faz chunking com RecursiveCharacterTextSplitter
      - chunk_size: 512 chars
      - chunk_overlap: 50 chars (mantém contexto entre chunks)
   d. Gera embeddings em batch com sentence-transformers
   e. Salva chunks + embeddings na tabela `chunks`
   f. Marca documento como DONE
9. Frontend faz polling a cada 3s em GET /api/documents/{id}/status
10. Quando status == "done", habilita o chat
```

---

## Fluxo: Pergunta (RAG)

```
1. Usuário digita pergunta no chat
2. Frontend → POST /api/chat { question, document_id }
3. FastAPI gera embedding da pergunta (sentence-transformers)
4. FastAPI consulta pgvector:
   SELECT chunks, (1 - embedding <=> query_vector) AS similarity
   FROM chunks
   ORDER BY embedding <=> query_vector
   LIMIT 5
5. FastAPI monta prompt com os chunks relevantes:
   "Você é um assistente. Baseado nos trechos abaixo, responda:
    [chunk1] [chunk2] [chunk3]
    Pergunta: {question}"
6. FastAPI envia prompt para Ollama (llama3)
7. Ollama retorna resposta
8. FastAPI retorna { answer, citations: [{ source, chunk_index, content }] }
9. Frontend renderiza resposta + citações
```

---

## Banco de Dados

### Tabela `documents`

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | UUID | PK, gerado automaticamente |
| filename | VARCHAR(255) | Nome original do arquivo |
| file_path | VARCHAR(512) | Caminho no filesystem |
| file_size_bytes | INTEGER | Tamanho do arquivo |
| status | ENUM | pending / processing / done / error |
| total_chunks | INTEGER | Chunks gerados (0 até DONE) |
| error_message | TEXT | Mensagem de erro (nullable) |
| created_at | TIMESTAMP | Criação |
| updated_at | TIMESTAMP | Última atualização |

### Tabela `chunks`

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | UUID | PK |
| document_id | UUID | FK → documents.id |
| content | TEXT | Texto do chunk |
| chunk_index | INTEGER | Ordem no documento (0, 1, 2...) |
| embedding | VECTOR(384) | Vetor gerado pelo sentence-transformers |
| created_at | TIMESTAMP | Criação |

### Query de Busca Semântica

```sql
SELECT
  c.id,
  c.content,
  c.chunk_index,
  d.filename,
  1 - (c.embedding <=> '[0.12, -0.83, ...]'::vector) AS similarity
FROM chunks c
JOIN documents d ON c.document_id = d.id
WHERE c.embedding IS NOT NULL
ORDER BY c.embedding <=> '[0.12, -0.83, ...]'::vector
LIMIT 5;
```

O operador `<=>` é a **distância de cosseno** do pgvector.
- Resultado 0 = vetores idênticos
- Resultado 1 = vetores ortogonais (sem relação)
- `1 - distância` = similaridade (quanto maior, mais relevante)

---

## Estrutura de Pastas

```
RAG/
├── docker-compose.yml          # PostgreSQL + Redis
├── .env.example                # Variáveis de ambiente (copie para .env)
├── .gitignore
├── ROADMAP.md                  # Plano de desenvolvimento
├── docs/
│   └── ARCHITECTURE.md         # Este arquivo
│
├── backend/
│   ├── Dockerfile              # FastAPI
│   ├── Dockerfile.worker       # Celery Worker
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI app + routers
│       ├── config.py           # Settings via pydantic-settings
│       ├── database.py         # Engine async + init_db
│       ├── celery_app.py       # Config do Celery
│       ├── models/
│       │   └── document.py     # SQLAlchemy: Document, Chunk
│       ├── schemas/
│       │   └── document.py     # Pydantic: request/response DTOs
│       ├── api/
│       │   ├── documents.py    # Endpoints de upload/listagem
│       │   ├── search.py       # Endpoint de busca semântica
│       │   └── chat.py         # Endpoint Q&A (Fase 4)
│       ├── services/
│       │   ├── document_processor.py   # Parse + chunking
│       │   ├── document_repository.py  # CRUD banco de dados
│       │   ├── embedding_service.py    # sentence-transformers
│       │   ├── search_service.py       # pgvector similarity search
│       │   └── chat_service.py         # Prompt + Ollama (Fase 4)
│       └── tasks/
│           └── process_document.py     # Celery task
│
├── frontend/
│   ├── vite.config.js          # Proxy + usePolling (Windows HMR)
│   ├── package.json
│   └── src/
│       ├── App.jsx             # Estado global (docs, activeDoc)
│       ├── styles.css          # Design system (CSS vars + componentes)
│       ├── api/
│       │   └── client.js       # Funções fetch para o backend
│       └── components/
│           ├── DocumentUpload.jsx   # Upload drag & drop
│           ├── DocumentList.jsx     # Lista + polling de status
│           └── ChatInterface.jsx    # Chat + citações
│
└── scripts/
    ├── setup.ps1               # Setup inicial (Windows)
    ├── start-dev.ps1           # Inicia todos os serviços (Windows)
    └── start-dev.sh            # Inicia todos os serviços (Linux/Mac)
```

---

## Variáveis de Ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Conexão com PostgreSQL |
| `REDIS_URL` | `redis://localhost:6379/0` | Conexão com Redis |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Modelo de embeddings |
| `EMBEDDING_DIMENSION` | `384` | Dimensão dos vetores |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL do Ollama |
| `OLLAMA_MODEL` | `llama3` | Modelo LLM |
| `CHUNK_SIZE` | `512` | Tamanho dos chunks (chars) |
| `CHUNK_OVERLAP` | `50` | Overlap entre chunks (chars) |
| `MAX_FILE_SIZE_MB` | `50` | Tamanho máximo de upload |

---

## Como Rodar Localmente

### Pré-requisitos
- Python 3.11+
- Node.js 18+
- Docker Desktop
- Ollama (https://ollama.com) com `ollama pull llama3`

### Setup (uma vez)
```powershell
.\scripts\setup.ps1
```

### Desenvolvimento
```powershell
.\scripts\start-dev.ps1
```

Abre 3 janelas: FastAPI (8000), Celery Worker, Frontend (5173).

### Endpoints disponíveis
- `http://localhost:8000/docs` — Swagger UI
- `http://localhost:8000/health` — Health check
- `http://localhost:5173` — Interface web

---

## Decisões Técnicas

### Por que pgvector em vez de Pinecone/Weaviate?
Empresas já usam PostgreSQL. pgvector é extensão nativa — menos infra, mesmo banco para dados relacionais e vetores. Custo zero.

### Por que sentence-transformers local?
Zero custo, zero latência de rede, sem API key, funciona offline. O `all-MiniLM-L6-v2` tem boa qualidade para retrieval semântico com apenas 384 dimensões.

### Por que Celery?
Documentos grandes levam segundos/minutos para processar. Processar sincronamente travaria a API. Celery permite resposta imediata ao upload e processamento em background.

### Por que FastAPI em vez de Flask/Django?
Async nativo (fundamental para I/O de banco), type hints com Pydantic, documentação automática, performance superior para APIs.

### Por que Ollama?
LLM gratuito, local, sem API key. Fácil trocar o modelo (`ollama pull mistral`, etc.). Demonstra conhecimento de LLMs locais — diferencial em portfolios.

---

## Status do Projeto

| Fase | Status | Descrição |
|------|--------|-----------|
| Fase 1 — Infra | ✅ Completo | Docker, FastAPI, health check |
| Fase 2 — Upload | ✅ Completo | Parse PDF/DOCX, chunking, Celery |
| Fase 3 — Embeddings | ✅ Completo | sentence-transformers, pgvector, busca semântica |
| Fase 4 — RAG/Chat | ✅ Completo | Ollama, prompt engineering, citações |
| Fase 5 — Frontend | 🔄 Em progresso | Chat UI, upload, lista de documentos |
| Fase 6 — Polish | ⏳ Pendente | README, testes, deploy |
