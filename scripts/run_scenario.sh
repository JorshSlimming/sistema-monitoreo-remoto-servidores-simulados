#!/usr/bin/env bash
# Ejecutar un escenario de prueba completo.
#
# Uso:
#   ./scripts/run_scenario.sh <escenario>
#
# Escenarios disponibles:
#   normal          Nodo normal sin anomalías
#   high-cpu        Anomalía de CPU (reduce_cpu)
#   high-ram        Anomalía de RAM (reduce_ram)
#   high-latency    Latencia alta (fix_latency)
#   service-failure Servicio web en falla (restart_service)
#   failed-event    Evento fallido en log (normalize_node)
#   multi-node      Tres nodos simultáneos
#   all              Todos los escenarios en secuencia
#
set -euo pipefail

cd "$(dirname "$0")/.."

run_scenario() {
    local mode="$1"
    local node_id="${2:-node-01}"
    local interval="${3:-5.0}"

    echo ""
    echo "=============================================="
    echo "  Escenario: $mode  (nodo=$node_id, intervalo=${interval}s)"
    echo "=============================================="

    # Iniciar servidor de fondo
    python3 -m server.tcp_server &
    SERVER_PID=$!
    sleep 0.5

    # Ejecutar cliente
    if [ "$mode" = "fake" ]; then
        python3 tests/fake_client.py --node-id "$node_id" --mode normal
    else
        python3 -m client.tcp_client --node-id "$node_id" --mode "$mode" --interval "$interval" &
        CLIENT_PID=$!
        sleep 5
        kill "$CLIENT_PID" 2>/dev/null || true
    fi

    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    echo "  -> Escenario '$mode' finalizado."
}

case "${1:-normal}" in
    normal)         run_scenario normal node-01 3.0 ;;
    high-cpu)       run_scenario high-cpu node-01 3.0 ;;
    high-ram)       run_scenario high-ram node-01 3.0 ;;
    high-latency)   run_scenario high-latency node-01 3.0 ;;
    service-failure) run_scenario service-failure node-01 3.0 ;;
    failed-event)   run_scenario failed-event node-01 3.0 ;;
    multi-node)
        run_scenario normal node-01 3.0 &
        run_scenario high-cpu node-02 3.0 &
        run_scenario high-latency node-03 3.0 &
        wait
        ;;
    all)
        for mode in normal high-cpu high-ram high-latency service-failure failed-event; do
            run_scenario "$mode" node-01 2.0
        done
        ;;
    *)
        echo "Uso: $0 <escenario>"
        echo "Escenarios: normal, high-cpu, high-ram, high-latency, service-failure, failed-event, multi-node, all"
        exit 1
        ;;
esac
