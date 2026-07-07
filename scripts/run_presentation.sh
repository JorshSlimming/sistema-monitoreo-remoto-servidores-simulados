#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PANEL_PORT="${1:-8080}"
PROFILE="${2:-trio}"
PYTHON_BIN="$(command -v python3 || true)"
LOG_DIR="logs"
SERVER_LOG="$LOG_DIR/server.log"
PANEL_LOG="$LOG_DIR/panel.log"

mkdir -p "$LOG_DIR"
rm -f "$SERVER_LOG" "$PANEL_LOG"

if [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: python3 no está disponible en PATH."
  exit 127
fi

SERVER_PID=""
PANEL_PID=""
CLIENT_PIDS=""

cleanup() {
  for pid in $CLIENT_PIDS; do
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
  if [ -n "$PANEL_PID" ]; then
    kill "$PANEL_PID" 2>/dev/null || true
    wait "$PANEL_PID" 2>/dev/null || true
  fi
  if [ -n "$SERVER_PID" ]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
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

start_client() {
  local mode="$1"
  local node_id="$2"
  local interval="$3"
  PYTHONUNBUFFERED=1 "$PYTHON_BIN" -m client.tcp_client --node-id "$node_id" --mode "$mode" --interval "$interval" &
  CLIENT_PIDS="$CLIENT_PIDS $!"
}

trap cleanup EXIT INT TERM

pkill -f "python3 -m server.tcp_server" 2>/dev/null || true
pkill -f "python3 -m frontend.dashboard_server" 2>/dev/null || true
pkill -f "python3 frontend/dashboard_server.py" 2>/dev/null || true
sleep 0.5

echo "=== Modo presentación ==="
echo "  Perfil:      $PROFILE"
echo "  Servidor:    127.0.0.1:5000"
echo "  Dashboard:   http://127.0.0.1:${PANEL_PORT}"
echo "  API estado:  http://127.0.0.1:${PANEL_PORT}/api/state"
echo "  Ctrl+C para detener todo"
echo ""

PYTHONUNBUFFERED=1 "$PYTHON_BIN" -m server.tcp_server >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

DASHBOARD_PORT="$PANEL_PORT" PYTHONUNBUFFERED=1 "$PYTHON_BIN" frontend/dashboard_server.py >"$PANEL_LOG" 2>&1 &
PANEL_PID=$!

if ! wait_for_http "http://127.0.0.1:${PANEL_PORT}/api/state" 20; then
  echo "ERROR: el dashboard no inició."
  exit 1
fi

case "$PROFILE" in
  trio)
    start_client normal node-01 3.0
    start_client high-cpu node-02 3.0
    start_client high-latency node-03 4.0
    ;;
  cpu)
    start_client high-cpu node-01 3.0
    ;;
  ram)
    start_client high-ram node-01 3.0
    ;;
  latency)
    start_client high-latency node-01 3.0
    ;;
  service)
    start_client service-failure node-01 3.0
    ;;
  failed-event)
    start_client failed-event node-01 3.0
    ;;
  normal)
    start_client normal node-01 3.0
    ;;
  *)
    echo "ERROR: perfil desconocido: $PROFILE"
    echo "Perfiles: trio, cpu, ram, latency, service, failed-event, normal"
    exit 1
    ;;
esac

echo "Procesos activos:"
echo "  server=$SERVER_PID"
echo "  panel=$PANEL_PID"
echo "  clients=${CLIENT_PIDS# }"
echo ""
echo "Sugerencia: abre el dashboard y usa los botones de evidencia cuando quieras capturas."
echo ""

wait -n "$SERVER_PID" "$PANEL_PID" $CLIENT_PIDS

echo "Uno de los procesos terminó. Apagando el resto..."
