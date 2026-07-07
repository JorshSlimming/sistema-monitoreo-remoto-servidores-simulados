#!/usr/bin/env bash
# Reiniciar el entorno: borrar base de datos, __pycache__ y archivos temporales.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== Limpiando entorno ==="

# Base de datos
if [ -f data/monitor.db ]; then
    rm -f data/monitor.db data/monitor.db-wal data/monitor.db-shm
    echo "  - data/monitor.db eliminado"
fi

# Directorio de capturas
if [ -d captures ]; then
    rm -rf captures/
    echo "  - captures/ eliminado"
fi

# Bytecode
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
echo "  - __pycache__ eliminado"

# Archivos .pyc sueltos
find . -name "*.pyc" -delete 2>/dev/null || true
echo "  - .pyc eliminados"

echo ""
echo "Entorno limpio. Listo para empezar."
