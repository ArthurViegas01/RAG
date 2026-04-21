# Arquitetura do Projeto RAG

Este documento descreve a arquitetura técnica, stack de tecnologias e fluxo de dados da aplicação.

## Stack de Tecnologias

### Backend

| Componente | Tecnologia | Versão | Propósito |
|-----------|-----------|--------|----------|
| **Framework** | FastAPI | 0.115.6 | API REST async de alta performance |
| **Servidor Web** | Uvicorn | 0.34.0 | ASGI server (dev) |
| **Produção** | Gunicorn + Uvicorn | 23.0.0 | Production-grade ASGI server |
| **Database** | PostgreSQL | 16 | RDBMS para metadados e documentos |
| **Vector DB** | pgvector | 0.3.6 | Extensão PostgreSQL para vetores |
| **ORM** | SQLAlchemy | 2.0.36 | Async ORM com suporte a PostgreSQL |
| **Driver DB** | asyncpg | 0.30.0 | Driver async para FastAPI |
| **Queue** | Redis | 7-alpine | Message broker para Celery |
| **Task Queue** | Celery | 5.4.0 | Processamento async de documentos |
| **Embeddings** | sentence-transformers | 3.3.1 | Modelos de embedding locais |
| **Chunking** | langchain-text-splitters | 0.3.4 | Processamento e divisão de documentos |
| **PDF Parser** | PyMuPDF (fitz) | 1.25.3 | Extração de texto de PDFs |
| **Docx Parser** | python-docx | 1.1.2 | Extração de texto de DOCX |
| **HTTP Client** | httpx | 0.28.1 | Client async para APIs externas |

### Frontend

| Componente | Tecnologia | Versão | Propósito |
|-----------|-----------|--------|----------|
| **Framework** | React | 18+ | UI framework |
| **Build Tool** | Vite | 5+ | Fast build tool e dev server |
| **Styling** | Tailwind CSS | 3+ | Utility-first CSS framework |
| **HTTP Client** | axios ou fetch | - | Requisições para API |
| **Runtime** | Node.js | 20-alpine | Runtime para frontend |
| **Produção** | serve | - | Static file server |

### DevOps / Infraestrutura

| Componente | Tecnologia | Versão | Propósito |
|-----------|-----------|--------|----------|
| **Containerização** | Docker | latest | Container runtime |
| **Orquestração** | Docker Compose | 1.29+ | Orquestração de containers |
| **Reverse Proxy** | Nginx | alpine | Load balancing e SSL termination |
| **Control Version** | Git | - | Version control |

## Arquitetura de Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                        USUÁRIO / FRONTEND                       │
│                    (React + Vite + Tailwind)                    │
└────────────────────┬────────────────────────────────────────────┘
                     │ HTTP REST
                     ▼
┌──────────────────────────────────────────────────────────────────┐
│                   NGINX (Reverse Proxy)                          │
│              - Load Balancing                                    │
│              - SSL Termination                                   │
│              - Static File Serving                               │
└──────────────┬─────────────────────┬──────────────────────────────┘
               │                     │
               ▼ /api               ▼ /
        ┌─────────────────┐   ┌──────────────────┐
        │   FastAPI API   │   │  Frontend Static │
        │  (Gunicorn)     │   │    Files (dist)  │
        │  Port 8000      │   │    Port 5173     │
        └────────┬────────┘   └──────────────────┘
                 │
    ┌────────────┼────────────────┐
    ▼            ▼                 ▼
┌─────────┐  ┌────────┐      ┌──────────┐
│PostgreSQL│ │ Redis  │      │ Celery   │
│  (DB)   │  │(Broker)│      │ Worker   │
│pgvector │  │        │      │          │
│         │  │        │      │ Task:    │
│ - Meta  │  │ Queue: │      │ - Upload │
│ - Docs  │  │ - Task │      │ - Process│
│ - Chunks│  │ - State│      │ - Index  │
└─────────┘  └────────┘      └──────────┘
    ▲                              │
    │                              │
    └──────────────────────────────┘
          (SQL + Results)
