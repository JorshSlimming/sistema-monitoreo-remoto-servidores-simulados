#!/usr/bin/env bash
# Full demo artifact generation pipeline.
#
# Runs: reset → scenarios → nmap → tshark → db summary
# Saves results under artifacts/demo/ (via the dashboard server if running,
# otherwise directly).
set -euo pipefail

cd "$(dirname "$0")/.."

ARTIFACTS_DIR="artifacts/demo"
SUMMARY_FILE="$ARTIFACTS_DIR/summary_$(date +%Y%m%d_%H%M%S).json"
mkdir -p "$ARTIFACTS_DIR" "captures"

echo "============================================"
echo "  Generate Demo Artifacts"
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

# 3. DB row counts
echo ""
echo "--- Step 3: DB Stats ---"
DB_STATS=$(python3 -c "
import sqlite3
try:
    db = sqlite3.connect('data/monitor.db')
    stats = {}
    for table in ['metrics','commands','acks']:
        count = db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        stats[table] = count
    db.close()
    print(stats)
except Exception:
    print({'metrics': 0, 'commands': 0, 'acks': 0})
")
echo "  $DB_STATS"

# 4. Nmap (source toolenv)
echo ""
echo "--- Step 4: Nmap localhost scan ---"
NMAP_OUTPUT=$(source ~/.local/bin/toolenv 2>/dev/null && nmap -p 5000 -T4 127.0.0.1 2>&1 || echo "nmap unavailable")
echo "$NMAP_OUTPUT"

# 5. TShark (may be blocked — capture error gracefully)
echo ""
echo "--- Step 5: TShark capture (5s) ---"
TSHARK_FILE="captures/tshark_$(date +%Y%m%d_%H%M%S).pcapng"
TSHARK_RESULT="ok"
TSHARK_ERROR=""
source ~/.local/bin/toolenv 2>/dev/null || true
if command -v tshark &>/dev/null; then
    tshark -i lo -f "tcp port 5000" -a duration:5 -w "$TSHARK_FILE" 2>&1 || {
        TSHARK_RESULT="blocked"
        TSHARK_ERROR="dumpcap/tshark lacks permission to capture on loopback"
        echo "  WARNING: $TSHARK_ERROR"
    }
else
    TSHARK_RESULT="unavailable"
    TSHARK_ERROR="tshark not installed"
    echo "  WARNING: $TSHARK_ERROR"
fi

# 6. Write summary JSON
echo ""
echo "--- Step 6: Summary ---"
cat > "$SUMMARY_FILE" <<JSONEOF
{
  "type": "full_demo_summary",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "label": "Full demo artifact generation",
  "details": {
    "db_stats": $DB_STATS,
    "nmap": $(echo "$NMAP_OUTPUT" | head -c 2000 | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))"),
    "tshark_result": "$TSHARK_RESULT",
    "tshark_error": "$TSHARK_ERROR",
    "tshark_file": "$TSHARK_FILE"
  }
}
JSONEOF

echo ""
echo "Summary written to: $SUMMARY_FILE"
echo "============================================"
echo "  Done — artifacts in $ARTIFACTS_DIR/"
echo "============================================"
