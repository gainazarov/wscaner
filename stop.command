#!/bin/bash
# Ziyo Scanner — Stop all services
cd "$(dirname "$0")"
echo "🛑 Stopping Ziyo Scanner..."
docker compose down
echo "✅ All services stopped."
