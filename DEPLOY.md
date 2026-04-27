# Deploying to production

Two options: a VPS (manual, full control) or Railway (managed, easier).

---

## Option A — VPS with Docker Compose + Nginx

Tested on Ubuntu 22.04. You need at least 2 vCPUs and 4 GB RAM to run the embedding model comfortably alongside the other services.

### 1. Server setup

```bash
# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

# Clone the repo
git clone https://github.com/your-username/context-rag.git
cd context-rag
```

### 2. Environment

```bash
cp .env.prod.example .env.prod
```

Edit `.env.prod` and set at minimum:

```env
POSTGRES_PASSWORD=<generate with: openssl rand -base64 32>
GROQ_API_KEY=gsk_...
CORS_ORIGINS=https://yourdomain.com
```

### 3. Start

```bash
chmod +x deploy.sh
./deploy.sh build
./deploy.sh start
./deploy.sh status
```

The app should be accessible on port 80. Check `./deploy.sh logs api` if anything looks wrong.

### 4. HTTPS with Let's Encrypt

```bash
sudo apt install certbot
sudo certbot certonly --standalone -d yourdomain.com

mkdir -p ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/key.pem
sudo chown $USER:$USER ssl/*
```

Uncomment the HTTPS server block in `nginx.prod.conf`, then:

```bash
./deploy.sh restart
```

For auto-renewal, add to crontab:

```
0 3 * * * certbot renew --quiet && docker compose -f docker-compose.prod.yml restart nginx
```

### Useful commands

```bash
./deploy.sh logs api       # tail API logs
./deploy.sh logs worker    # tail Celery logs
./deploy.sh backup         # dump PostgreSQL to ./backups/
./deploy.sh restart        # restart all services
./deploy.sh shell api      # open a shell inside the API container
```

---

## Option B — Railway

Railway handles PostgreSQL, Redis, and the app containers with minimal config. Good if you don't want to manage a server.

1. Fork the repo and connect it to a new Railway project.
2. Add a PostgreSQL plugin and a Redis plugin — Railway injects `DATABASE_URL` and `REDIS_URL` automatically.
3. Set the remaining environment variables in the Railway dashboard:
   - `LLM_PROVIDER=groq`
   - `GROQ_API_KEY=gsk_...`
   - `CORS_ORIGINS=https://your-frontend-url`
4. Deploy. The `railway.toml` in the repo configures the build and start commands.

---

## Troubleshooting

**Workers aren't processing documents** — Check `./deploy.sh logs worker`. The most common cause is Redis not being reachable; verify `REDIS_URL` in your env file.

**Embedding model downloads on every restart** — The first startup pulls `all-MiniLM-L6-v2` (~80 MB). Mount a volume for the model cache if you want to avoid re-downloading:
```yaml
# in docker-compose.prod.yml, under the worker service:
volumes:
  - model-cache:/root/.cache/torch
```

**Out of memory** — The embedding model needs ~500 MB. If your VPS is tight on RAM, set `CELERY_WORKER_CONCURRENCY=1` in your env file to limit parallel processing.

**Database backup/restore**

```bash
# Backup
./deploy.sh backup
# Creates: backups/db_backup_YYYYMMDD_HHMMSS.sql

# Restore
./deploy.sh stop
docker run --rm \
  -v rag-postgres-prod:/var/lib/postgresql/data \
  -v $(pwd)/backups:/backups \
  pgvector/pgvector:pg16 \
  psql -U raguser -d ragdb < /backups/db_backup_YYYYMMDD_HHMMSS.sql
./deploy.sh start
```
