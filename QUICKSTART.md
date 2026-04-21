# Quick Start - Desenvolvimento Local

Comece a desenvolver a aplicação RAG em poucos minutos.

## Pré-requisitos

- Docker & Docker Compose instalados
- Git
- Opcional: VS Code, Python IDE para desenvolvimento backend

## Opção 1: Docker Compose (Recomendado)

### 1. Clonar repositório

```bash
git clone <seu-repo>
cd rag-app
```

### 2. Criar arquivo .env com padrões de dev

```bash
cp .env.example .env
```

Conteúdo padrão já está configurado para dev local.

### 3. Iniciar todos os containers

```bash
docker-compose up
```

Aguarde até ver:
```
rag-api | INFO:     Uvicorn running on http://0.0.0.0:8000
rag-frontend | Local:   http://localhost:5173
```

### 4. Acessar a aplicação

- **Frontend**: http://localhost:5173
- **API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Opção 2: Desenvolvimento Manual (Windows/Mac/Linux)

Se preferir rodar fora do Docker:

### Backend

#### 1. Python virtual environment

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

#### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

#### 3. PostgreSQL

Você precisa de PostgreSQL 16 rodando localmente:

```bash
# Windows: Download de https://www.postgresql.org/download/windows/
# Mac: brew install postgresql@16
# Linux: sudo apt install postgresql-16

# Criar banco
psql -U postgres -c "CREATE USER raguser WITH PASSWORD 'ragpass123';"
psql -U postgres -c "CREATE DATABASE ragdb OWNER raguser;"
psql -U postgres -d ragdb -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### 4. Redis

```bash
# Windows: Download de https://github.com/microsoftarchive/redis/releases
# Mac: brew install redis
# Linux: sudo apt install redis-server

# Iniciar Redis
redis-server
```

#### 5. Variáveis de ambiente

Criar `.env` na raiz de `backend/`:

```bash
DATABASE_URL=postgresql+asyncpg://raguser:ragpass123@localhost:5432/ragdb
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
CORS_ORIGINS=http://localhost:5173
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHUNK_SIZE=800
CHUNK_OVERLAP=150
```

#### 6. Iniciar FastAPI

```bash
uvicorn app.main:app --reload
```

API rodando em http://localhost:8000

#### 7. Iniciar Celery Worker (em outro terminal)

```bash
celery -A app.celery_app worker --loglevel=info
```

### Frontend

#### 1. Instalar Node.js

```bash
# Download de https://nodejs.org/
# Ou use nvm: https://github.com/nvm-sh/nvm
```

#### 2. Instalar dependências

```bash
cd frontend
npm install
```

#### 3. Iniciar dev server

```bash
npm run dev
```

Frontend rodando em http://localhost:5173

### Ollama (Optional - para LLM local)

Se quer usar Ollama em vez de Groq:

```bash
# Download de https://ollama.ai/
ollama run llama3
```

## Primeiro Uso

### 1. Upload um documento

1. Acesse http://localhost:5173
2. Clique em "Upload Document"
3. Selecione um PDF ou DOCX

**O documento será:**
- Armazenado em `backend/uploads/`
- Processado pelo Celery worker
- Convertido em chunks
- Embeddings gerados
- Indexado em PostgreSQL

Status muda:
- PENDING → PROCESSING → COMPLETED

### 2. Buscar documento

1. Na página principal, use a barra de busca
2. Digite uma query relacionada ao documento

**O que acontece:**
- Query é convertida em embedding
- Busca vetorial em pgvector
- Retorna chunks mais relevantes

### 3. Chat com RAG

1. Veja os chunks retornados
2. Clique em "Chat with RAG"
3. Faça perguntas sobre o documento

**O que acontece:**
- Query + chunks mais relevantes são enviados ao LLM
- LLM gera resposta contextualizada
- Resposta é mostrada ao usuário

## Estrutura do Projeto

```
rag-app/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── database.py          # SQLAlchemy config
│   │   ├── models.py            # Database models
│   │   ├── config.py            # Settings
│   │   ├── celery_app.py        # Celery config
│   │   ├── api/
│   │   │   ├── documents.py     # Upload endpoints
│   │   │   ├── search.py        # Search endpoints
│   │   │   └── chat.py          # Chat endpoints
│   │   └── services/
│   │       ├── embedding.py     # Embedding service
│   │       ├── chunking.py      # Document chunking
│   │       └── llm.py           # LLM integration
│   ├── Dockerfile               # Dev image
│   ├── Dockerfile.prod          # Prod image
│   ├── requirements.txt
│   └── uploads/                 # Uploaded files
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── DocumentUpload.jsx
│   │   │   ├── DocumentList.jsx
│   │   │   ├── SearchBar.jsx
│   │   │   └── ChatInterface.jsx
│   │   └── services/
│   │       └── api.js           # API calls
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml           # Dev compose
├── docker-compose.prod.yml      # Prod compose
├── .env.example                 # Env template
├── ARCHITECTURE.md              # Architecture docs
├── README.DEPLOY.md             # Deployment guide
└── QUICKSTART.md                # Este arquivo
```

## Comandos Úteis

### Docker Compose

```bash
# Iniciar todos os containers
docker-compose up

