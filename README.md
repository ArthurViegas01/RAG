# Context

A RAG application for chatting with your documents. Upload a PDF or DOCX, wait for indexing, and ask questions in natural language — the answer comes with citations pointing back to the exact source passages.

![Context app screenshot](docs/screenshot.png)

## How it works

When you upload a document, a Celery worker picks it up asynchronously, extracts the text, splits it into overlapping chunks, and generates vector embeddings using a local sentence-transformers model. Those embeddings live in PostgreSQL via the pgvector extension alongside the regular document metadata.

When you ask a question, the backend embeds the query with the same model, does a cosine-similarity search against the stored chunks, and sends the top results as context to the LLM. The response comes back with references to each source passage so you can verify what the model pulled from.

```
upload → parse → chunk → embed → store in pgvector
query  → embed → vector search → context → LLM → answer + citations
```

## Stack

| Layer | Tech | Notes |
|---|---|---|
| Frontend | React + Vite | No UI framework, just CSS variables |
| Backend | FastAPI | Async throughout |
| Task queue | Celery + Redis | Document processing runs in the background |
| Database | PostgreSQL + pgvector | One less service to run vs a dedicated vector DB |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` | Runs locally, no API key needed |
| LLM | Groq (prod) / Ollama (local) | Groq's free tier is fast enough for this use case |
| Infra | Docker Compose | One command to start everything |

**Why pgvector instead of Pinecone/Weaviate?** Most projects already run Postgres. Adding `pgvector` keeps the stack simpler — one database handles both relational data and vector search, and the similarity query is just SQL.

**Why local embeddings?** Zero latency, no API costs, works offline. `all-MiniLM-L6-v2` is 80MB and gives good retrieval quality at 384 dimensions.

## Getting started

```bash
git clone https://github.com/your-username/context-rag.git
cd context-rag

cp .env.example .env
# Add your GROQ_API_KEY to .env (free at console.groq.com)
# Or set LLM_PROVIDER=ollama and run: ollama pull llama3

docker compose up
```

Frontend at `http://localhost:5173`, API docs at `http://localhost:8000/docs`.

For local LLM with Ollama, install it from [ollama.com](https://ollama.com), pull a model, and set `LLM_PROVIDER=ollama` in your `.env`.

## Project structure

```
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers (documents, search, chat)
│   │   ├── models/         # SQLAlchemy models (Document, Chunk)
│   │   ├── schemas/        # Pydantic DTOs
│   │   └── services/
│   │       ├── document_processor.py   # Parse + chunking
│   │       ├── embedding_service.py    # sentence-transformers
│   │       ├── search_service.py       # pgvector similarity search
│   │       └── chat_service.py         # Prompt assembly + LLM call
│   ├── Dockerfile
│   └── Dockerfile.worker
└── frontend/
    └── src/
        ├── components/
        │   ├── ChatInterface.jsx
        │   ├── DocumentList.jsx
        │   ├── DocumentUpload.jsx
        │   └── SplashScreen.jsx
        ├── api/client.js
        └── styles.css
```

## Configuration

Copy `.env.example` to `.env` and fill in the required values:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `LLM_PROVIDER` | `groq`, `ollama`, or `openai` |
| `GROQ_API_KEY` | Free key from console.groq.com |
| `OLLAMA_BASE_URL` | Ollama URL (default: `http://localhost:11434`) |
| `CHUNK_SIZE` | Characters per chunk (default: 800) |
| `CHUNK_OVERLAP` | Overlap between chunks (default: 150) |
| `MAX_FILE_SIZE_MB` | Upload limit (default: 50) |

## Deploying

See [DEPLOY.md](DEPLOY.md) for production setup with Docker Compose + Nginx on a VPS, or one-click deploy on Railway.

## License

MIT
