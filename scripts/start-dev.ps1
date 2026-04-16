# =============================================
# start-dev.ps1 — Inicia todos os serviços em janelas separadas
# Usage: .\scripts\start-dev.ps1
# =============================================

Write-Host "=== RAG Pipeline — Iniciando ambiente de dev ===" -ForegroundColor Cyan

# 1. Docker (PostgreSQL + Redis)
Write-Host "[1/4] Subindo Docker (PostgreSQL + Redis)..." -ForegroundColor Blue
docker-compose up -d

Write-Host "Aguardando PostgreSQL ficar pronto..." -ForegroundColor Yellow
$maxAttempts = 20
$attempt = 0
do {
    $attempt++
    Start-Sleep -Seconds 2
    $result = docker exec rag-postgres pg_isready -U raguser -d ragdb 2>&1
    Write-Host "  [$attempt/$maxAttempts] $result"
} while ($result -notmatch "accepting connections" -and $attempt -lt $maxAttempts)

if ($attempt -ge $maxAttempts) {
    Write-Host "[ERRO] PostgreSQL não ficou pronto a tempo. Verifique: docker-compose logs db" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Docker iniciado e PostgreSQL pronto" -ForegroundColor Green

# 2. FastAPI — nova janela PowerShell
Write-Host "[2/4] Iniciando FastAPI (nova janela)..." -ForegroundColor Blue
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$PWD\backend'; Write-Host '=== FastAPI Backend ===' -ForegroundColor Cyan; .\venv\Scripts\activate; uvicorn app.main:app --reload"

Start-Sleep -Seconds 2

# 3. Celery Worker — nova janela PowerShell
Write-Host "[3/4] Iniciando Celery Worker (nova janela)..." -ForegroundColor Blue
Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "cd '$PWD\backend'; Write-Host '=== Celery Worker ===' -ForegroundColor Cyan; .\venv\Scripts\activate; celery -A app.celery_app worker --loglevel=info --pool=solo"

Start-Sleep -Seconds 2

# 4. Frontend React — nova janela PowerShell (se existir)
if (Test-Path "frontend\package.json") {
    Write-Host "[4/4] Iniciando Frontend React (nova janela)..." -ForegroundColor Blue
    Start-Process powershell -ArgumentList "-NoExit", "-Command", `
        "cd '$PWD\frontend'; Write-Host '=== Frontend React ===' -ForegroundColor Cyan; npm run dev"
} else {
    Write-Host "[4/4] Frontend não encontrado, pulando." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Tudo iniciado! ===" -ForegroundColor Cyan
Write-Host "API:      http://localhost:8000" -ForegroundColor White
Write-Host "Docs:     http://localhost:8000/docs" -ForegroundColor White
Write-Host "Frontend: http://localhost:5173" -ForegroundColor White
Write-Host ""
Write-Host "Para parar o Docker: docker-compose down" -ForegroundColor Yellow
