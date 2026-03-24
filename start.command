#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 🚀 Ziyo Scanner — One-Click Installer & Launcher (macOS / Linux)
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'
CHECK="${GREEN}[✔]${NC}"
CROSS="${RED}[✘]${NC}"
WAIT="${YELLOW}[…]${NC}"
INFO="${CYAN}[i]${NC}"

REPO_URL="https://github.com/gainazarov/wscaner.git"
PROJECT_DIR_NAME="wscaner"

clear
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  🚀 Ziyo Scanner — Installer & Launcher${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ── Navigate to script directory ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: Check & Install Prerequisites
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${CYAN}─── Step 1/5: Checking prerequisites ───────────────────${NC}"
echo ""

# ── 1a. Check Git ──
echo -e "${WAIT} Checking Git..."
if command -v git &>/dev/null; then
    GIT_VER=$(git --version | awk '{print $3}')
    echo -e "${CHECK} Git found: v${GIT_VER}"
else
    echo -e "${CROSS} Git is not installed."
    echo ""
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "${INFO} Installing Git via Xcode Command Line Tools..."
        xcode-select --install 2>/dev/null || true
        echo ""
        echo -e "${YELLOW}    A dialog will appear — click \"Install\" and wait.${NC}"
        echo -e "${YELLOW}    After installation, run this script again.${NC}"
    else
        echo -e "${INFO} Install Git with your package manager:"
        echo "    Ubuntu/Debian: sudo apt install git"
        echo "    Fedora:        sudo dnf install git"
        echo "    Arch:          sudo pacman -S git"
    fi
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# ── 1b. Check Docker ──
echo -e "${WAIT} Checking Docker..."
if command -v docker &>/dev/null; then
    DOCKER_VER=$(docker --version | awk '{print $3}' | tr -d ',')
    echo -e "${CHECK} Docker found: v${DOCKER_VER}"
else
    echo -e "${CROSS} Docker is not installed."
    echo ""
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # Check if Homebrew is available for auto-install
        if command -v brew &>/dev/null; then
            echo -e "${INFO} Installing Docker Desktop via Homebrew..."
            brew install --cask docker
            if [ $? -eq 0 ]; then
                echo -e "${CHECK} Docker Desktop installed"
                echo -e "${INFO} Starting Docker Desktop for the first time..."
                open -a "Docker"
                echo -ne "${WAIT} Waiting for Docker to initialize (first launch takes 1-2 min) "
                RETRIES=0
                while ! command -v docker &>/dev/null || ! docker info &>/dev/null 2>&1; do
                    echo -n "."
                    sleep 5
                    RETRIES=$((RETRIES + 1))
                    if [ $RETRIES -gt 60 ]; then
                        echo ""
                        echo -e "${CROSS} Docker is taking too long to start."
                        echo -e "    Please open Docker Desktop manually and run this script again."
                        read -p "Press Enter to exit..."
                        exit 1
                    fi
                done
                echo ""
                DOCKER_VER=$(docker --version | awk '{print $3}' | tr -d ',')
                echo -e "${CHECK} Docker is ready: v${DOCKER_VER}"
            else
                echo -e "${CROSS} Homebrew install failed. Opening download page..."
                open "https://www.docker.com/products/docker-desktop/"
                echo ""
                echo -e "    ${BOLD}Install Docker Desktop from the opened page.${NC}"
                echo -e "${DIM}    After installing, run this script again.${NC}"
                read -p "Press Enter to exit..."
                exit 1
            fi
        else
            echo -e "${INFO} Opening Docker Desktop download page..."
            open "https://www.docker.com/products/docker-desktop/"
            echo ""
            echo -e "    ${BOLD}Download and install Docker Desktop from the opened page.${NC}"
            echo -e "${DIM}    Drag Docker to Applications, then launch it.${NC}"
            echo ""
            read -p "    Press Enter after you've installed and started Docker..."
            echo ""
            if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
                DOCKER_VER=$(docker --version | awk '{print $3}' | tr -d ',')
                echo -e "${CHECK} Docker detected: v${DOCKER_VER}"
            else
                echo -e "${CROSS} Docker still not detected."
                echo -e "    Make sure Docker Desktop is installed and running, then try again."
                read -p "Press Enter to exit..."
                exit 1
            fi
        fi
    else
        echo -e "${INFO} Install Docker for your Linux distribution:"
        echo ""
        echo "    Ubuntu/Debian: https://docs.docker.com/engine/install/ubuntu/"
        echo "    Fedora:        https://docs.docker.com/engine/install/fedora/"
        echo "    Or install Docker Desktop: https://www.docker.com/products/docker-desktop/"
        echo ""
        echo -e "${DIM}    After installing, run this script again.${NC}"
        read -p "Press Enter to exit..."
        exit 1
    fi
fi

# ── 1c. Check Docker is running ──
echo -e "${WAIT} Checking Docker daemon..."
if docker info &>/dev/null 2>&1; then
    echo -e "${CHECK} Docker daemon is running"
else
    echo -e "${YELLOW}[!] Docker daemon is not running.${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "${INFO} Starting Docker Desktop..."
        open -a "Docker"
    else
        echo -e "${INFO} Attempting to start Docker..."
        sudo systemctl start docker 2>/dev/null || true
    fi
    echo -ne "${WAIT} Waiting for Docker to start "
    RETRIES=0
    while ! docker info &>/dev/null 2>&1; do
        echo -n "."
        sleep 3
        RETRIES=$((RETRIES + 1))
        if [ $RETRIES -gt 40 ]; then
            echo ""
            echo -e "${CROSS} Docker failed to start after 2 minutes."
            echo "  Please start Docker Desktop manually and try again."
            read -p "Press Enter to exit..."
            exit 1
        fi
    done
    echo ""
    echo -e "${CHECK} Docker daemon is running"
fi

# ── 1d. Check Docker Compose ──
echo -e "${WAIT} Checking Docker Compose..."
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_VER=$(docker compose version --short 2>/dev/null || docker compose version | awk '{print $NF}')
    echo -e "${CHECK} Docker Compose found: v${COMPOSE_VER}"
else
    echo -e "${CROSS} Docker Compose not found."
    echo "  Please update Docker Desktop to the latest version."
    read -p "Press Enter to exit..."
    exit 1
fi

echo -e "${INFO} Redis will run automatically inside Docker (no local install needed)"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: Clone or update project
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${CYAN}─── Step 2/5: Project setup ────────────────────────────${NC}"
echo ""

# Determine if we're already inside the project
if [ -f "$SCRIPT_DIR/docker-compose.yml" ] && [ -d "$SCRIPT_DIR/backend" ] && [ -d "$SCRIPT_DIR/scanner" ]; then
    PROJECT_DIR="$SCRIPT_DIR"
    echo -e "${CHECK} Project found in current directory"

    echo -e "${WAIT} Checking for updates..."
    if git -C "$PROJECT_DIR" rev-parse --git-dir &>/dev/null 2>&1; then
        CURRENT_HASH=$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || echo "unknown")
        git -C "$PROJECT_DIR" pull --ff-only 2>/dev/null && {
            NEW_HASH=$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || echo "unknown")
            if [ "$CURRENT_HASH" != "$NEW_HASH" ]; then
                echo -e "${CHECK} Updated to latest version"
            else
                echo -e "${CHECK} Already up to date"
            fi
        } || {
            echo -e "${INFO} Could not auto-update (local changes?). Continuing with current version."
        }
    fi