# Em background
docker-compose up -d

# Parar containers
docker-compose down

# Ver logs
docker-compose logs -f api
docker-compose logs -f worker
docker-compose logs -f db

# Executar comando em container
docker-compose exec api python -m pytest

# Rebuild images
docker-compose build
```

### FastAPI/Python

```bash
# Rodar testes
pytest backend/tests/

# Criar migration (se usar Alembic)
alembic revision --autogenerate -m "Add new column"

# Apply migrations
alembic upgrade head

# Reset database (CUIDADO!)
python -m backend.app.database drop_db
```

### Frontend/Node

```bash
# Build para produção
npm run build

# Lint/format code
npm run lint
npm run format

# Testes (se houver)
npm test
```

## Debugging

### Ver logs da API

```bash
docker-compose logs -f api
```

Ou se rodar manualmente:
```bash
uvicorn app.main:app --reload --log-level debug
```

### Ver logs do Celery

```bash
docker-compose logs -f worker
```

Ou:
```bash
celery -A app.celery_app worker --loglevel=debug
```

### Acessar database

```bash
# Via Docker
docker-compose exec db psql -U raguser -d ragdb

# Manualmente
psql -U raguser -d ragdb -h localhost

# Dentro do psql:
\dt                    # Ver tabelas
SELECT * FROM documents;  # Ver documentos
\q                     # Sair
```

### Acessar Redis

```bash
# Via Docker
docker-compose exec redis redis-cli

# Manualmente
redis-cli

# Dentro do redis-cli:
KEYS *                 # Ver todas as chaves
GET chave              # Ver valor
DEL chave              # Deletar chave
FLUSHALL               # Limpar tudo (CUIDADO!)
```

## Troubleshooting

### Erro: "Cannot connect to Docker daemon"

```bash
# Reiniciar Docker
docker daemon restart
# ou Windows: Docker Desktop menu → Restart
```

### Erro: "Port already in use"

```bash
# Mudar porta em docker-compose.yml
# Ou parar container que usa a porta
docker ps
docker stop <container_id>
```

### Erro: "Database connection refused"

```bash
# Aguardar container PostgreSQL iniciar
docker-compose logs db

# Ou restart
docker-compose restart db
```

### Documento não processa

```bash
# Ver logs do worker
docker-compose logs -f worker

# Verificar se Redis está rodando
docker-compose exec redis redis-cli ping
# Deve retornar: PONG
```

### Embedding dimensão não bate

```bash
# Se mudar EMBEDDING_MODEL em config.py:
# 1. Deletar chunks antigos
docker-compose exec db psql -U raguser -d ragdb -c "DELETE FROM chunks;"

# 2. Reprocessar documentos (fazer upload novamente)
```

## Próximos Passos

1. **Explorar API**: http://localhost:8000/docs
2. **Ler** `ARCHITECTURE.md` para entender fluxo
3. **Modificar código** e ver hot reload
4. **Escrever testes** para novas features
5. **Deploy em produção**: Ver `README.DEPLOY.md`

## Recursos

- FastAPI docs: https://fastapi.tiangolo.com/
- SQLAlchemy docs: https://docs.sqlalchemy.org/
- Celery docs: https://docs.celeryproject.org/
- pgvector docs: https://github.com/pgvector/pgvector
- React docs: https://react.dev/
- Docker docs: https://docs.docker.com/

## Suporte

Se tiver dúvidas:

1. Verificar logs: `docker-compose logs -f [service]`
2. Ler `ARCHITECTURE.md` e `README.DEPLOY.md`
3. Checar se .env está correto
4. Fazer rebuild: `docker-compose build && docker-compose up`

Happy coding! 🚀
