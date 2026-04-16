# Fase 2 — Upload e Processamento

## O que foi feito

Implementamos a infraestrutura completa para:
1. **Upload de documentos** (PDF/DOCX) via API
2. **Extração de texto** de PDF e DOCX
3. **Chunking inteligente** com LangChain (mantém contexto entre chunks)
4. **Armazenamento** de documentos e chunks no PostgreSQL
5. **Processamento assíncrono** via Celery + Redis

## Arquitetura

```
Frontend
   ↓ (POST /api/documents/upload com arquivo)
FastAPI ← enfileira task no Redis
   ↓
Celery Worker ← lê task do Redis
   ↓ (1. Parse do arquivo, 2. Chunking, 3. Salva chunks)
PostgreSQL (documents + chunks)
```

## Como testar

### 1. Confirme que tudo está rodando

```powershell
# Terminal 1: Docker
docker-compose ps
# Você verá rag-postgres e rag-redis rodando

# Terminal 2: FastAPI
cd backend
.\venv\Scripts\activate
uvicorn app.main:app --reload

# Terminal 3: Celery Worker
cd backend
.\venv\Scripts\activate
celery -A app.celery_app worker --loglevel=info
```

### 2. Upload de um documento via Swagger

1. Acesse `http://localhost:8000/docs`
2. Procure por **POST /api/documents/upload**
3. Clique em "Try it out"
4. Selecione um PDF ou DOCX do seu computador
5. Clique em "Execute"

**Resposta esperada** (201 Created):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "meu_documento.pdf",
  "status": "pending",
  "total_chunks": 0,
  "error_message": null,
  "created_at": "2026-04-16T02:00:00",
  "updated_at": "2026-04-16T02:00:00"
}
```

### 3. Acompanhe o processamento

Copie o `id` da resposta acima e use para verificar o status:

```bash
# GET /api/documents/{id}/status
curl http://localhost:8000/api/documents/550e8400-e29b-41d4-a716-446655440000/status
```

**Respostas esperadas:**

**Enquanto está processando:**
```json
{
  "status": "processing",
  "total_chunks": 0
}
```

**Após sucesso:**
```json
{
  "status": "done",
  "total_chunks": 15,
  "error_message": null
}
```

### 4. Veja o documento com seus chunks

```bash
curl http://localhost:8000/api/documents/550e8400-e29b-41d4-a716-446655440000
```

**Resposta:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "meu_documento.pdf",
  "status": "done",
  "total_chunks": 15,
  "chunks": [
    {
      "id": "...",
      "chunk_index": 0,
      "content": "Primer chunk de texto..."
    },
    {
      "id": "...",
      "chunk_index": 1,
      "content": "Segundo chunk de texto..."
    }
    // ... mais chunks
  ]
}
```

### 5. Liste todos os documentos

```bash
curl http://localhost:8000/api/documents
```

## O que observar

### Terminal do Celery Worker

Você verá logs tipo:
```
[2026-04-16 02:00:00,000: INFO/MainProcess] Task process_document[abc-123] received
[2026-04-16 02:00:01,234: INFO/MainProcess] Task process_document[abc-123] succeeded in 1.23s: {...}
```

### Banco de dados

Dados sendo salvos em **duas tabelas**:

```sql
-- Documents (rastreamento)
SELECT * FROM documents;

-- Chunks (conteúdo)
SELECT chunk_index, LENGTH(content) as chars FROM chunks WHERE document_id = '...' ORDER BY chunk_index;
```

## Decisões de Design

**Por que separar Document e Chunk?**
- Um documento com 100 páginas gera 50-200 chunks
- Pesquisar por chunks (não documentos) permite encontrar exatamente qual seção é relevante
- Na Fase 3, a busca retorna chunks + documentos fonte

**Por que Celery em background?**
- PDF grande pode levar 10+ segundos para processar
- Se fosse síncrono, o upload.js demoraria muito (timeout HTTP)
- Celery deixa a API responder imediatamente e processa em paralelo

**Por que pgvector?**
- Já usamos PostgreSQL para dados estruturados
- pgvector é extensão nativa (não é um banco separado)
- A query de similaridade é SQL: `SELECT * FROM chunks ORDER BY embedding <-> query_embedding LIMIT 5`

## Troubleshooting

### "Documento fica em PENDING e nunca passa para DONE"

**Causa:** Celery worker não está rodando.

**Solução:**
```powershell
# Terminal 3
cd backend
.\venv\Scripts\activate
celery -A app.celery_app worker --loglevel=info
```

### "Error: document.pdf (No such file or directory)"

**Causa:** O arquivo foi salvo em um caminho, mas o worker está rodando em outro lugar.

**Solução:** Certifique-se que `UPLOAD_DIR` é um caminho absoluto ou relativo do mesmo diretório.

### "Connection refused: 6379"

**Causa:** Redis não está rodando.

**Solução:**
```powershell
docker-compose up -d
docker-compose logs redis
```

## Próximo: Fase 3

Agora que temos documentos + chunks no banco, vamos:
1. Gerar embeddings com sentence-transformers
2. Fazer busca semântica com pgvector
3. Criar endpoint de Q&A com retrieval + LLM

**ETA:** 3 dias
