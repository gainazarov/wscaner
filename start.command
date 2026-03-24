#!/bin/bash
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                     WScaner — One-Click Installer & Launcher               ║
# ║                         macOS / Linux                                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

set -e

# ── Config ────────────────────────────────────────────────────────────────────
REPO_URL="https://github.com/gainazarov/wscaner.git"
PROJECT_DIR="$HOME/wscaner"
FRONTEND_URL="http://localhost:3000"
HEALTH_URL="http://localhost:8000/api/health/"

# ── Colors & Symbols ─────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

CHECK="${GREEN}✅${NC}"
CROSS="${RED}❌${NC}"
WARN="${YELLOW}⚠️${NC}"
ROCKET="${CYAN}🚀${NC}"
SEARCH="${BLUE}🔍${NC}"
PACKAGE="${CYAN}📦${NC}"
LOCK="${YELLOW}🔐${NC}"
DOCKER="${BLUE}🐳${NC}"
GLOBE="${GREEN}🌐${NC}"
GEAR="${BLUE}⚙️${NC}"

# ── Helpers ───────────────────────────────────────────────────────────────────
print_header() {
    echo ""
    echo -e "${BOLD}${CYAN}"
    echo "  ╔══════════════════════════════════════════════╗"
    echo "  ║         🛡️  WScaner Installer  🛡️           ║"
    echo "  ║       Link Discovery & Security Scanner      ║"
    echo "  ╚══════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
}

print_step() {
    echo -e "\n${BOLD}$1${NC}"
}

