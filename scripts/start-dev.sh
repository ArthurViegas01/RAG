#!/bin/bash
# =============================================
# start-dev.sh — Inicia todos os serviços (Linux/Mac/WSL)
# Usage: bash scripts/start-dev.sh
# =============================================

echo -e "\033[0;36m=== RAG Pipeline — Iniciando ambiente de dev ===\033[0m"

# 1. Docker
echo "[1/4] Subindo Docker (PostgreSQL + Redis)..."
docker-compose up -d
sleep 3
echo "[OK] Docker iniciado"

# 2. FastAPI em background
echo "[2/4] Iniciando FastAPI..."
cd backend
source venv/bin/activate
uvicorn app.main:app --reload &
FASTAPI_PID=$!
cd ..
echo "[OK] FastAPI rodando (PID: $FASTAPI_PID)"

sleep 2

# 3. Celery Worker em background
echo "[3/4] Iniciando Celery Worker..."
cd backend
source venv/bin/activate
celery -A app.celery_app worker --loglevel=info &
CELERY_PID=$!
cd ..
echo "[OK] Celery rodando (PID: $CELERY_PID)"

# 4. Frontend
if [ -f "frontend/package.json" ]; then
    echo "[4/4] Iniciando Frontend React..."
    cd frontend
    npm run dev &
    FRONTEND_PID=$!
    cd ..
    echo "[OK] Frontend rodando (PID: $FRONTEND_PID)"
fi

echo ""
echo -e "\033[0;36m=== Tudo iniciado! ===\033[0m"
echo "API:      http://localhost:8000"
echo "Docs:     http://localhost:8000/docs"
echo "Frontend: http://localhost:5173"
echo ""
echo "Para parar tudo: kill $FASTAPI_PID $CELERY_PID $FRONTEND_PID && docker-compose down"
