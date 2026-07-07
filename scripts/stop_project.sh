#!/usr/bin/env bash
set -euo pipefail

echo "=== Deteniendo proyecto ==="

pkill -f "python3 -m server.tcp_server" 2>/dev/null || true
pkill -f "python3 frontend/dashboard_server.py" 2>/dev/null || true

echo "Procesos detenidos (si estaban corriendo)."