else
    PARENT_DIR="$SCRIPT_DIR"
    PROJECT_DIR="$PARENT_DIR/$PROJECT_DIR_NAME"

    if [ -d "$PROJECT_DIR" ] && [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
        echo -e "${CHECK} Project already cloned at: ${DIM}${PROJECT_DIR}${NC}"
        echo -e "${WAIT} Pulling latest changes..."
        git -C "$PROJECT_DIR" pull --ff-only 2>/dev/null || {
            echo -e "${INFO} Could not auto-update. Continuing with current version."
        }
    else
        echo -e "${WAIT} Cloning project from GitHub..."
        echo -e "${DIM}    ${REPO_URL}${NC}"
        echo ""
        git clone --progress "$REPO_URL" "$PROJECT_DIR" 2>&1
        echo ""
        echo -e "${CHECK} Project cloned successfully"
    fi

    cd "$PROJECT_DIR"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: Configure API keys (backend/.env)
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${CYAN}─── Step 3/5: Configuration ────────────────────────────${NC}"
echo ""

ENV_FILE="$PROJECT_DIR/backend/.env"

if [ -f "$ENV_FILE" ]; then
    # .env exists — check if API keys are already set
    EXISTING_GOOGLE=$(grep -oP '(?<=GOOGLE_SAFE_BROWSING_API_KEY=).+' "$ENV_FILE" 2>/dev/null || true)
    EXISTING_VT=$(grep -oP '(?<=VIRUSTOTAL_API_KEY=).+' "$ENV_FILE" 2>/dev/null || true)

    if [ -n "$EXISTING_GOOGLE" ] && [ -n "$EXISTING_VT" ]; then
        echo -e "${CHECK} API keys already configured"
        echo -e "${DIM}    Google Safe Browsing: ${EXISTING_GOOGLE:0:10}...${NC}"
        echo -e "${DIM}    VirusTotal:           ${EXISTING_VT:0:10}...${NC}"
    else
        echo -e "${INFO} API keys are not set. Let's configure them."
        echo -e "${DIM}    These are needed for domain reputation checks.${NC}"
        echo -e "${DIM}    You can skip by pressing Enter (features will be disabled).${NC}"
        echo ""

        if [ -z "$EXISTING_GOOGLE" ]; then
            echo -e "${CYAN}  Google Safe Browsing API Key${NC}"
            echo -e "${DIM}    Get it free: https://developers.google.com/safe-browsing/v4/get-started${NC}"
            read -p "  → Enter key (or press Enter to skip): " INPUT_GOOGLE
            if [ -n "$INPUT_GOOGLE" ]; then
                if grep -q "GOOGLE_SAFE_BROWSING_API_KEY=" "$ENV_FILE" 2>/dev/null; then
                    sed -i.bak "s|GOOGLE_SAFE_BROWSING_API_KEY=.*|GOOGLE_SAFE_BROWSING_API_KEY=${INPUT_GOOGLE}|" "$ENV_FILE"
                else
                    echo "GOOGLE_SAFE_BROWSING_API_KEY=${INPUT_GOOGLE}" >> "$ENV_FILE"
                fi
                echo -e "${CHECK} Google Safe Browsing API key saved"
            else
                echo -e "${DIM}    Skipped — you can add it later in backend/.env${NC}"
            fi
            echo ""
        fi

        if [ -z "$EXISTING_VT" ]; then
            echo -e "${CYAN}  VirusTotal API Key${NC}"
            echo -e "${DIM}    Get it free: https://www.virustotal.com/gui/my-apikey${NC}"
            read -p "  → Enter key (or press Enter to skip): " INPUT_VT
            if [ -n "$INPUT_VT" ]; then
                if grep -q "VIRUSTOTAL_API_KEY=" "$ENV_FILE" 2>/dev/null; then
                    sed -i.bak "s|VIRUSTOTAL_API_KEY=.*|VIRUSTOTAL_API_KEY=${INPUT_VT}|" "$ENV_FILE"
                else
                    echo "VIRUSTOTAL_API_KEY=${INPUT_VT}" >> "$ENV_FILE"
                fi
                echo -e "${CHECK} VirusTotal API key saved"
            else
                echo -e "${DIM}    Skipped — you can add it later in backend/.env${NC}"
            fi
        fi

        # Clean up sed backup files (macOS creates .bak)
        rm -f "${ENV_FILE}.bak"
    fi
else
    # No .env file — create from template
    echo -e "${INFO} Creating backend/.env configuration..."
    echo ""

    EXAMPLE_FILE="$PROJECT_DIR/backend/.env.example"
    if [ -f "$EXAMPLE_FILE" ]; then
        cp "$EXAMPLE_FILE" "$ENV_FILE"
    else
        # Create minimal .env
        cat > "$ENV_FILE" << 'ENVEOF'
APP_MODE=local
DJANGO_SECRET_KEY=local-dev-key-change-if-needed
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,*
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
SCANNER_SERVICE_URL=http://scanner:8001
GOOGLE_SAFE_BROWSING_API_KEY=
VIRUSTOTAL_API_KEY=
DOMAIN_REPUTATION_CACHE_HOURS=24
ENVEOF
    fi

    echo -e "${CHECK} Configuration file created"
    echo ""
    echo -e "${INFO} Let's configure your API keys for domain reputation checks."
    echo -e "${DIM}    You can skip by pressing Enter (features will be disabled).${NC}"
    echo ""

    echo -e "${CYAN}  Google Safe Browsing API Key${NC}"
    echo -e "${DIM}    Get it free: https://developers.google.com/safe-browsing/v4/get-started${NC}"
    read -p "  → Enter key (or press Enter to skip): " INPUT_GOOGLE
    if [ -n "$INPUT_GOOGLE" ]; then
        sed -i.bak "s|GOOGLE_SAFE_BROWSING_API_KEY=.*|GOOGLE_SAFE_BROWSING_API_KEY=${INPUT_GOOGLE}|" "$ENV_FILE"
        echo -e "${CHECK} Google Safe Browsing API key saved"
    else
        echo -e "${DIM}    Skipped${NC}"
    fi
    echo ""

    echo -e "${CYAN}  VirusTotal API Key${NC}"
    echo -e "${DIM}    Get it free: https://www.virustotal.com/gui/my-apikey${NC}"
    read -p "  → Enter key (or press Enter to skip): " INPUT_VT
    if [ -n "$INPUT_VT" ]; then
        sed -i.bak "s|VIRUSTOTAL_API_KEY=.*|VIRUSTOTAL_API_KEY=${INPUT_VT}|" "$ENV_FILE"
        echo -e "${CHECK} VirusTotal API key saved"
    else
        echo -e "${DIM}    Skipped${NC}"
    fi

    # Clean up sed backup files
    rm -f "${ENV_FILE}.bak"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: Build & Start containers (with progress)
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${CYAN}─── Step 4/5: Building & starting services ─────────────${NC}"
echo ""

# ── Check for port conflicts ──
echo -e "${WAIT} Checking for port conflicts..."
PORT_CONFLICT=0
for PORT in 8000 8001 3000 6080; do
    if lsof -i :$PORT -sTCP:LISTEN &>/dev/null 2>&1; then
        PROC_NAME=$(lsof -i :$PORT -sTCP:LISTEN -t 2>/dev/null | head -1)
        PROC_INFO=$(ps -p "$PROC_NAME" -o comm= 2>/dev/null || echo "unknown")
        # Skip if it's our own docker containers
        if echo "$PROC_INFO" | grep -qi "com.docker\|docker"; then
            continue
        fi
        echo -e "${YELLOW}[!] Port $PORT is in use by: ${PROC_INFO} (PID: ${PROC_NAME})${NC}"
        PORT_CONFLICT=1
    fi
done

if [ "$PORT_CONFLICT" -eq 1 ]; then
    echo ""
    read -p "  Stop conflicting processes and continue? (y/N): " KILL_CONFIRM
    if [[ "$KILL_CONFIRM" =~ ^[Yy]$ ]]; then
        for PORT in 8000 8001 3000 6080; do
            PIDS=$(lsof -i :$PORT -sTCP:LISTEN -t 2>/dev/null || true)
            for PID in $PIDS; do
                PROC_INFO=$(ps -p "$PID" -o comm= 2>/dev/null || echo "unknown")
                if echo "$PROC_INFO" | grep -qi "com.docker\|docker"; then
                    continue
                fi
                kill "$PID" 2>/dev/null && echo -e "${CHECK} Stopped process on port $PORT (PID: $PID)"
            done
        done
        sleep 1
    else
        echo -e "${INFO} Continuing anyway — Docker may fail if ports are busy."
    fi
else
    echo -e "${CHECK} No port conflicts"
fi
echo ""

# Check if images already exist (not first run)
EXISTING_IMAGES=$(docker compose images -q 2>/dev/null | wc -l | tr -d ' ')
if [ "$EXISTING_IMAGES" -gt 0 ] 2>/dev/null; then
    echo -e "${INFO} Existing containers found — rebuilding if needed..."
else
    echo -e "${INFO} First run — building all images (this may take 5-10 minutes)..."
fi
echo ""

# Build with visible progress (--progress=plain shows every step)
echo -e "${BOLD}──── Docker Build Log ──────────────────────────────────${NC}"
docker compose build --progress=plain 2>&1 | while IFS= read -r line; do
    if echo "$line" | grep -qE "^#[0-9]+ \["; then
        echo -e "${DIM}  ${line}${NC}"
    elif echo "$line" | grep -qi "DONE\|CACHED"; then
        echo -e "  ${GREEN}${line}${NC}"
    elif echo "$line" | grep -qi "ERROR\|FAIL"; then
        echo -e "  ${RED}${line}${NC}"
    elif echo "$line" | grep -qi "downloading\|extracting\|pulling"; then
        echo -e "  ${YELLOW}${line}${NC}"
    else
        echo -e "  ${DIM}${line}${NC}"
    fi
done

BUILD_EXIT=${PIPESTATUS[0]}
if [ "$BUILD_EXIT" -ne 0 ]; then
    echo ""
    echo -e "${CROSS} Build failed! Check the errors above."
    read -p "Press Enter to exit..."
    exit 1
fi

echo -e "${BOLD}────────────────────────────────────────────────────────${NC}"
echo ""
echo -e "${CHECK} All images built successfully"
echo ""

# Start containers (Redis starts automatically as part of docker-compose)
echo -e "${WAIT} Starting containers (including Redis)..."
docker compose up -d 2>&1
echo -e "${CHECK} All containers started (backend, scanner, frontend, redis, celery)"

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: Health checks & status
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${CYAN}─── Step 5/5: Waiting for services ─────────────────────${NC}"
echo ""

# Check Redis first
echo -ne "${WAIT} Redis "
RETRIES=0
while ! docker compose exec -T redis redis-cli ping &>/dev/null 2>&1; do
    echo -n "."
    sleep 2
    RETRIES=$((RETRIES + 1))
    if [ $RETRIES -gt 15 ]; then
        echo ""
        echo -e "${YELLOW}    Redis is taking longer than expected...${NC}"
        break
    fi
done
if docker compose exec -T redis redis-cli ping &>/dev/null 2>&1; then
    echo -e " ${GREEN}ready${NC}"
fi

# Check backend
echo -ne "${WAIT} Backend "
RETRIES=0
while ! curl -s http://localhost:8000/api/dashboard/ &>/dev/null; do
    echo -n "."
    sleep 2
    RETRIES=$((RETRIES + 1))
    if [ $RETRIES -gt 30 ]; then
        echo ""
        echo -e "${YELLOW}    Backend is taking longer than expected...${NC}"
        break
    fi
done
if curl -s http://localhost:8000/api/dashboard/ &>/dev/null; then
    echo -e " ${GREEN}ready${NC}"
fi

# Check scanner
echo -ne "${WAIT} Scanner "
RETRIES=0
while ! curl -s http://localhost:8001/health &>/dev/null; do
    echo -n "."
    sleep 2
    RETRIES=$((RETRIES + 1))
    if [ $RETRIES -gt 20 ]; then
        echo ""
        echo -e "${YELLOW}    Scanner is taking longer than expected...${NC}"
        break
    fi
done
if curl -s http://localhost:8001/health &>/dev/null; then
    echo -e " ${GREEN}ready${NC}"
fi

# Check frontend
echo -ne "${WAIT} Frontend "
RETRIES=0
while ! curl -s http://localhost:3000/ &>/dev/null; do
    echo -n "."
    sleep 2
    RETRIES=$((RETRIES + 1))
    if [ $RETRIES -gt 20 ]; then
        echo ""
        echo -e "${YELLOW}    Frontend is taking longer than expected...${NC}"
        break
    fi
done
if curl -s http://localhost:3000/ &>/dev/null; then
    echo -e " ${GREEN}ready${NC}"
fi

echo ""
echo -e "${CYAN}─── System Status ──────────────────────────────────────${NC}"
echo ""

# Final status
if docker compose exec -T redis redis-cli ping &>/dev/null 2>&1; then
    echo -e "  Redis:    ${GREEN}🟢 running${NC}  → port 6379 (Docker)"
else
    echo -e "  Redis:    ${RED}🔴 starting...${NC}"
fi

if curl -s http://localhost:8000/api/dashboard/ &>/dev/null; then
    echo -e "  Backend:  ${GREEN}🟢 running${NC}  → http://localhost:8000"
else
    echo -e "  Backend:  ${RED}🔴 starting...${NC}"
fi

if curl -s http://localhost:8001/health &>/dev/null; then
    echo -e "  Scanner:  ${GREEN}🟢 running${NC}  → http://localhost:8001"
else
    echo -e "  Scanner:  ${RED}🔴 starting...${NC}"
fi

if curl -s http://localhost:3000/ &>/dev/null; then
    echo -e "  Frontend: ${GREEN}🟢 running${NC}  → http://localhost:3000"
else
    echo -e "  Frontend: ${RED}🔴 starting...${NC}"
fi

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}🎉 Ziyo Scanner is ready!${NC}"
echo -e "  ${CYAN}Open: ${BOLD}${GREEN}http://localhost:3000${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ── Open browser ──
if [[ "$OSTYPE" == "darwin"* ]]; then
    open "http://localhost:3000"
elif command -v xdg-open &>/dev/null; then
    xdg-open "http://localhost:3000"
fi

echo "To stop: run ./stop.command or press Enter below"
echo ""

# Keep terminal open
read -p "Press Enter to stop all services..."
echo ""
echo -e "${WAIT} Stopping services..."
docker compose down
echo -e "${CHECK} All services stopped. Goodbye!"
