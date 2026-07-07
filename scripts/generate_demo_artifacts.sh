#!/usr/bin/env bash
# Full demo artifact generation pipeline.
#
# Runs: reset → scenarios → db dump → nmap → tshark → tests → evidence index
# Saves results under artifacts/demo/
#
# Usage: ./scripts/generate_demo_artifacts.sh
#
# Environment:
#   SKIP_TESTS=1   skip test suite run (useful when server is already busy)
#   SKIP_TSHARK=1  skip tshark capture
#   SKIP_NMAP=1    skip nmap scan
#
set -euo pipefail

cd "$(dirname "$0")/.."

ARTIFACTS_DIR="artifacts/demo"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SUMMARY_FILE="$ARTIFACTS_DIR/summary_${TIMESTAMP}.json"
DEMO_LOG="$ARTIFACTS_DIR/demo_${TIMESTAMP}.log"
STATE_SNAPSHOT="$ARTIFACTS_DIR/state_snapshot_${TIMESTAMP}.json"
METRICS_SAMPLE="$ARTIFACTS_DIR/metrics_sample.jsonl"
COMMANDS_SAMPLE="$ARTIFACTS_DIR/commands_sample.jsonl"
ACKS_SAMPLE="$ARTIFACTS_DIR/acks_sample.jsonl"
NMAP_OUTPUT="$ARTIFACTS_DIR/nmap_output.txt"
TSHARK_FILE="$ARTIFACTS_DIR/tshark_capture_${TIMESTAMP}.pcapng"
TEST_OUTPUT="$ARTIFACTS_DIR/test_output.log"
EVIDENCE_INDEX="$ARTIFACTS_DIR/evidence_index.json"
DASHBOARD_STARTED_HERE=0
DASHBOARD_PID=""

mkdir -p "$ARTIFACTS_DIR" "captures"

exec > >(tee -a "$DEMO_LOG") 2>&1

