#!/bin/bash
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                     WScaner — Stop All Services                            ║
# ║                         macOS / Linux                                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

PROJECT_DIR="$HOME/wscaner"

echo ""
echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║       🛑  WScaner — Остановка сервисов       ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Check if project exists
if [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
    echo -e "  ${YELLOW}⚠️${NC}  Проект не найден: $PROJECT_DIR"
    echo -e "  Нечего останавливать."
    echo ""
    exit 0
fi

# Check Docker
if ! command -v docker &>/dev/null; then
    echo -e "  ${RED}❌${NC} Docker не найден."
    exit 1
fi

if ! docker info &>/dev/null 2>&1; then
    echo -e "  ${YELLOW}⚠️${NC}  Docker не запущен. Сервисы уже остановлены."
    echo ""
    exit 0
fi

cd "$PROJECT_DIR"

# Check running containers
RUNNING=$(docker compose ps --format "{{.Name}}" 2>/dev/null | grep -c ".")
if [ "$RUNNING" -eq 0 ]; then
    echo -e "  ${GREEN}✅${NC} Сервисы уже остановлены."
    echo ""
    exit 0
fi

# Show what's running
echo -e "  ${BOLD}Запущенные сервисы:${NC}"
echo "  ────────────────────────────────────────────"
docker compose ps --format "table {{.Name}}\t{{.State}}\t{{.Ports}}" 2>/dev/null
echo "  ────────────────────────────────────────────"
echo ""

echo -e "  ⏳ Остановка всех сервисов..."
echo ""

if docker compose down; then
    echo ""
    echo -e "  ${GREEN}✅${NC} Все сервисы остановлены."
else
    echo ""
    echo -e "  ${YELLOW}⚠️${NC}  Принудительная остановка..."
    docker compose down --remove-orphans --timeout 10
    echo ""
    echo -e "  ${GREEN}✅${NC} Сервисы остановлены принудительно."
fi

echo ""
echo -e "  ${DIM}Полезные команды:${NC}"
echo -e "  ${DIM}  docker compose up -d     — запустить снова${NC}"
echo -e "  ${DIM}  docker system prune -f   — очистить кэш Docker${NC}"
echo -e "  ${DIM}  docker volume prune -f   — удалить неиспользуемые данные${NC}"
echo ""
