#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# 🚀 Ziyo Scanner — One-Click Local Launcher (macOS / Linux)
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
CHECK="${GREEN}[✔]${NC}"
CROSS="${RED}[✘]${NC}"
WAIT="${YELLOW}[…]${NC}"

clear
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  🚀 Ziyo Scanner — Local-First Launcher${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""

# ── Navigate to project directory ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── 1. Check Git ──
echo -e "${WAIT} Checking Git..."
if command -v git &>/dev/null; then
    echo -e "${CHECK} Git found: $(git --version)"
else
    echo -e "${CROSS} Git not found. Please install Git."
    echo "  → https://git-scm.com/downloads"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# ── 2. Check Docker ──
echo -e "${WAIT} Checking Docker..."
if command -v docker &>/dev/null; then
    echo -e "${CHECK} Docker found: $(docker --version | cut -d' ' -f3 | tr -d ',')"
else
    echo -e "${CROSS} Docker not found. Please install Docker Desktop."
    echo "  → https://www.docker.com/products/docker-desktop/"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# ── 3. Check Docker is running ──
echo -e "${WAIT} Checking Docker daemon..."
if docker info &>/dev/null 2>&1; then
    echo -e "${CHECK} Docker is running"
else
    echo -e "${YELLOW}[!] Docker is not running. Starting Docker Desktop...${NC}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open -a "Docker"
    fi
    echo -e "${WAIT} Waiting for Docker to start..."
    RETRIES=0
    while ! docker info &>/dev/null 2>&1; do
        sleep 2
        RETRIES=$((RETRIES + 1))
        if [ $RETRIES -gt 30 ]; then
            echo -e "${CROSS} Docker failed to start after 60 seconds."
            echo "  Please start Docker Desktop manually and try again."
            read -p "Press Enter to exit..."
            exit 1
        fi
    done
    echo -e "${CHECK} Docker is running"
fi

# ── 4. Check Docker Compose ──
echo -e "${WAIT} Checking Docker Compose..."
if docker compose version &>/dev/null 2>&1; then
    echo -e "${CHECK} Docker Compose found"
else
    echo -e "${CROSS} Docker Compose not found."
    echo "  Please update Docker Desktop to the latest version."
    read -p "Press Enter to exit..."
    exit 1
fi

echo ""
echo -e "${CYAN}─── Starting services ───────────────────────────────${NC}"
echo ""

# ── 5. Build and start ──
echo -e "${WAIT} Building & starting containers (first run may take a few minutes)..."
docker compose up -d --build 2>&1 | tail -5

echo ""

# ── 6. Wait for services ──
echo -e "${WAIT} Waiting for services to be ready..."
sleep 5

# Check backend
RETRIES=0
while ! curl -s http://localhost:8000/api/dashboard/ &>/dev/null; do
    sleep 2
    RETRIES=$((RETRIES + 1))
    if [ $RETRIES -gt 30 ]; then
        echo -e "${YELLOW}[!] Backend is taking longer than expected...${NC}"
        break
    fi
done

# Check frontend
RETRIES=0
while ! curl -s http://localhost:3000/ &>/dev/null; do
    sleep 2
    RETRIES=$((RETRIES + 1))
    if [ $RETRIES -gt 20 ]; then
        echo -e "${YELLOW}[!] Frontend is taking longer than expected...${NC}"
        break
    fi
done

echo ""
echo -e "${CYAN}─── System Status ──────────────────────────────────────${NC}"
echo ""

# Status checks
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
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}🎉 Ziyo Scanner is ready!${NC}"
echo -e "  ${CYAN}Open: ${GREEN}http://localhost:3000${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""

# ── 7. Open browser ──
if [[ "$OSTYPE" == "darwin"* ]]; then
    open "http://localhost:3000"
elif command -v xdg-open &>/dev/null; then
    xdg-open "http://localhost:3000"
fi

echo "Press Ctrl+C or close this window to keep running."
echo "To stop: docker compose down"
echo ""

# Keep terminal open
read -p "Press Enter to stop all services..."
echo ""
echo -e "${WAIT} Stopping services..."
docker compose down
echo -e "${CHECK} All services stopped."
