#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Verifica se todos os serviços do Papyrus estão funcionando corretamente.

.DESCRIPTION
    Testa: PostgreSQL, Redis, Ollama, API FastAPI e modelos disponíveis.
    Execute antes de iniciar o app para confirmar que tudo está em ordem.

.EXAMPLE
    .\scripts\check-services.ps1
#>

$ErrorActionPreference = "Continue"
$allOk = $true

function Write-Check {
    param($Name, $Ok, $Detail = "")
    $icon  = if ($Ok) { "✅" } else { "❌" }
    $color = if ($Ok) { "Green" } else { "Red" }
    Write-Host "$icon  $Name" -ForegroundColor $color
    if ($Detail) {
        Write-Host "     $Detail" -ForegroundColor DarkGray
    }
    if (-not $Ok) { $script:allOk = $false }
}

function Write-Warn {
    param($Name, $Detail = "")
    Write-Host "⚠️  $Name" -ForegroundColor Yellow
    if ($Detail) { Write-Host "     $Detail" -ForegroundColor DarkGray }
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  Papyrus — Diagnóstico de Serviços" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# ── 1. Docker Desktop ─────────────────────────────────────────────────────────
try {
    $dockerInfo = docker info 2>&1
    $dockerOk = $LASTEXITCODE -eq 0
    Write-Check "Docker Desktop" $dockerOk $(if (-not $dockerOk) { "Execute o Docker Desktop e aguarde inicializar." })
} catch {
    Write-Check "Docker Desktop" $false "Comando 'docker' não encontrado."
}

# ── 2. Containers em execução ─────────────────────────────────────────────────
$containers = @("rag-postgres", "rag-redis", "rag-api", "rag-worker", "rag-frontend")
Write-Host ""
Write-Host "  Containers:" -ForegroundColor DarkGray

foreach ($c in $containers) {
    try {
        $state = docker inspect --format "{{.State.Status}}" $c 2>&1
        $running = $state -eq "running"
        Write-Check "  $c" $running $(if (-not $running) { "Estado: $state — rode: docker-compose up" })
    } catch {
        Write-Check "  $c" $false "Container não encontrado"
    }
}

# ── 3. PostgreSQL ─────────────────────────────────────────────────────────────
Write-Host ""
try {
    $pgCheck = docker exec rag-postgres pg_isready -U raguser -d ragdb 2>&1
    $pgOk = $LASTEXITCODE -eq 0
    Write-Check "PostgreSQL (porta 5432)" $pgOk $(if (-not $pgOk) { $pgCheck })
} catch {
    Write-Check "PostgreSQL (porta 5432)" $false "Erro ao verificar: $_"
}

# ── 4. Redis ──────────────────────────────────────────────────────────────────
try {
    $redisCheck = docker exec rag-redis redis-cli ping 2>&1
    $redisOk = $redisCheck -eq "PONG"
    Write-Check "Redis (porta 6379)" $redisOk $(if (-not $redisOk) { "Resposta: $redisCheck" })
} catch {
    Write-Check "Redis (porta 6379)" $false "Erro ao verificar: $_"
}

# ── 5. FastAPI ────────────────────────────────────────────────────────────────
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
    $apiOk = $response.status -eq "healthy"
    Write-Check "FastAPI (porta 8000)" $apiOk

    if ($apiOk) {
        Write-Host "     Modelo embedding : $($response.embedding_model)" -ForegroundColor DarkGray
        Write-Host "     Modelo LLM       : $($response.llm_model)" -ForegroundColor DarkGray
        Write-Host "     Ollama URL       : $($response.ollama_url)" -ForegroundColor DarkGray

        if ($response.ollama_reachable) {
            Write-Check "  Ollama acessível via API" $true
        } else {
            Write-Check "  Ollama acessível via API" $false "Erro: $($response.ollama_error)"
        }
    }
} catch {
    Write-Check "FastAPI (porta 8000)" $false "Erro: $_ — verifique se 'docker-compose up' rodou"
}

# ── 6. Ollama direto no host ──────────────────────────────────────────────────
Write-Host ""
try {
    $ollamaResp = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5
    $ollamaOk = $true
    $models = $ollamaResp.models | ForEach-Object { $_.name }
    Write-Check "Ollama no host (porta 11434)" $true
    Write-Host "     Modelos instalados: $($models -join ', ')" -ForegroundColor DarkGray

    $llama3 = $models | Where-Object { $_ -like "llama3*" }
    if ($llama3) {
        Write-Check "  Modelo llama3 disponível" $true "$llama3"
    } else {
        Write-Check "  Modelo llama3 disponível" $false "Execute: ollama pull llama3"
    }
} catch {
    Write-Check "Ollama no host (porta 11434)" $false (
        "Ollama não está rodando!`n" +
        "     Solução: abra um terminal e execute 'ollama serve'"
    )
}

# ── 7. Frontend ───────────────────────────────────────────────────────────────
Write-Host ""
try {
    $frontResp = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 5 -UseBasicParsing
    Write-Check "Frontend React (porta 5173)" ($frontResp.StatusCode -eq 200)
} catch {
    Write-Check "Frontend React (porta 5173)" $false "Verifique o container rag-frontend"
}

# ── Resumo ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
if ($allOk) {
    Write-Host "  ✅ Todos os serviços estão operacionais!" -ForegroundColor Green
    Write-Host "  Acesse: http://localhost:5173" -ForegroundColor Cyan
} else {
    Write-Host "  ❌ Alguns serviços precisam de atenção." -ForegroundColor Red
    Write-Host "  Corrija os erros acima e rode novamente." -ForegroundColor Yellow
}
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
