# Guia de Deploy em Produção

Este documento descreve como fazer deploy da aplicação RAG em um servidor de produção (VPS).

## Arquitetura de Produção

```
┌─────────────────────────────────────┐
│         Internet (Users)            │
└──────────────┬──────────────────────┘
               │ HTTP/HTTPS
               ▼
┌──────────────────────────────────────────┐
│    Nginx (Reverse Proxy & Load Balancer) │
│    - Porta 80 (HTTP)                     │
│    - Porta 443 (HTTPS/SSL) [opcional]    │
└──────────────┬──────────────────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
┌──────────────┐   ┌──────────────┐
│  FastAPI API │   │   Frontend   │
│  (Gunicorn)  │   │   (Static)   │
│  Port 8000   │   │  Port 5173   │
└──────┬───────┘   └──────────────┘
       │
       ├─── PostgreSQL (Port 5432 - interno)
       └─── Redis (Port 6379 - interno)
            │
            ▼
       Celery Worker
       (Processamento async)
```

## Pré-requisitos

1. **VPS com:**
   - Ubuntu 20.04+ ou similar
   - 2+ CPUs
   - 4GB+ RAM
   - 20GB+ espaço em disco

2. **Instalado no servidor:**
   - Docker ([instalação](https://docs.docker.com/engine/install/))
   - Docker Compose ([instalação](https://docs.docker.com/compose/install/))
   - Git (para clonar o repositório)

3. **Opcional:**
   - SSL/TLS (Let's Encrypt gratuito)
   - Domínio (para HTTPS)

## Passo 1: Preparar o Servidor

### 1.1 SSH no servidor

```bash
ssh user@seu-vps-ip
```

### 1.2 Update do sistema

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl
```

### 1.3 Instalar Docker

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker
```

Verificar instalação:

```bash
docker --version
docker-compose --version
```

## Passo 2: Clonar Repositório

```bash
# Na home do usuário ou pasta de projetos
git clone https://seu-repo-url.git rag-app
cd rag-app
```

## Passo 3: Configurar Variáveis de Ambiente

### 3.1 Criar .env.prod

```bash
cp .env.prod.example .env.prod
nano .env.prod  # ou vim .env.prod
```

### 3.2 Preencher variáveis importantes

```bash
# === DATABASE ===
POSTGRES_USER=raguser
POSTGRES_PASSWORD=GERE_SENHA_FORTE_COM_OPENSSL
POSTGRES_DB=ragdb

# === LLM PROVIDER ===
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_COLE_CHAVE_GROQ_AQUI

# === CORS ===
CORS_ORIGINS=https://seu-dominio.com

# === OUTROS ===
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=50
```

#### Gerar senha forte:

```bash
openssl rand -base64 32
```

#### Obter chave Groq (gratuita):

1. Vá para https://console.groq.com
2. Login/Signup
3. Crie API key
4. Cole em `GROQ_API_KEY`

## Passo 4: Tornar script de deploy executável

```bash
chmod +x deploy.sh
```

## Passo 5: Iniciar a Aplicação

### 5.1 Build das imagens (primeira vez ou após mudanças)

```bash
./deploy.sh build
```

### 5.2 Iniciar containers

```bash
./deploy.sh start
```

### 5.3 Verificar status

```bash
./deploy.sh status
```

Você verá algo como:

```
NAME                    COMMAND                  SERVICE    STATUS
rag-postgres-prod       "docker-entrypoint..."   db         Up (healthy)
rag-redis-prod          "redis-server /etc/..."  redis      Up (healthy)
rag-api-prod            "gunicorn app.main:..."  api        Up (healthy)
rag-worker-prod         "celery -A app.celery..." worker    Up
rag-frontend-prod       "serve -s dist -l..."    frontend   Up (healthy)
rag-nginx-prod          "nginx -g daemon off"    nginx      Up (healthy)
```

## Passo 6: Acessar a Aplicação

```
HTTP: http://seu-vps-ip
Health Check: http://seu-vps-ip/health
API Docs: http://seu-vps-ip/api/docs
```

## Passo 7: Configurar HTTPS com Let's Encrypt (Recomendado)

### 7.1 Instalar Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 7.2 Gerar certificado

```bash
sudo certbot certonly --standalone -d seu-dominio.com -d www.seu-dominio.com
```

### 7.3 Copiar certificados para o projeto

```bash
mkdir -p ssl
sudo cp /etc/letsencrypt/live/seu-dominio.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/seu-dominio.com/privkey.pem ssl/key.pem
sudo chown $USER:$USER ssl/*
```

### 7.4 Descomentar HTTPS no nginx.prod.conf

Editar `nginx.prod.conf` e descomentar:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name seu-dominio.com;
    return 301 https://$host$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name seu-dominio.com;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ...
}
```

### 7.5 Restart

```bash
./deploy.sh restart
```

### 7.6 Renovação automática (cron)

```bash
sudo crontab -e
# Adicionar linha:
# 0 3 * * * certbot renew --quiet && docker-compose -f /caminho/docker-compose.prod.yml restart nginx
```

## Operações Comuns

### Ver logs da API

```bash
./deploy.sh logs api
```

### Ver logs do worker Celery

```bash
./deploy.sh logs worker
```

### Ver todos os logs

```bash
docker-compose -f docker-compose.prod.yml logs -f
```

### Parar aplicação

```bash
./deploy.sh stop
```

### Reiniciar aplicação

```bash
./deploy.sh restart
```

### Acessar shell da API

```bash
./deploy.sh shell api
```

### Fazer backup do banco

```bash
./deploy.sh backup
```

Backups são salvos em `backups/db_backup_YYYYMMDD_HHMMSS.sql`

### Executar migrations

```bash
./deploy.sh migrate
```

## Monitoramento

### Verificar saúde dos containers

```bash
./deploy.sh status
```

### Health check endpoint

```bash
curl http://seu-vps-ip/health
```

Resposta esperada:

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "embedding_model": "all-MiniLM-L6-v2",
  "llm_model": "llama3-8b-8192",
  "ollama_url": "http://host.docker.internal:11434",
  "ollama_reachable": false,
  "ollama_error": null
}
```

## Troubleshooting

### Erro: "Connection refused"

```bash
# Verificar se containers estão rodando
./deploy.sh status

# Se não estiverem, verificar logs
./deploy.sh logs api
./deploy.sh logs db
```

### Erro: "Database connection timeout"

```bash
# PostgreSQL pode estar iniciando ainda, aguarde 10-15 segundos
./deploy.sh status

# Ou force restart
./deploy.sh restart
```

### Erro: "Disk space full"

```bash
# Ver uso de disco
df -h

# Limpar imagens Docker não usadas
docker image prune -a
```

### Erro: "Port already in use"

```bash
# Ver processos na porta
lsof -i :80
lsof -i :443
lsof -i :8000

# Se outro serviço usa port 80/443, configure Nginx em porta diferente
# Edite nginx.prod.conf
```

## Backup e Recuperação

### Fazer backup

```bash
./deploy.sh backup
```

### Restaurar backup

```bash
# Parar aplicação
./deploy.sh stop

# Restaurar banco
docker run --rm -v rag-postgres-prod:/var/lib/postgresql/data \
  -v $(pwd)/backups:/backups \
  pgvector/pgvector:pg16 \
  psql -U raguser -d ragdb < /backups/db_backup_YYYYMMDD_HHMMSS.sql

# Reiniciar
./deploy.sh start
```

## Performance Tuning

### Aumentar workers da API

Editar `backend/Dockerfile.prod`, linha com `--workers`:

```dockerfile
CMD ["gunicorn", "app.main:app", \
     "--workers", "8",  # ← Aumentar baseado em CPUs
     ...]
```

Fórmula: `workers = (2 * CPU cores) + 1`

### Aumentar memória do Redis

Editar `docker-compose.prod.yml`:

```yaml
redis:
  # ... configuração ...
  command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
```

### Aumentar pool de conexões PostgreSQL

Editar `backend/app/database.py`:

```python
engine = create_async_engine(
    settings.async_database_url,
    pool_size=20,        # ← Aumentar
    max_overflow=10,     # ← Aumentar
)
```

## Segurança

### Checklist de produção:

- [ ] `.env.prod` NÃO está no git (incluir em `.gitignore`)
- [ ] Senhas fortes geradas com `openssl rand -base64 32`
- [ ] HTTPS/SSL configurado
- [ ] CORS_ORIGINS aponta para domínio correto
- [ ] Firewall permite apenas portas 80, 443 de entrada
- [ ] SSH usa chaves (não password)
- [ ] Docker daemon roda com usuário não-root

### Configurar firewall

```bash
sudo ufw enable
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw status
```

## CI/CD Automático (Opcional)

Você pode configurar GitHub Actions para fazer deploy automático:

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: SSH e deploy
        run: |
          ssh -i ${{ secrets.SSH_KEY }} user@vps \
            'cd rag-app && git pull && ./deploy.sh deploy'
```

## Suporte e Debugging

Se tiver problemas:

1. **Verificar logs:** `./deploy.sh logs [service]`
2. **Verificar saúde:** `./deploy.sh status`
3. **Verificar configuração:** `cat .env.prod` (sem revelar senhas)
4. **Reiniciar tudo:** `./deploy.sh restart`

## Próximos Passos

- [ ] Configurar DNS (apontar domínio para VPS)
- [ ] Configurar HTTPS/SSL
- [ ] Configurar backups automáticos
- [ ] Configurar CI/CD
- [ ] Monitorar logs com Sentry ou similar
- [ ] Configurar alertas de uptime
