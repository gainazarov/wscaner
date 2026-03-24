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
echo -e "${CYAN}─── Step 1/4: Checking prerequisites ───────────────────${NC}"
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
        echo -e "${INFO} Please install Docker Desktop for Mac:"
    else
        echo -e "${INFO} Please install Docker Desktop:"
    fi
    echo ""
    echo -e "    ${BOLD}https://www.docker.com/products/docker-desktop/${NC}"
    echo ""
    echo -e "${DIM}    After installing, run this script again.${NC}"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
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

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: Clone or update project
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${CYAN}─── Step 2/4: Project setup ────────────────────────────${NC}"
echo ""

# Determine if we're already inside the project
if [ -f "$SCRIPT_DIR/docker-compose.yml" ] && [ -d "$SCRIPT_DIR/backend" ] && [ -d "$SCRIPT_DIR/scanner" ]; then
    # We're inside the project directory already
    PROJECT_DIR="$SCRIPT_DIR"
    echo -e "${CHECK} Project found in current directory"

    # Pull latest changes
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
    # Not inside project — need to clone
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
# STEP 3: Build & Start containers (with progress)
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${CYAN}─── Step 3/4: Building & starting services ─────────────${NC}"
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
    # Highlight key build events
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

# Start containers
echo -e "${WAIT} Starting containers..."
docker compose up -d 2>&1
echo -e "${CHECK} Containers started"

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: Health checks & status
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "${CYAN}─── Step 4/4: Waiting for services ─────────────────────${NC}"
echo ""

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

if docker compose exec -T redis redis-cli ping &>/dev/null 2>&1; then
    echo -e "  Redis:    ${GREEN}🟢 running${NC}"
else
    echo -e "  Redis:    ${RED}🔴 starting...${NC}"
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
