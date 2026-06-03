# CLAUDE.md

## Project
RAG pipeline for uploading and querying private documents (PDF/DOCX). Files are parsed, chunked, embedded locally (fastembed/ONNX), and stored in PostgreSQL + pgvector. Queries use hybrid retrieval (semantic cosine + PostgreSQL FTS) with RRF reranking, then pass top-k chunks to a configured LLM.

## Stack
- **Backend**: FastAPI + Celery + SQLAlchemy 2.0 (async) + PostgreSQL + pgvector + Redis
- **Embeddings**: fastembed (ONNX, all-MiniLM-L6-v2, 384d, runs locally, ~80-120 MB RAM)
- **LLM**: Groq (default prod), Ollama (local dev), OpenAI — switched via `LLM_PROVIDER` env var
- **Frontend**: React 18 + Vite 5 (deployed on Netlify)
- **Infra**: Railway (API + Worker microservices), docker-compose for local dev

## Running locally

```bash
cp .env.example .env   # set GROQ_API_KEY (free at console.groq.com)
docker-compose up
```

- UI: http://localhost:5173
- API / Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Running tests

Tests mock the database and embedding service — no live infrastructure needed.

```bash
cd backend
pytest tests/test_chunking.py tests/test_upload_endpoint.py tests/test_document_endpoints.py \
       tests/test_search_endpoint.py tests/test_search_utils.py tests/test_upload_validation.py \
       --cov=app --cov-report=term-missing -v
```

CI runs the same set via `.github/workflows/ci.yml` on every push.

## Backend structure

```
backend/app/
├── api/           # FastAPI routers: documents, search, chat
├── models/        # SQLAlchemy ORM: Document, Chunk, DocumentStatus
├── schemas/       # Pydantic DTOs (request/response)
├── services/      # Business logic: processor, embedding, search, chat
└── tasks/         # Celery task: process_document (parse → chunk → embed → store)
```

Key files:
- `config.py` — all settings via pydantic-settings, loaded from `.env`
- `services/search_service.py` — hybrid search (pgvector + ILIKE + FTS) with RRF fusion
- `services/chat_service.py` — LLM dispatch (Groq / Ollama / OpenAI)
- `tasks/process_document.py` — async ingestion pipeline (runs in Celery worker)

## Deployment

| Target | Command | Dockerfiles used |
|--------|---------|-----------------|
| Local dev | `docker-compose up` | `backend/Dockerfile`, `backend/Dockerfile.worker`, `frontend/Dockerfile` |
| Railway | Auto-deploy from `main` via `railway.toml` | `Dockerfile.api`, `Dockerfile.worker` (root) |
| Netlify | Auto-deploy frontend via `netlify.toml` | — (builds from source) |
| Self-hosted VPS | `./deploy.sh deploy` | `backend/Dockerfile.prod`, `backend/Dockerfile.worker.prod` |

## Key design decisions

- **File storage in Redis** (not filesystem): uploaded bytes are stored via `setex` with 7-day TTL so the API and Celery worker share them without a shared volume. This is what makes Railway's isolated-container model work.
- **`create_all` instead of Alembic**: schema is managed by SQLAlchemy at startup. Alembic is initialized but unused — migrate to it if the schema needs versioned migrations.
- **fastembed over sentence-transformers**: ONNX runtime, no PyTorch dependency, faster cold start.