```

## Fluxo de Dados: Upload e Processamento

```
1. UPLOAD
   User → Frontend → FastAPI /api/documents/upload
   └─→ Arquivo salvo em ./backend/uploads/
       └─→ Metadados salvos em PostgreSQL (status: PENDING)

2. ENFILEIRAMENTO (Celery Task)
   FastAPI → Redis Broker
   └─→ Task: process_document(doc_id)

3. PROCESSAMENTO (Celery Worker)
   Worker ← Redis
   └─→ 1. Ler arquivo de ./uploads/
       2. Parse PDF/DOCX com PyMuPDF ou python-docx
       3. Chunk com LangChain text splitters
       4. Gerar embeddings com sentence-transformers
       5. Salvar chunks + embeddings em PostgreSQL

4. INDEXAÇÃO (pgvector)
   PostgreSQL
   └─→ CREATE INDEX idx_chunks_embedding_hnsw (HNSW)
       └─→ Permite buscas vetoriais rápidas

5. BUSCA (Retrieval Augmented Generation)
   User → Frontend → FastAPI /api/search
   └─→ 1. Embed query com sentence-transformers
       2. Busca vetorial em pgvector (HNSW) + filtro
       3. Retorna chunks mais relevantes

6. RESPOSTA (LLM Integration)
   FastAPI → Groq API (ou Ollama, OpenAI)
   └─→ Enviar: <contexto_chunks> + <query>
       └─→ Receber: resposta do modelo
           └─→ Retornar ao usuário
```

## Componentes Principais

### 1. FastAPI Application (`backend/app/main.py`)

Endpoint principais:

- `POST /api/documents/upload` - Upload de arquivo
- `GET /api/documents` - Listar documentos
- `DELETE /api/documents/{id}` - Deletar documento
- `POST /api/search` - Buscar documentos
- `POST /api/chat` - Chat com RAG
- `GET /health` - Health check

### 2. Database Model (`backend/app/models.py`)

Entidades:

```
Document
├── id: UUID
├── filename: str
├── content: text
├── status: enum (PENDING, PROCESSING, COMPLETED, ERROR)
├── created_at: datetime
└── error_message: str

Chunk
├── id: UUID
├── document_id: FK(Document)
├── content: text
├── embedding: vector(384)  # pgvector
├── page_num: int
├── position: int
├── metadata: json
└── similarity_score: float (calculado em query)
```

### 3. Celery Worker (`backend/app/celery_app.py`)

Tasks:

- `process_document()` - Processa arquivo enviado
  1. Parse arquivo
  2. Chunking
  3. Embedding
  4. Save to DB

### 4. Embedding & Retrieval

**Modelo:** `all-MiniLM-L6-v2` (384 dimensões)

- Embeddings locais (não depende de APIs externas)
- Fast (~5-10ms per chunk)
- Bom tradeoff entre speed e qualidade
- Alternativas: `all-mpnet-base-v2` (768d, mais lento mas melhor)

**Search Strategy:**

1. **Semantic Search** (pgvector HNSW)
   ```sql
   SELECT * FROM chunks
   WHERE 1 - (embedding <=> query_embedding) > min_similarity
   ORDER BY embedding <=> query_embedding
   LIMIT top_k
   ```

2. **Filtering**
   - Por document_id
   - Por date range
   - Por metadata

### 5. LLM Integration

Suportado 3 providers:

#### a) **Groq (Recomendado para Produção)**
- Gratuito (até limite)
- Ultra-rápido
- Modelos: llama3-8b-8192, mixtral-8x7b, etc.

#### b) **Ollama (Dev Local)**
- Totalmente local
- Requer `ollama run llama2` antes
- Lento (CPU-only)
- Bom para desenvolvimento

#### c) **OpenAI (Premium)**
- Pago
- Melhor qualidade
- Modelos: GPT-4o, GPT-4o-mini

### 6. Frontend (React + Vite)

Componentes principais:

```
App
├── DocumentUpload
│   └── File input → POST /api/documents/upload
├── DocumentList
│   ├── GET /api/documents
│   ├── DELETE /api/documents/{id}
│   └── Show status (PENDING, PROCESSING, COMPLETED, ERROR)
├── SearchBar
│   └── POST /api/search
└── ChatInterface
    ├── Display search results
    └── POST /api/chat (com history)
