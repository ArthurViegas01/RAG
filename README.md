# Context RAG

[![CI](https://github.com/ArthurViegas01/RAG/actions/workflows/ci.yml/badge.svg)](https://github.com/ArthurViegas01/RAG/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ArthurViegas01/RAG/branch/main/graph/badge.svg)](https://codecov.io/gh/ArthurViegas01/RAG)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

Aplicação de **Retrieval-Augmented Generation (RAG)**: faça upload de PDFs e DOCXs, busque por similaridade semântica e obtenha respostas de um LLM com contexto real dos seus documentos.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│               User / Browser (React + Vite)             │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP
                       ▼
              ┌─────────────────┐
              │  FastAPI (API)  │
              │   Port 8000     │
              └────────┬────────┘
                       │
         ┌─────────────┼──────────────┐
         ▼             ▼              ▼
   ┌──────────┐  ┌──────────┐  ┌──────────────┐
   │PostgreSQL│  │  Redis   │  │Celery Worker │
   │+pgvector │  │ (broker) │  │              │
   └──────────┘  └──────────┘  └──────────────┘
```

**Upload flow:** `POST /api/documents/upload` → valida arquivo → salva no Redis → dispara task Celery → worker faz parse + chunking + embedding (sentence-transformers local) + salva no pgvector.

**Search flow:** `POST /api/search` → embeda a query → busca híbrida (semântica pgvector + full-text PostgreSQL) → retorna chunks mais relevantes.

**Chat flow:** `POST /api/chat` → busca chunks relevantes → monta prompt → chama LLM (Groq / Ollama / OpenAI).

---

## Running locally

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Node.js 20+ (para o frontend)

### 1. Clone e configure

```bash
git clone https://github.com/ArthurViegas01/RAG.git
cd RAG
cp .env.example .env       # edite com suas chaves
```

### 2. Suba os serviços (PostgreSQL + Redis)

```bash
docker-compose up -d db redis
```

### 3. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate          # Windows
# source venv/bin/activate       # Linux/macOS
pip install -r requirements.dev.txt

# API
uvicorn app.main:app --reload

# Worker Celery (novo terminal)
celery -A app.celery_app worker --loglevel=info
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Acesse `http://localhost:5173` (UI) ou `http://localhost:8000/docs` (Swagger).

---

## Environment variables

Crie `backend/.env` baseado em `.env.example`:

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://raguser:ragpass123@localhost:5432/ragdb` | PostgreSQL connection string |
| `REDIS_URL` | ✅ | `redis://localhost:6379/0` | Redis URL (Celery broker) |
| `LLM_PROVIDER` | | `ollama` | LLM provider: `ollama`, `groq` ou `openai` |
| `GROQ_API_KEY` | se Groq | — | Chave da API Groq (gratuita em console.groq.com) |
| `GROQ_MODEL` | | `llama-3.1-8b-instant` | Modelo Groq |
| `OPENAI_API_KEY` | se OpenAI | — | Chave da API OpenAI |
| `OLLAMA_BASE_URL` | | `http://localhost:11434` | URL do Ollama local |
| `OLLAMA_MODEL` | | `llama3` | Modelo Ollama |
| `EMBEDDING_MODEL` | | `all-MiniLM-L6-v2` | Modelo sentence-transformers (local) |
| `CHUNK_SIZE` | | `800` | Tamanho máximo de cada chunk (chars) |
| `CHUNK_OVERLAP` | | `150` | Sobreposição entre chunks (chars) |
| `MAX_CHUNKS_PER_DOC` | | `2000` | Limite de chunks por documento |
| `MAX_FILE_SIZE_MB` | | `50` | Limite de tamanho de upload |
| `DEFAULT_TOP_K` | | `8` | Chunks retornados por busca |
| `CORS_ORIGINS` | | `http://localhost:5173` | Origens CORS permitidas |

---

## Running tests

```bash
cd backend

# Apenas testes unitários (sem serviços externos — roda no CI)
pytest tests/test_chunking.py tests/test_upload_endpoint.py \
       tests/test_search_endpoint.py tests/test_upload_validation.py \
       --cov=app --cov-report=term-missing -v

# Todos os testes unitários marcados
pytest -m unit -v

# Testes de integração (requer PostgreSQL, Redis e Ollama rodando)
pytest -m integration -v
```

---

## API reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/documents/upload` | Upload PDF ou DOCX |
| `GET` | `/api/documents` | Listar documentos |
| `GET` | `/api/documents/{id}` | Detalhes + chunks do documento |
| `GET` | `/api/documents/{id}/status` | Status do processamento |
| `POST` | `/api/documents/{id}/reprocess` | Reprocessar documento |
| `DELETE` | `/api/documents/{id}` | Remover documento |
| `POST` | `/api/search` | Busca semântica híbrida |
| `POST` | `/api/chat` | Chat RAG com LLM |
| `GET` | `/health` | Health check (API + Ollama) |

---

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── documents.py      # POST /api/documents/upload + CRUD
│   │   │   ├── search.py         # POST /api/search (busca híbrida)
│   │   │   └── chat.py           # POST /api/chat (RAG + LLM)
│   │   ├── services/
│   │   │   ├── document_processor.py  # Parse PDF/DOCX + chunking
│   │   │   ├── embedding_service.py   # sentence-transformers local
│   │   │   ├── search_service.py      # Busca semântica + keyword + RRF
│   │   │   ├── chat_service.py        # Integração com LLMs
│   │   │   └── document_repository.py # Acesso ao banco de dados
│   │   ├── tasks/
│   │   │   └── process_document.py   # Celery task de ingestão
│   │   ├── models/                   # SQLAlchemy models (Document, Chunk)
│   │   ├── schemas/                  # Pydantic schemas
│   │   ├── config.py                 # pydantic-settings
│   │   ├── database.py               # Engine async + get_db
│   │   └── main.py                   # FastAPI app factory
│   ├── tests/
│   │   ├── test_chunking.py          # DocumentParser + DocumentChunker
│   │   ├── test_upload_endpoint.py   # Upload API (Celery mockado)
│   │   ├── test_search_endpoint.py   # Search API (DB mockado)
│   │   ├── test_upload_validation.py # Tipos inválidos + tamanho
│   │   └── test_health.py            # Testes de integração e embedding
│   ├── requirements.txt
│   └── requirements.dev.txt          # + pytest-cov + httpx
├── frontend/                         # React + Vite
├── .github/
│   └── workflows/
│       └── ci.yml                    # pytest --cov em todo push/PR
├── docker-compose.yml
├── docker-compose.prod.yml
└── .env.example
```

---

## License

MIT
