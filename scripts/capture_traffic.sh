#!/usr/bin/env bash
# Iniciar captura de tráfico con tshark para el sistema de monitoreo.
#
# Uso:
#   sudo ./scripts/capture_traffic.sh [archivo_salida.pcapng]
#
# Requiere: tshark (parte de Wireshark)
#
# El archivo se guarda en captures/ por defecto.
set -euo pipefail

OUTPUT="${1:-captures/monitoreo_$(date +%Y%m%d_%H%M%S).pcapng}"
mkdir -p "$(dirname "$OUTPUT")"

if ! command -v tshark &>/dev/null; then
    echo "ERROR: tshark no está instalado. Instalar Wireshark/tshark primero."
    exit 1
fi

echo "=== Captura de tráfico ==="
echo "  Puerto:    5000"
echo "  Interfaz:  lo (loopback)"
echo "  Archivo:   $OUTPUT"
echo ""
echo "Instrucciones:"
echo "  1. En otra terminal, iniciar el servidor:  python3 -m server.tcp_server"
echo "  2. En otra terminal, iniciar el cliente:   python3 -m client.tcp_client --node-id node-01 --mode high-cpu"
echo "  3. Presiona Ctrl+C aquí para detener la captura."
echo ""

sudo tshark -i lo -f "tcp port 5000" -w "$OUTPUT"

echo ""
echo "Captura guardada en: $OUTPUT"
echo "Ver con: tshark -r $OUTPUT -Y 'tcp.port == 5000'"
echo "O abrir en Wireshark."
