# =============================================
# setup.ps1 — Rodar UMA VEZ para configurar o projeto
# Usage: .\scripts\setup.ps1
# =============================================

Write-Host "=== RAG Pipeline — Setup Inicial ===" -ForegroundColor Cyan

# 1. Copiar .env
if (-Not (Test-Path "backend\.env")) {
    Copy-Item "backend\.env.example" "backend\.env" -ErrorAction SilentlyContinue
    Copy-Item ".env.example" ".env" -ErrorAction SilentlyContinue
    Write-Host "[OK] .env criado" -ForegroundColor Green
} else {
    Write-Host "[SKIP] .env já existe" -ForegroundColor Yellow
}

# 2. Criar venv se não existir
if (-Not (Test-Path "backend\venv")) {
    Write-Host "Criando venv Python..." -ForegroundColor Blue
    Set-Location backend
    python -m venv venv
    Set-Location ..
    Write-Host "[OK] venv criado" -ForegroundColor Green
} else {
    Write-Host "[SKIP] venv já existe" -ForegroundColor Yellow
}

# 3. Instalar dependências Python
Write-Host "Instalando dependências Python..." -ForegroundColor Blue
Set-Location backend
.\venv\Scripts\activate
pip install -r requirements.txt --quiet
Set-Location ..
Write-Host "[OK] Dependências Python instaladas" -ForegroundColor Green

# 4. Instalar dependências Node (frontend)
if (Test-Path "frontend\package.json") {
    Write-Host "Instalando dependências Node..." -ForegroundColor Blue
    Set-Location frontend
    npm install --silent
    Set-Location ..
    Write-Host "[OK] Dependências Node instaladas" -ForegroundColor Green
}

# 5. Verificar Docker
try {
    docker info | Out-Null
    Write-Host "[OK] Docker está rodando" -ForegroundColor Green
} catch {
    Write-Host "[AVISO] Docker não encontrado. Certifique-se que o Docker Desktop está iniciado." -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Setup concluído! ===" -ForegroundColor Cyan
Write-Host "Para iniciar o projeto, rode:" -ForegroundColor White
Write-Host "  .\scripts\start-dev.ps1" -ForegroundColor Yellow