spinner() {
    local pid=$1
    local msg="$2"
    local frames=("⠋" "⠙" "⠹" "⠸" "⠼" "⠴" "⠦" "⠧" "⠇" "⠏")
    local i=0
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${BLUE}${frames[$i]}${NC} %s" "$msg"
        i=$(( (i + 1) % ${#frames[@]} ))
        sleep 0.1
    done
    wait "$pid"
    return $?
}

progress_bar() {
    local current=$1
    local total=$2
    local width=30
    local pct=$(( current * 100 / total ))
    local filled=$(( current * width / total ))
    local empty=$(( width - filled ))
    local bar=""
    for ((i=0; i<filled; i++)); do bar+="█"; done
    for ((i=0; i<empty; i++)); do bar+="░"; done
    printf "\r  [${GREEN}%s${NC}] %3d%%" "$bar" "$pct"
}

open_browser() {
    if command -v open &>/dev/null; then
        open "$1"
    elif command -v xdg-open &>/dev/null; then
        xdg-open "$1"
    elif command -v sensible-browser &>/dev/null; then
        sensible-browser "$1"
    fi
}

# ── Main ──────────────────────────────────────────────────────────────────────

print_header

# ── Detect Mode ───────────────────────────────────────────────────────────────
if [ -d "$PROJECT_DIR" ] && [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
    MODE="update"
    echo -e "  ${GEAR} ${BOLD}Режим:${NC} Обновление и запуск"
else
    MODE="install"
    echo -e "  ${ROCKET} ${BOLD}Режим:${NC} Первая установка"
fi
echo ""

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Check Git
# ══════════════════════════════════════════════════════════════════════════════
print_step "${SEARCH} Шаг 1: Проверка Git..."

if command -v git &>/dev/null; then
    GIT_VER=$(git --version | awk '{print $3}')
    echo -e "  ${CHECK} Git найден (v${GIT_VER})"
else
    echo -e "  ${WARN} Git не найден"
    echo -e "  ${PACKAGE} Установка Git..."

    if command -v brew &>/dev/null; then
        brew install git 2>&1 | tail -1
    elif command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y -qq git
    elif command -v yum &>/dev/null; then
        sudo yum install -y git
    else
        echo -e "  ${CROSS} Не удалось установить Git автоматически"
        echo -e "  👉 Установите вручную: ${BOLD}https://git-scm.com/downloads${NC}"
        echo ""
        read -p "  Нажмите Enter после установки Git..."
        if ! command -v git &>/dev/null; then
            echo -e "  ${CROSS} Git всё ещё не найден. Выход."
            exit 1
        fi
    fi
    echo -e "  ${CHECK} Git установлен"
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Check Docker
# ══════════════════════════════════════════════════════════════════════════════
print_step "${SEARCH} Шаг 2: Проверка Docker..."

if command -v docker &>/dev/null; then
    DOCKER_VER=$(docker --version | awk '{print $3}' | tr -d ',')
    echo -e "  ${CHECK} Docker найден (v${DOCKER_VER})"
else
    echo -e "  ${CROSS} Docker не найден"
    echo ""
    echo -e "  👉 Установите ${BOLD}Docker Desktop${NC}:"
    echo -e "     ${CYAN}https://www.docker.com/products/docker-desktop/${NC}"
    echo ""

    # Try to open download page
    open_browser "https://www.docker.com/products/docker-desktop/"

    echo -e "  ${WARN} После установки Docker Desktop запустите этот скрипт снова."
    echo ""
    read -p "  Нажмите Enter для выхода..."
    exit 1
fi

# Check docker compose
if ! docker compose version &>/dev/null 2>&1; then
    if ! docker-compose --version &>/dev/null 2>&1; then
        echo -e "  ${CROSS} Docker Compose не найден"
        echo -e "  👉 Обновите Docker Desktop до последней версии"
        read -p "  Нажмите Enter для выхода..."
        exit 1
    fi
fi
echo -e "  ${CHECK} Docker Compose найден"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Ensure Docker is running
# ══════════════════════════════════════════════════════════════════════════════
print_step "${DOCKER} Шаг 3: Проверка запуска Docker..."

if docker info &>/dev/null 2>&1; then
    echo -e "  ${CHECK} Docker запущен"
else
    echo -e "  ${WARN} Docker не запущен"
    echo -e "  ${ROCKET} Запуск Docker Desktop..."

    # macOS
    if [ -d "/Applications/Docker.app" ]; then
        open -a Docker
    # Linux — try systemd
    elif command -v systemctl &>/dev/null; then
        sudo systemctl start docker 2>/dev/null || true
    fi

    # Wait for Docker to be ready (up to 60 seconds)
    echo -ne "  ⏳ Ожидание Docker"
    for i in $(seq 1 60); do
        if docker info &>/dev/null 2>&1; then
            echo ""
            echo -e "  ${CHECK} Docker готов"
            break
        fi
        echo -n "."
        sleep 2
        if [ $i -eq 60 ]; then
            echo ""
            echo -e "  ${CROSS} Docker не запустился за 2 минуты"
            echo -e "  👉 Запустите Docker Desktop вручную и попробуйте снова"
            read -p "  Нажмите Enter для выхода..."
            exit 1
        fi
    done
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Clone or Update Project
# ══════════════════════════════════════════════════════════════════════════════

if [ "$MODE" = "install" ]; then
    # ── INSTALL FLOW ──────────────────────────────────────────────────────────
    print_step "${PACKAGE} Шаг 4: Клонирование проекта..."

    git clone "$REPO_URL" "$PROJECT_DIR" 2>&1 | tail -3
    echo -e "  ${CHECK} Репозиторий загружен"

    cd "$PROJECT_DIR"

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 5 — Setup .env
    # ══════════════════════════════════════════════════════════════════════════
    print_step "${LOCK} Шаг 5: Настройка окружения..."

    echo ""
    echo -e "  ${DIM}Для работы репутации доменов нужны API ключи.${NC}"
    echo -e "  ${DIM}Можно оставить пустыми — сканер будет работать без них.${NC}"
    echo ""

    read -p "  Введите GOOGLE_SAFE_BROWSING_API_KEY (Enter = пропустить): " GSB_KEY
    read -p "  Введите VIRUSTOTAL_API_KEY (Enter = пропустить): " VT_KEY

    # Create .env file for backend
    cat > "$PROJECT_DIR/backend/.env" <<ENVEOF
# WScaner — Backend Environment
APP_MODE=local
DJANGO_SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || echo "local-dev-$(date +%s)")
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,*
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
SCANNER_SERVICE_URL=http://scanner:8001
GOOGLE_SAFE_BROWSING_API_KEY=${GSB_KEY}
VIRUSTOTAL_API_KEY=${VT_KEY}
DOMAIN_REPUTATION_CACHE_HOURS=24
ENVEOF

    echo -e "  ${CHECK} Файл .env создан"

else
    # ── UPDATE FLOW ───────────────────────────────────────────────────────────
    print_step "${PACKAGE} Шаг 4: Обновление проекта..."

    cd "$PROJECT_DIR"

    # Stop existing containers first
    echo -e "  ⏳ Остановка текущих контейнеров..."
    docker compose down 2>/dev/null || true

    # Pull latest changes
    echo -e "  ⬇️  Загрузка обновлений..."
    git pull origin main 2>&1 | tail -3
    echo -e "  ${CHECK} Проект обновлён"

    # Skip .env setup — already exists
    print_step "${LOCK} Шаг 5: Проверка .env..."
    if [ -f "$PROJECT_DIR/backend/.env" ]; then
        echo -e "  ${CHECK} Файл .env найден (сохранён)"
    else
        echo -e "  ${WARN} Файл .env не найден — создаю стандартный..."

        read -p "  Введите GOOGLE_SAFE_BROWSING_API_KEY (Enter = пропустить): " GSB_KEY
        read -p "  Введите VIRUSTOTAL_API_KEY (Enter = пропустить): " VT_KEY

        cat > "$PROJECT_DIR/backend/.env" <<ENVEOF
# WScaner — Backend Environment
APP_MODE=local
DJANGO_SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || echo "local-dev-$(date +%s)")
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,*
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
SCANNER_SERVICE_URL=http://scanner:8001
GOOGLE_SAFE_BROWSING_API_KEY=${GSB_KEY}
VIRUSTOTAL_API_KEY=${VT_KEY}
DOMAIN_REPUTATION_CACHE_HOURS=24
ENVEOF

        echo -e "  ${CHECK} Файл .env создан"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Build
# ══════════════════════════════════════════════════════════════════════════════
print_step "${DOCKER} Шаг 6: Сборка контейнеров..."

echo -e "  ${DIM}Это может занять 3-10 минут при первой сборке...${NC}"
echo ""

# Build with visible progress
docker compose build --progress=plain 2>&1 | while IFS= read -r line; do
    # Show key build milestones
    if echo "$line" | grep -qiE "^#[0-9]+ \[|DONE|successfully|ERROR|CACHED"; then
        # Clean up the line for display
        clean=$(echo "$line" | sed 's/^#[0-9]* //' | head -c 80)
        printf "\r  ${BLUE}⠸${NC} %s\033[K" "$clean"
    fi
done
echo ""
echo -e "  ${CHECK} Сборка завершена"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — Start
# ══════════════════════════════════════════════════════════════════════════════
print_step "${ROCKET} Шаг 7: Запуск сервисов..."

docker compose up -d 2>&1 | tail -5

# Wait for services to be healthy
echo ""
echo -ne "  ⏳ Ожидание готовности сервисов"

SERVICES_READY=false
for i in $(seq 1 45); do
    # Check if backend is responding
    if curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null | grep -q "200"; then
        # Check if frontend is responding
        if curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL" 2>/dev/null | grep -qE "200|304"; then
            SERVICES_READY=true
            break
        fi
    fi
    echo -n "."
    sleep 2
done

echo ""

if [ "$SERVICES_READY" = true ]; then
    echo -e "  ${CHECK} Все сервисы запущены"
else
    echo -e "  ${WARN} Сервисы запускаются (может потребоваться ещё 30 сек)"
    echo -e "  ${DIM}  Если не откроется — подождите и обновите страницу${NC}"
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 8 — Open Browser
# ══════════════════════════════════════════════════════════════════════════════
print_step "${GLOBE} Шаг 8: Открытие интерфейса..."

echo -e "  ${CHECK} Открытие ${BOLD}${FRONTEND_URL}${NC}"
sleep 1
open_browser "$FRONTEND_URL"

# ══════════════════════════════════════════════════════════════════════════════
# Done
# ══════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${GREEN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║          ✅  WScaner запущен!  ✅            ║"
echo "  ║                                              ║"
echo "  ║    🌐  http://localhost:3000                 ║"
echo "  ║    📡  http://localhost:8000/api             ║"
echo "  ║                                              ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "  ${DIM}Для остановки:  docker compose down${NC}"
echo -e "  ${DIM}Для логов:      docker compose logs -f${NC}"
echo ""
echo -e "  ${DIM}Нажмите Enter чтобы остановить сервисы и выйти...${NC}"
read -r

echo ""
echo -e "  ⏳ Остановка сервисов..."
cd "$PROJECT_DIR" && docker compose down
echo -e "  ${CHECK} Сервисы остановлены. До встречи!"
echo ""
