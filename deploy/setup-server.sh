#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# WScaner — Production Deployment Script
# Run on a fresh Ubuntu 22.04 / 24.04 server
# ═══════════════════════════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════════════════════"
echo "  WScaner — Production Setup"
echo "═══════════════════════════════════════════════════════════"

# ─── 1. System update ────────────────────────────────────────────────────────
echo "[1/7] Updating system..."
apt update && apt upgrade -y

# ─── 2. Install Docker ──────────────────────────────────────────────────────
echo "[2/7] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
else
    echo "  Docker already installed."
fi

# ─── 3. Install Docker Compose plugin ────────────────────────────────────────
echo "[3/7] Installing Docker Compose..."
if ! docker compose version &> /dev/null; then
    apt install -y docker-compose-plugin
else
    echo "  Docker Compose already installed."
fi

# ─── 4. Install Nginx ───────────────────────────────────────────────────────
echo "[4/7] Installing Nginx..."
apt install -y nginx
systemctl enable nginx

# ─── 5. Setup swap (2 GB) ───────────────────────────────────────────────────
echo "[5/7] Setting up swap..."
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "  2 GB swap created."
else
    echo "  Swap already exists."
fi

# ─── 6. Setup firewall ──────────────────────────────────────────────────────
echo "[6/7] Configuring firewall..."
apt install -y ufw
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 6080/tcp  # noVNC (recorder)
ufw --force enable

# ─── 7. Clone project ───────────────────────────────────────────────────────
echo "[7/7] Setting up project..."
PROJECT_DIR="/opt/scaner"
if [ ! -d "$PROJECT_DIR" ]; then
    echo "  Please clone your project to $PROJECT_DIR"
    echo "  Example: git clone <your-repo-url> $PROJECT_DIR"
else
    echo "  Project directory exists."
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  System setup complete!"
echo "  Next steps:"
echo "  1. Clone project to /opt/scaner"
echo "  2. Copy .env.production to .env"
echo "  3. Edit .env with real SECRET_KEY"
echo "  4. Copy nginx config"
echo "  5. Run: docker compose up -d --build"
echo "═══════════════════════════════════════════════════════════"
