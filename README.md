# Context RAG

[![CI](https://github.com/ArthurViegas01/RAG/actions/workflows/ci.yml/badge.svg)](https://github.com/ArthurViegas01/RAG/actions/workflows/ci.yml)

RAG pipeline for querying private documents: upload PDFs and DOCXs, ask questions in plain language, get answers grounded in the actual content.

## What it does

Accepts PDF and DOCX uploads, splits them into overlapping chunks, generates embeddings locally using Sentence Transformers, and stores them in PostgreSQL with pgvector. At query time it performs hybrid retrieval — semantic similarity via pgvector plus PostgreSQL full-text search — ranks the results with Reciprocal Rank Fusion, then passes the top chunks as context to an LLM to generate a grounded response with source attribution.

## Architecture

The upload endpoint returns immediately; parsing and embedding happen in a Celery worker so large files don't block the API.

```
Upload  →  Parse (PyMuPDF / python-docx)
        →  Chunk (LangChain, 800 chars, 150 overlap)
        →  Embed (all-MiniLM-L6-v2, 384d)
        →  Store (PostgreSQL + pgvector, HNSW index)

Query   →  Embed query
        →  Hybrid search (pgvector cosine + PostgreSQL FTS, RRF rerank)
        →  Top-k chunks as LLM context
        →  Response
```

```
Browser (React + Vite)
       │ HTTP
       ▼
  FastAPI :8000
  ├── PostgreSQL + pgvector   (documents, chunks, embeddings)
  ├── Redis :6379              (Celery broker)
  └── Celery Worker           (parse → chunk → embed → store)
```


## Estrutura de Pastas

```
RAG/
├── docker-compose.yml          # PostgreSQL + Redis
├── .env.example                # Variáveis de ambiente (copie para .env)
├── .gitignore
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

## Stack

- FastAPI
- Celery + Redis
- PostgreSQL + pgvector
- LangChain text splitters
- fastembed / ONNX Runtime (all-MiniLM-L6-v2, 384d, local)
- Groq / Llama 3 (default), Ollama, OpenAI (configurable via env)
- React + Vite
- Docker + Docker Compose
- Netlify (frontend)

## Running locally

The full stack — API, worker, database, frontend — starts with a single command.

```bash
git clone https://github.com/ArthurViegas01/RAG.git
cd RAG
cp .env.example .env        # set GROQ_API_KEY (free at console.groq.com)
docker-compose up
```

- UI: http://localhost:5173
- API / Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health

### Without Docker

Spin up the infrastructure first, then run the backend and frontend processes manually.

```bash
# Infrastructure
docker-compose up -d db redis

# Terminal 1 — API
cd backend
python -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\activate
pip install -r requirements.dev.txt
uvicorn app.main:app --reload

# Terminal 2 — Worker
cd backend && source venv/bin/activate
celery -A app.celery_app worker --loglevel=info

# Terminal 3 — Frontend
cd frontend && npm install && npm run dev
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:password@localhost:5432/ragdb` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker |
| `JWT_SECRET` | *(insecure default)* | HS256 signing key — set a random value in production (`openssl rand -hex 32`) |
| `LLM_PROVIDER` | `groq` | `groq`, `ollama`, or `openai` |
| `GROQ_API_KEY` | — | Free key at console.groq.com |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Groq model |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Local embedding model |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed origins (no wildcards) |
| `CHUNK_SIZE` | `800` | Max characters per chunk |
| `CHUNK_OVERLAP` | `150` | Overlap between adjacent chunks |
| `DEFAULT_TOP_K` | `8` | Chunks returned per query |
| `MAX_USER_UPLOADS_PER_DAY` | `20` | Per-tenant upload count quota (24 h rolling window) |
| `MAX_USER_UPLOAD_BYTES_PER_DAY` | `524288000` | Per-tenant upload size quota in bytes (500 MB) |
| `DB_CA_CERT_PATH` | — | Path to the PostgreSQL CA certificate for TLS verification (Railway: save the cert as a secret file) |

### Tests

```bash
cd backend
pytest tests/test_chunking.py tests/test_upload_endpoint.py tests/test_document_endpoints.py \
       tests/test_search_endpoint.py tests/test_search_utils.py tests/test_upload_validation.py \
       --cov=app --cov-report=term-missing -v

# Integration tests (requires PostgreSQL, Redis, and an LLM provider running)
pytest -m integration -v
```

## Security

### Authentication and multi-tenant isolation

All API endpoints require a bearer token:

```bash
curl -X POST https://<your-api>/api/auth/token
# {"access_token": "eyJ...", "token_type": "bearer"}
```

Pass it as `Authorization: Bearer <token>` on every subsequent request. The frontend handles this automatically.

Tokens are self-contained JWTs signed with `JWT_SECRET` (HS256, 1-year TTL). There are no user accounts or passwords: each browser session gets its own identity. Every query — semantic search, keyword search, document listing, and ownership checks — is scoped to the authenticated `user_id`. Documents belonging to another user return 404, not 403, to avoid confirming existence.

Legacy `localStorage` UUIDs can be migrated by passing `user_id` in the token request body.

### Rate limiting and upload quotas

- Upload: 10 requests/hour per IP; per-tenant daily quota of 20 files or 500 MB (24-hour rolling window, stored in Redis).
- Search: 30 requests/minute per IP.
- Chat: 10 requests/minute per IP.

Requests that exceed the rate limit return 429. Requests that exceed the upload quota also return 429.

The `Content-Length` header is checked before reading the request body, so oversized uploads are rejected without materialising in memory.

### Document parsing protections

- PDF: capped at 2 000 pages and 200 MB of extracted text per file.
- DOCX: the zip is inspected before decompression; total uncompressed size must be under 200 MB. Both limits protect the worker against decompression bombs.

### Prompt injection mitigations

Document content is wrapped in `<<<DOCUMENTO_INICIO>>>` / `<<<DOCUMENTO_FIM>>>` delimiters in every prompt, and the system prompt instructs the model to treat content between those markers as data, not instructions. Filenames are sanitised (newlines stripped, truncated to 255 chars) before being stored or included in prompts.

### Transport and headers

- PostgreSQL connection uses `ssl.create_default_context()` (`CERT_REQUIRED` + `check_hostname=True`). Supply `DB_CA_CERT_PATH` to pin the provider's CA certificate.
- Netlify serves the frontend with `Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and `Referrer-Policy`.
- CORS is restricted to the explicit origin list in `CORS_ORIGINS`. The app refuses to start if that list contains `*`.

### Production checklist

- Set `JWT_SECRET` to a random value: `openssl rand -hex 32`.
- Set `CORS_ORIGINS` to the exact frontend URL (e.g. `https://yourapp.netlify.app`).
- Provide `DB_CA_CERT_PATH` if your PostgreSQL provider supplies a CA certificate.
- Never commit `.env` to version control.

## Key decisions

- **pgvector over a dedicated vector database.** The project already uses PostgreSQL for document metadata and chunk storage. pgvector keeps everything in a single service — no Pinecone or Weaviate to manage — and similarity queries stay in SQL alongside joins on document metadata. For this scale it avoids the operational overhead of a separate vector store without meaningful quality loss.

- **Celery for async ingestion.** Parsing and embedding a large PDF can take 10–30 seconds. Doing it synchronously would mean the upload request blocks until completion, which hits HTTP timeouts and prevents concurrent uploads. Celery enqueues the work and the endpoint returns immediately with a document ID the client can poll.

- **all-MiniLM-L6-v2 for embeddings.** Runs entirely locally with no API dependency or per-token cost. At 384 dimensions the vectors are compact enough that HNSW indexing stays fast even as the document count grows. The model's retrieval quality is sufficient — the LLM handles nuance at generation time, so embeddings only need to get the right chunks into the context window.

- **Groq as the default LLM provider.** The free tier gives fast Llama 3 inference without a local GPU. The provider is a single env var (`LLM_PROVIDER`), so switching to Ollama for fully local operation or OpenAI for higher quality requires no code changes.

## License

MIT
