#!/usr/bin/env bash
# Start the local dashboard server.
# Usage: ./scripts/run_frontend.sh [port]
set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${1:-8080}"
export DASHBOARD_PORT="$PORT"

echo "=== Starting Dashboard Server ==="
echo "  Port:    $PORT"
echo "  URL:     http://127.0.0.1:$PORT"
echo "  API:     http://127.0.0.1:$PORT/api/status"
echo ""

python3 frontend/dashboard_server.py
