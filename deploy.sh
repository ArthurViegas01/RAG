#!/bin/bash

# ============================================
# Script de Deploy em Produção
# ============================================
# Uso: ./deploy.sh [start|stop|restart|logs|status|backup]

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================
# Funções auxiliares
# ============================================

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_env() {
    if [ ! -f ".env.prod" ]; then
        print_error ".env.prod não encontrado!"
        print_info "Crie o arquivo: cp .env.prod.example .env.prod"
        exit 1
    fi
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker não está instalado!"
        exit 1
    fi
}

# ============================================
# Comandos
# ============================================

cmd_start() {
    print_info "Iniciando aplicação em produção..."
    check_env
    docker-compose -f docker-compose.prod.yml up -d
    print_info "Aguardando containers ficarem saudáveis..."
    sleep 5
    docker-compose -f docker-compose.prod.yml ps
    print_info "✓ Aplicação iniciada!"
    print_info "API: http://localhost/api"
    print_info "Health check: http://localhost/health"
}

cmd_stop() {
    print_info "Parando aplicação..."
    docker-compose -f docker-compose.prod.yml down
    print_info "✓ Aplicação parada!"
}

cmd_restart() {
    print_info "Reiniciando aplicação..."
    cmd_stop
    sleep 2
    cmd_start
}

cmd_logs() {
    service=${1:-"api"}
    print_info "Mostrando logs de $service (Ctrl+C para sair)..."
    docker-compose -f docker-compose.prod.yml logs -f "$service"
}

cmd_status() {
    print_info "Status dos containers:"
    docker-compose -f docker-compose.prod.yml ps
    print_info ""
    print_info "Verificando saúde da API..."
    if curl -s http://localhost/health > /dev/null; then
        print_info "✓ API está saudável"
    else
        print_warn "⚠ API pode não estar respondendo"
    fi
}

cmd_backup() {
    print_info "Fazendo backup do banco de dados..."
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="backups/db_backup_${TIMESTAMP}.sql"

    mkdir -p backups

    docker-compose -f docker-compose.prod.yml exec -T db \
        pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$BACKUP_FILE"

    print_info "✓ Backup salvo em: $BACKUP_FILE"
    ls -lh "$BACKUP_FILE"
}

cmd_build() {
    print_info "Buildando imagens Docker..."
    docker-compose -f docker-compose.prod.yml build
    print_info "✓ Build concluído!"
}

cmd_deploy() {
    print_info "Executando deploy completo..."
    print_info "1. Fazendo backup do banco..."
    cmd_backup

    print_info "2. Parando aplicação..."
    cmd_stop

    print_info "3. Buildando imagens..."
    cmd_build

    print_info "4. Iniciando aplicação..."
    cmd_start

    print_info "✓ Deploy concluído com sucesso!"
}

cmd_shell() {
    service=${1:-"api"}
    print_info "Abrindo shell no container $service..."
    docker-compose -f docker-compose.prod.yml exec "$service" /bin/bash
}

cmd_migrate() {
    print_info "Executando migrations no banco de dados..."
    docker-compose -f docker-compose.prod.yml exec -T api \
        python -m alembic upgrade head
    print_info "✓ Migrations executadas!"
}

# ============================================
# Main
# ============================================

check_docker

COMMAND=${1:-"status"}

case "$COMMAND" in
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    logs)
        cmd_logs "${2:-api}"
        ;;
    status)
        cmd_status
        ;;
    backup)
        cmd_backup
        ;;
    build)
        cmd_build
        ;;
    deploy)
        cmd_deploy
        ;;
    shell)
        cmd_shell "${2:-api}"
        ;;
    migrate)
        cmd_migrate
        ;;
    *)
        echo "Uso: $0 [comando] [opções]"
        echo ""
        echo "Comandos:"
        echo "  start              - Inicia containers em produção"
        echo "  stop               - Para containers"
        echo "  restart            - Reinicia containers"
        echo "  logs [service]     - Mostra logs (api, worker, db, redis, nginx)"
        echo "  status             - Mostra status dos containers"
        echo "  backup             - Faz backup do banco de dados"
        echo "  build              - Faz build das imagens Docker"
        echo "  deploy             - Deploy completo (backup + build + start)"
        echo "  shell [service]    - Abre shell em um container"
        echo "  migrate            - Executa migrations do banco"
        echo ""
        echo "Exemplos:"
        echo "  ./deploy.sh start"
        echo "  ./deploy.sh logs api"
        echo "  ./deploy.sh logs worker"
        echo "  ./deploy.sh status"
        exit 1
        ;;
esac
