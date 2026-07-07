#!/usr/bin/env bash
# Run the persistent TCP client.
# Usage: ./scripts/run_client.sh [mode] [node-id] [interval]
MODE="${1:-normal}"
NODE_ID="${2:-node-01}"
INTERVAL="${3:-5.0}"
python3 -m client.tcp_client --node-id "$NODE_ID" --mode "$MODE" --interval "$INTERVAL"
