# Checklist de Deployment

Use este checklist para garantir que tudo está pronto antes de fazer deploy em produção.

## Pre-Deployment

- [ ] Código está commitado no git
- [ ] Todos os testes passam: `pytest backend/tests/`
- [ ] Linting passou: `eslint frontend/` (se configurado)
- [ ] Não há secrets/senhas commitadas no repo
- [ ] .env.prod foi criado com variáveis corretas
- [ ] Senha do PostgreSQL foi gerada com `openssl rand -base64 32`
- [ ] Chave Groq foi obtida em https://console.groq.com
- [ ] Domínio está apontando para VPS (DNS)

## Infraestrutura

- [ ] VPS tem 2+ CPUs, 4GB+ RAM, 20GB+ espaço
- [ ] Docker está instalado: `docker --version`
- [ ] Docker Compose está instalado: `docker-compose --version`
- [ ] SSH access configurado (não password-based)
- [ ] Firewall permite portas 22 (SSH), 80 (HTTP), 443 (HTTPS)

## Arquivos de Configuração

- [ ] `backend/Dockerfile.prod` existe
- [ ] `backend/Dockerfile.worker.prod` existe
- [ ] `frontend/Dockerfile.prod` existe
- [ ] `docker-compose.prod.yml` existe
- [ ] `nginx.prod.conf` existe
- [ ] `.env.prod` existe (não commitado)
- [ ] `.env.prod` tem todos os valores preenchidos
- [ ] `deploy.sh` é executável: `chmod +x deploy.sh`

## Segurança (IMPORTANTE)

- [ ] POSTGRES_PASSWORD é forte (32 chars aleatória)
- [ ] GROQ_API_KEY não está em texto plano em repo
- [ ] .env.prod está em `.gitignore`
- [ ] Não há hardcoded passwords em código
- [ ] CORS_ORIGINS aponta para domínio correto
- [ ] Firewall restringe acesso apenas a portas 80/443
- [ ] SSH usa public key auth (não password)
- [ ] Docker não roda como root

## Certificados SSL (Se usar HTTPS)

- [ ] Let's Encrypt certificado foi gerado
- [ ] Certificado foi copiado para `ssl/cert.pem`
- [ ] Chave foi copiada para `ssl/key.pem`
- [ ] Permissões corretas: `chmod 600 ssl/key.pem`
- [ ] `nginx.prod.conf` foi descomentar seções HTTPS
- [ ] Renovação automática foi configurada em cron

## Database

- [ ] Backup do banco de dados foi feito: `./deploy.sh backup`
- [ ] Migrations foram rodadas (se houver)
- [ ] Índices pgvector foram criados
- [ ] Pool de conexões está configurado corretamente

## Volumes e Persistência

- [ ] `pgdata` volume foi criado: `docker volume create rag-pgdata`
- [ ] `redis-data` volume foi criado: `docker volume create rag-redis-data`
- [ ] Diretório `./backend/uploads` existe e é writable
- [ ] Volumes estão mapeados corretamente em docker-compose.prod.yml

## Performance

- [ ] Gunicorn workers definidos: `--workers 4` (ajustar para CPU cores)
- [ ] Celery concurrency configurado: `--concurrency 4`
- [ ] PostgreSQL pool_size configurado
- [ ] Nginx gzip compression habilitado
- [ ] Cache headers configurados para assets estáticos

## Monitoring & Logging

- [ ] Health check endpoint testado: `curl http://localhost/health`
- [ ] Logs estão sendo capturados corretamente
- [ ] Alertas foram configurados (opcional)
- [ ] Monitoramento foi configurado (opcional)

## Pré-deployment Test

Execute antes de ir para prod:

```bash
# 1. Build das imagens
./deploy.sh build

# 2. Iniciar containers
./deploy.sh start

# 3. Verificar status
./deploy.sh status

# 4. Testar health check
curl http://localhost/health

# 5. Testar API
curl http://localhost/api/docs

# 6. Testar frontend
curl http://localhost/

# 7. Ver logs de erros
./deploy.sh logs api
./deploy.sh logs worker
./deploy.sh logs db

# 8. Parar (cleanup antes de deploy real)
./deploy.sh stop
```