```

## Configuração (Settings)

Arquivo: `backend/app/config.py`

Usa `pydantic-settings` para carregar variáveis de `.env`:

```python
class Settings:
    database_url: str         # PostgreSQL
    redis_url: str           # Redis
    llm_provider: str        # ollama, groq, openai
    groq_api_key: str        # para Groq
    chunk_size: int          # 800 chars
    chunk_overlap: int       # 150 chars
    default_top_k: int       # 8 chunks
    min_similarity: float    # 0.15
    max_file_size_mb: int    # 50
    cors_origins: str        # CORS whitelist
```

## Performance Considerations

### Database

- **pgvector HNSW index** em embeddings para busca rápida
- **B-tree index** em document_id para filtros
- **Connection pooling** com SQLAlchemy (`pool_size=20`)

### Embeddings

- **Model**: all-MiniLM-L6-v2 é otimizado para speed
- **Batch processing**: chunks processados em batch
- **Caching**: embeddings já calculados reutilizados

### API

- **Async/await** throughout (FastAPI)
- **Gunicorn with multiple workers** em produção
- **Nginx compression** (gzip)
- **Browser caching** para assets estáticos

### Celery

- **Redis broker** (mais rápido que RabbitMQ para uso leve)
- **Prefork pool** com 4 workers
- **Task timeouts** para evitar tasks travadas

## Deployment

### Desenvolvimento

```bash
docker-compose up
# Frontend: http://localhost:5173
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Produção

```bash
docker-compose -f docker-compose.prod.yml up -d
# Frontend: https://seu-dominio.com
# API: https://seu-dominio.com/api
# Nginx em port 80/443
```

## Escalabilidade

Para escalar em produção:

### Horizontal Scaling

1. **API**: Aumentar `--workers` em Gunicorn
2. **Worker**: Rodar múltiplos containers de worker
3. **Database**: Usar managed PostgreSQL (AWS RDS, etc.)
4. **Redis**: Usar managed Redis (AWS ElastiCache, etc.)

### Vertical Scaling

1. Aumentar CPU/RAM da VPS
2. Aumentar `pool_size` de PostgreSQL
3. Aumentar `--workers` de Gunicorn

### Caching

1. Implementar Redis cache para queries frequentes
2. Browser caching para assets estáticos
3. Cache de embeddings já calculados

## Segurança

- ✅ HTTPS/SSL via Nginx
- ✅ CORS configurável
- ✅ SQL injection prevention (SQLAlchemy ORM)
- ✅ File upload validation
- ✅ Rate limiting (via Nginx)
- ✅ Sensitive data in .env (não commitado)
- ✅ Docker security best practices

## Monitoramento

### Health Checks

- API: `/health` (retorna status do Ollama/LLM)
- Database: `pg_isready`
- Redis: `PING`

### Logging

- **Uvicorn logs**: requests/responses
- **Celery logs**: task execution
- **Database logs**: queries (se `echo=True`)

### Métricas (Optional)

Pode adicionar:
- Prometheus para métricas
- Grafana para dashboards
- Sentry para error tracking

## Troubleshooting

### Problema: "Embedding dimension mismatch"

**Causa**: Mudou `EMBEDDING_MODEL` sem regenerar embeddings

**Solução**: Fazer backup + delete chunks antigos + reprocessar documentos

### Problema: "Task timeout"

**Causa**: Documentos muito grandes

**Solução**: Aumentar `--time-limit` em Celery

### Problema: "Connection refused to database"

**Causa**: PostgreSQL container não iniciou

**Solução**: `docker-compose up db` e aguarde health check passar

## Próximos Melhoramentos

- [ ] Autenticação (OAuth, JWT)
- [ ] Rate limiting
- [ ] Batch processing optimization
- [ ] Cache distribuído
- [ ] Monitoring (Prometheus + Grafana)
- [ ] CI/CD pipeline
- [ ] Unit tests coverage > 80%
- [ ] Load testing
- [ ] Documentation API (OpenAPI/Swagger)