cleanup() {
  if [ "$DASHBOARD_STARTED_HERE" = "1" ] && [ -n "$DASHBOARD_PID" ]; then
    kill "$DASHBOARD_PID" 2>/dev/null || true
    wait "$DASHBOARD_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

if python3 - <<'PY'
import socket
s = socket.socket()
s.settimeout(0.2)
busy = s.connect_ex(("127.0.0.1", 5000)) == 0
s.close()
raise SystemExit(0 if busy else 1)
PY
then
  echo "ERROR: el puerto TCP 5000 ya está en uso."
  echo "Detén el servidor activo antes de ejecutar make evidence, o usa la demo interactiva por separado."
  exit 1
fi

echo "============================================"
echo "  Generate Demo Artifacts — ${TIMESTAMP}"
echo "============================================"

# 1. Reset environment
echo ""
echo "--- Step 1: Reset ---"
bash scripts/reset_environment.sh

# 2. Run selected scenarios
echo ""
echo "--- Step 2: Scenarios ---"
for scenario in normal high-cpu high-ram; do
    echo "  Scenario: $scenario"
    bash scripts/run_scenario.sh "$scenario"
done

# 3. DB row counts + dump samples
echo ""
echo "--- Step 3: DB Stats and Samples ---"
python3 -c "
import sqlite3, json
try:
    db = sqlite3.connect('data/monitor.db')
    db.row_factory = sqlite3.Row

    # Stats
    for table in ['metrics','commands','acks']:
        count = db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        print(f'  {table}: {count} rows')

    # Dump samples as JSONL
    def dump_jsonl(table, path, limit=50):
        rows = db.execute(f'SELECT * FROM {table} ORDER BY rowid DESC LIMIT {limit}').fetchall()
        with open(path, 'w') as f:
            for r in reversed(rows):
                f.write(json.dumps(dict(r), default=str) + '\n')
        print(f'  Wrote {len(rows)} rows to {path}')

    dump_jsonl('metrics', '$METRICS_SAMPLE')
    dump_jsonl('commands', '$COMMANDS_SAMPLE')
    dump_jsonl('acks', '$ACKS_SAMPLE')

    db.close()
except Exception as e:
    print(f'  DB error: {e}')
"

# 4. State snapshot via /api/state (if dashboard is running)
echo ""
echo "--- Step 4: State snapshot ---"
if ! curl -sf http://localhost:8080/api/state >/dev/null 2>&1; then
    DASHBOARD_PORT=8080 python3 frontend/dashboard_server.py >/dev/null 2>&1 &
    DASHBOARD_PID=$!
    DASHBOARD_STARTED_HERE=1
    sleep 1
fi
if curl -sf http://localhost:8080/api/state > "$STATE_SNAPSHOT" 2>/dev/null; then
    echo "  /api/state snapshot saved to $STATE_SNAPSHOT"
else
    echo "  WARNING: no se pudo obtener /api/state"
    echo '{"error":"dashboard_unavailable","hint":"frontend/dashboard_server.py could not provide /api/state"}' > "$STATE_SNAPSHOT"
fi

# 5. Nmap localhost scan
echo ""
echo "--- Step 5: Nmap localhost scan ---"
NMAP_STATUS="unavailable"
if [ "${SKIP_NMAP:-0}" != "1" ]; then
    if command -v nmap &>/dev/null; then
        nmap -p 5000 -T4 127.0.0.1 2>&1 | tee "$NMAP_OUTPUT" && NMAP_STATUS="ok" || NMAP_STATUS="error"
    else
        echo "  WARNING: nmap not installed"
        echo "nmap not installed — install with: sudo apt install nmap" > "$NMAP_OUTPUT"
    fi
else
    echo "  SKIP_NMAP set, skipping"
    echo "nmap scan skipped (SKIP_NMAP=1)" > "$NMAP_OUTPUT"
fi

# 6. TShark capture (may be blocked — capture error gracefully)
echo ""
echo "--- Step 6: TShark capture (5s) ---"
TSHARK_STATUS="unavailable"
TSHARK_ERROR=""
if [ "${SKIP_TSHARK:-0}" != "1" ]; then
    if command -v tshark &>/dev/null; then
        if tshark -i lo -f "tcp port 5000" -a duration:5 -w "$TSHARK_FILE" 2>/dev/null; then
            TSHARK_STATUS="ok"
            TSHARK_SIZE=$(stat -c%s "$TSHARK_FILE" 2>/dev/null || echo 0)
            echo "  Capture saved: $TSHARK_FILE ($TSHARK_SIZE bytes)"
        else
            TSHARK_STATUS="blocked"
            TSHARK_ERROR="dumpcap/tshark lacks permission to capture on loopback"
            echo "  WARNING: $TSHARK_ERROR"
            echo "$TSHARK_ERROR" > "${ARTIFACTS_DIR}/tshark_result_blocked.txt"
            echo "  To fix: run with sudo or add user to wireshark group"
            echo "  See docs/evidence/README.md for details"
        fi
    else
        echo "  WARNING: tshark not installed"
        echo "tshark not installed" > "${ARTIFACTS_DIR}/tshark_result_unavailable.txt"
    fi
else
    echo "  SKIP_TSHARK set, skipping"
fi

# 7. Run test suite
echo ""
echo "--- Step 7: Test suite ---"
TEST_STATUS="skipped"
if [ "${SKIP_TESTS:-0}" != "1" ]; then
    echo "  Running: python3 -m unittest discover -s tests -v"
    if python3 -m unittest discover -s tests -v 2>&1 | tee "$TEST_OUTPUT"; then
        TEST_STATUS="passed"
    else
        TEST_STATUS="failed"
    fi
else
    echo "  SKIP_TESTS set, skipping"
    echo "Tests skipped (SKIP_TESTS=1)" > "$TEST_OUTPUT"
fi

# 8. Database stats for summary
DB_STATS=$(python3 -c "
import sqlite3
try:
    db = sqlite3.connect('data/monitor.db')
    stats = {}
    for table in ['metrics','commands','acks']:
        count = db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        stats[table] = count
    db.close()
    print(__import__('json').dumps(stats))
except Exception:
    print('{\"metrics\": 0, \"commands\": 0, \"acks\": 0}')
")

# 9. Build evidence index
echo ""
echo "--- Step 8: Evidence index ---"

cat > "$EVIDENCE_INDEX" <<JSONEOF
{
  "type": "evidence_index",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "artifacts": {
    "summary": "$SUMMARY_FILE",
    "demo_log": "$DEMO_LOG",
    "state_snapshot": "$STATE_SNAPSHOT",
    "metrics_sample": "$METRICS_SAMPLE",
    "commands_sample": "$COMMANDS_SAMPLE",
    "acks_sample": "$ACKS_SAMPLE",
    "nmap_output": "$NMAP_OUTPUT",
    "tshark_capture": "$TSHARK_FILE",
    "test_output": "$TEST_OUTPUT"
  },
  "results": {
    "nmap_status": "$NMAP_STATUS",
    "tshark_status": "$TSHARK_STATUS",
    "tshark_error": "$TSHARK_ERROR",
    "test_status": "$TEST_STATUS",
    "db_stats": $DB_STATS,
    "tshark_file_size_bytes": ${TSHARK_SIZE:-0}
  }
}
JSONEOF

# 10. Legacy summary for compatibility
cat > "$SUMMARY_FILE" <<JSONEOF
{
  "type": "full_demo_summary",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "label": "Full demo artifact generation",
  "details": {
    "db_stats": $DB_STATS,
    "test_status": "$TEST_STATUS",
    "nmap_status": "$NMAP_STATUS",
    "tshark_status": "$TSHARK_STATUS",
    "tshark_error": "$TSHARK_ERROR",
    "artifacts_dir": "$ARTIFACTS_DIR"
  }
}
JSONEOF

echo ""
echo "============================================"
echo "  Done — artifacts in $ARTIFACTS_DIR/"
echo "  Evidence index: $EVIDENCE_INDEX"
echo "  Summary: $SUMMARY_FILE"
echo "============================================"
