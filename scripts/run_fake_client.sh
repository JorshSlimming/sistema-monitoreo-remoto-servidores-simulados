#!/usr/bin/env bash
MODE="${1:-normal}"
NODE_ID="${2:-node-01}"
python tests/fake_client.py --node-id "$NODE_ID" --mode "$MODE"