## Deploy Checklist

- [ ] Executar `./deploy.sh deploy` (faz backup automático)
- [ ] Aguardar até "Deploy concluído com sucesso"
- [ ] Verificar status: `./deploy.sh status`
- [ ] Acessar aplicação: `https://seu-dominio.com`
- [ ] Testar upload de documento
- [ ] Testar busca
- [ ] Testar chat com RAG
- [ ] Verificar logs para erros: `./deploy.sh logs api`

## Post-Deployment

- [ ] Backup automático foi configurado (cron)
- [ ] Monitoramento foi configurado (alertas)
- [ ] Rollback plan foi documentado
- [ ] Team foi notificado do deploy
- [ ] Documentação foi atualizada
- [ ] Logs estão sendo monitorados

## Rollback Plan

Se algo der errado:

```bash
# 1. Parar aplicação
./deploy.sh stop

# 2. Restore backup
# (ver instruções em README.DEPLOY.md)

# 3. Reiniciar
./deploy.sh start

# 4. Investigar logs
./deploy.sh logs api
```

## Performance Tuning (Pós-Deploy)

Se aplicação ficar lenta:

- [ ] Aumentar Gunicorn workers
- [ ] Aumentar Celery concurrency
- [ ] Aumentar PostgreSQL pool_size
- [ ] Usar managed database (AWS RDS)
- [ ] Usar managed Redis (AWS ElastiCache)
- [ ] Adicionar caching layer (Redis cache)
- [ ] Otimizar queries (EXPLAIN ANALYZE)

## Security Audit (Pós-Deploy)

- [ ] Verificar HTTPS está habilitado
- [ ] Testar CORS com ferramentas online
- [ ] Verificar rate limiting (via Nginx)
- [ ] Testar SQL injection (deve falhar)
- [ ] Verificar file upload validations
- [ ] Checklist OWASP Top 10

## Documentação Pós-Deploy

- [ ] README.DEPLOY.md foi atualizado com domínio real
- [ ] QUICKSTART.md foi atualizado
- [ ] Team tem acesso ao guia de operações
- [ ] Runbook de troubleshooting foi criado
- [ ] On-call guide foi atualizado

## Final Verification

```bash
# Health check
curl https://seu-dominio.com/health

# API é acessível
curl https://seu-dominio.com/api/docs

# Frontend carrega
curl https://seu-dominio.com

# Database está saudável
./deploy.sh logs db | grep -i error

# Workers estão processando
./deploy.sh logs worker | grep -i "worker online"

# Nginx está rodando
./deploy.sh logs nginx | grep -i error
```

## Após confirmar tudo funcionando:

✅ **Deployment bem-sucedido!**

Próximos passos:
- Monitor logs por 24h
- Backup diário configurado
- Alertas configurados
- Team notificado
- Documentação atualizada

---

## Template de Comunicação para Team

```
🚀 Deployment realizado com sucesso!

Alterações:
- Setup de produção com Docker + Nginx
- Gunicorn para FastAPI
- Celery worker otimizado
- Nginx reverse proxy

Status: ✅ Operacional

Acessar em:
- Frontend: https://seu-dominio.com
- API: https://seu-dominio.com/api
- Docs: https://seu-dominio.com/api/docs
- Health: https://seu-dominio.com/health

Comandos úteis:
./deploy.sh logs api       # Ver logs API
./deploy.sh status         # Ver status containers
./deploy.sh backup         # Fazer backup BD
./deploy.sh restart        # Reiniciar app

Rollback procedure:
./deploy.sh stop
# restore DB from backup
./deploy.sh start

Contacts para issues:
- [@seu-nome] - Ops/Deploy
```

---

## Notes

Qualquer problema durante deployment:
1. Ver logs: `./deploy.sh logs [service]`
2. Não parar - tomar screenshot de erros
3. Investigar root cause
4. Fixar problema
5. Testar localmente se possível
6. Fazer deploy novamente

Documentação completa em:
- README.DEPLOY.md - Guia detalhado de deploy
- ARCHITECTURE.md - Arquitetura técnica
- QUICKSTART.md - Desenvolvimento local
