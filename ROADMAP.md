# RAG Pipeline — AI Document Processor

## Visão Geral

Uma aplicação que permite upload de documentos (PDF, DOCX), faz chunking inteligente, gera embeddings, armazena em PostgreSQL com pgvector, e usa retrieval + LLM para responder perguntas com citações das fontes originais.

## Stack Técnica

| Camada | Tecnologia | Por quê |
|--------|-----------|---------|
| Backend API | FastAPI (Python) | Async nativo, documentação automática, padrão de mercado |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Gratuito, roda local, 384 dimensões, boa qualidade |
| LLM | Ollama (llama3 / mistral) | Gratuito, roda local, fácil de trocar modelos |
| Vector DB | PostgreSQL + pgvector | Pragmático — empresas já usam Postgres, pgvector é extensão |
| Fila assíncrona | Celery + Redis | Processamento de docs em background, padrão da indústria |
| Frontend | React + Vite | Chat interface simples, rápido de montar |
| Orquestração | Docker Compose | Tudo sobe com um comando |
| Chunking | LangChain TextSplitters | Chunking inteligente com overlap configurável |

## Arquitetura

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  React UI   │────▶│  FastAPI      │────▶│  PostgreSQL     │
│  (Chat +    │     │  (REST API)   │     │  + pgvector     │
│   Upload)   │◀────│               │◀────│  (docs + vecs)  │
└─────────────┘     └──────┬───────┘     └─────────────────┘
                           │
                    ┌──────▼───────┐     ┌─────────────────┐
                    │  Celery      │────▶│  Redis           │
                    │  (Workers)   │     │  (Message Broker) │
                    └──────┬───────┘     └─────────────────┘
                           │
                    ┌──────▼───────┐     ┌─────────────────┐
                    │  Sentence    │     │  Ollama          │
                    │  Transformers│     │  (LLM local)     │
                    │  (Embeddings)│     │                   │
                    └──────────────┘     └─────────────────┘
```

## Fases do Projeto

### Fase 1 — Infraestrutura (Dia 1-2)
- [x] Inicializar repositório Git
- [ ] Estrutura de pastas do projeto
- [ ] Docker Compose: PostgreSQL + pgvector + Redis
- [ ] Setup do backend FastAPI (hello world + health check)
- [ ] Configuração do Ollama local
- [ ] `.env.example` com todas as variáveis

**Entregável:** `docker-compose up` sobe toda a infra, API responde em `/health`

### Fase 2 — Upload e Processamento de Documentos (Dia 3-5)
- [ ] Modelo de dados: `documents` e `chunks` no PostgreSQL
- [ ] Endpoint de upload (`POST /api/documents`)
- [ ] Parser de PDF (PyMuPDF) e DOCX (python-docx)
- [ ] Chunking inteligente com LangChain (RecursiveCharacterTextSplitter)
- [ ] Task Celery para processar documento em background
- [ ] Endpoint de status do processamento (`GET /api/documents/{id}`)

**Entregável:** Upload de PDF/DOCX → documento aparece como "processado" com chunks no banco

### Fase 3 — Embeddings e Vector Search (Dia 6-8)
- [ ] Integração com sentence-transformers para gerar embeddings
- [ ] Armazenamento dos embeddings no pgvector
- [ ] Busca por similaridade (cosine similarity)
- [ ] Endpoint de busca semântica (`POST /api/search`)
- [ ] Testes com documentos reais

**Entregável:** Busca semântica funcionando — query retorna chunks relevantes rankeados

### Fase 4 — RAG: Retrieval + Generation (Dia 9-11)
- [ ] Template de prompt para o LLM (contexto + pergunta)
- [ ] Integração com Ollama para geração de respostas
- [ ] Pipeline completo: query → embedding → search → context → LLM → resposta
- [ ] Citações: vincular resposta aos chunks fonte
- [ ] Endpoint de Q&A (`POST /api/chat`)

**Entregável:** Pergunta em linguagem natural → resposta com citações dos documentos

### Fase 5 — Frontend React (Dia 12-13)
- [ ] Setup React + Vite
- [ ] Componente de upload de documentos
- [ ] Lista de documentos com status de processamento
- [ ] Interface de chat (pergunta → resposta com citações)
- [ ] Estilização básica (limpa e profissional)

**Entregável:** UI completa e funcional conectada ao backend

### Fase 6 — Polish e Deploy (Dia 14)
- [ ] README.md profissional (com GIFs/screenshots)
- [ ] Docker Compose unificado (backend + frontend + infra)
- [ ] Testes básicos (pytest)
- [ ] Tratamento de erros e edge cases
- [ ] Review final do código

**Entregável:** Projeto pronto para GitHub, com documentação e demo

## Estrutura de Pastas

```
RAG/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── ROADMAP.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/              # Migrations do banco
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI app entry point
│   │   ├── config.py         # Settings via pydantic
│   │   ├── database.py       # SQLAlchemy + async session
│   │   ├── models/           # SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   └── document.py
│   │   ├── schemas/          # Pydantic schemas (request/response)
│   │   │   ├── __init__.py
│   │   │   └── document.py
│   │   ├── api/              # Routers
│   │   │   ├── __init__.py
│   │   │   ├── documents.py
│   │   │   ├── search.py
│   │   │   └── chat.py
│   │   ├── services/         # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── document_processor.py
│   │   │   ├── embedding_service.py
│   │   │   ├── search_service.py
│   │   │   └── chat_service.py
│   │   └── tasks/            # Celery tasks
│   │       ├── __init__.py
│   │       └── process_document.py
│   └── tests/
│       └── __init__.py
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── App.jsx
        ├── main.jsx
        ├── components/
        │   ├── ChatInterface.jsx
        │   ├── DocumentUpload.jsx
        │   └── DocumentList.jsx
        └── api/
            └── client.js
```

## Como Vamos Trabalhar

**Workflow:** Eu (Claude) guio → Você (Arthur) implementa

A cada módulo:
1. Eu explico **o que** vamos fazer e **por quê**
2. Mostro o código com comentários explicativos
3. Você implementa no seu editor / terminal
4. Validamos juntos que está funcionando
5. Commit com mensagem descritiva

Isso garante que você entende cada peça e consegue explicar em entrevistas.

## Decisões Técnicas (ADRs simplificados)

### Por que pgvector em vez de Pinecone/Weaviate?
Empresas já usam PostgreSQL. Adicionar pgvector é pragmático — menos infra para gerenciar, mesmo banco para dados e vetores.

### Por que sentence-transformers em vez de OpenAI Embeddings?
Zero custo, roda local, sem dependência de API externa. O modelo all-MiniLM-L6-v2 tem boa qualidade para 384 dimensões.

### Por que Ollama em vez de OpenAI GPT?
Gratuito, roda local, privacy-first. Fácil trocar o modelo depois. Mostra que você sabe trabalhar com LLMs locais.

### Por que Celery em vez de processar síncrono?
Documentos grandes podem levar minutos para processar. Celery faz isso em background sem travar a API. É o padrão da indústria Python.

### Por que FastAPI em vez de Flask/Django?
Async nativo, type hints com Pydantic, docs automáticas (Swagger/ReDoc), performance superior. É o framework moderno de escolha para APIs Python.
