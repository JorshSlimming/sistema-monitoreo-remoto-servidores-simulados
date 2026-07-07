#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PANEL_PORT="${1:-8080}"
PYTHON_BIN="$(command -v python3 || true)"
SERVER_PID=""
PANEL_PID=""
SERVER_TAIL_PID=""
PANEL_TAIL_PID=""
LOG_DIR="logs"
SERVER_LOG="$LOG_DIR/server.log"
PANEL_LOG="$LOG_DIR/panel.log"

mkdir -p "$LOG_DIR"
rm -f "$SERVER_LOG" "$PANEL_LOG"

if [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: python3 no está disponible en PATH."
  exit 127
fi

cleanup() {
  if [ -n "$PANEL_PID" ]; then
    kill "$PANEL_PID" 2>/dev/null || true
    wait "$PANEL_PID" 2>/dev/null || true
  fi
  if [ -n "$SERVER_PID" ]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  if [ -n "$PANEL_TAIL_PID" ]; then
    kill "$PANEL_TAIL_PID" 2>/dev/null || true
    wait "$PANEL_TAIL_PID" 2>/dev/null || true
  fi
  if [ -n "$SERVER_TAIL_PID" ]; then
    kill "$SERVER_TAIL_PID" 2>/dev/null || true
    wait "$SERVER_TAIL_PID" 2>/dev/null || true
  fi
}

pause_if_interactive() {
  if [ -t 0 ]; then
    echo ""
    read -r -p "Presiona Enter para cerrar..." _ || true
  fi
}

wait_for_http() {
  local url="$1"
  local tries="${2:-20}"
  local i
  for i in $(seq 1 "$tries"); do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

trap cleanup EXIT INT TERM

echo "=== Levantando proyecto ==="
echo "  Servidor TCP: 127.0.0.1:5000"
echo "  Panel:        http://127.0.0.1:${PANEL_PORT}"
echo "  API panel:    http://127.0.0.1:${PANEL_PORT}/api/status"
echo "  Logs:         $SERVER_LOG | $PANEL_LOG"
echo "  Python:       $PYTHON_BIN"
echo ""

# limpiar restos de ejecuciones anteriores para no chocar con puertos
pkill -f "python3 -m server.tcp_server" 2>/dev/null || true
pkill -f "python3 -m frontend.dashboard_server" 2>/dev/null || true
pkill -f "python3 frontend/dashboard_server.py" 2>/dev/null || true
sleep 0.5

PYTHONUNBUFFERED=1 "$PYTHON_BIN" -m server.tcp_server >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

DASHBOARD_PORT="$PANEL_PORT" PYTHONUNBUFFERED=1 "$PYTHON_BIN" frontend/dashboard_server.py >"$PANEL_LOG" 2>&1 &
PANEL_PID=$!

tail -n +1 -f "$SERVER_LOG" | sed -u 's/^/[tcp-server] /' &
SERVER_TAIL_PID=$!

tail -n +1 -f "$PANEL_LOG" | sed -u 's/^/[panel] /' &
PANEL_TAIL_PID=$!

echo "PIDs: server=$SERVER_PID panel=$PANEL_PID"
echo "Ctrl+C para detener ambos."
echo ""

if ! wait_for_http "http://127.0.0.1:${PANEL_PORT}/api/status" 20; then
  echo "ERROR: el panel no logró iniciar."
  echo "--- Últimas líneas de $SERVER_LOG ---"
  tail -n 20 "$SERVER_LOG" 2>/dev/null || true
  echo "--- Últimas líneas de $PANEL_LOG ---"
  tail -n 20 "$PANEL_LOG" 2>/dev/null || true
  pause_if_interactive
  exit 1
fi

echo "Proyecto activo."
echo ""

wait -n "$SERVER_PID" "$PANEL_PID"

echo ""
echo "Uno de los procesos terminó. Apagando el resto..."
echo "--- Últimas líneas de $SERVER_LOG ---"
tail -n 20 "$SERVER_LOG" 2>/dev/null || true
echo "--- Últimas líneas de $PANEL_LOG ---"
tail -n 20 "$PANEL_LOG" 2>/dev/null || true
pause_if_interactive
