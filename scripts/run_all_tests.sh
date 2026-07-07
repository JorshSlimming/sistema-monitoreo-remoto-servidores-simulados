#!/usr/bin/env bash
# Ejecutar todas las pruebas del sistema.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== Sistema de Monitoreo Remoto - Pruebas ==="
echo ""

python3 -m unittest discover -s tests -v 2>&1
