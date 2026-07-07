#!/usr/bin/env bash
# Generate attack simulation evidence.
#
# Runs all 7 attacks against the local server, saves results as JSON
# artifacts under artifacts/demo/, and updates the evidence index.
#
# Usage: ./scripts/generate_attack_evidence.sh
#
# Environment:
#   ALLOW_NON_LOCAL_ATTACK_TARGET=1  allow non-local target (not recommended)
#
set -euo pipefail

cd "$(dirname "$0")/.."

ARTIFACTS_DIR="artifacts/demo"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$ARTIFACTS_DIR"

echo "============================================"
echo "  Generate Attack Evidence — ${TIMESTAMP}"
echo "============================================"

# Check if server is reachable
if ! python3 -c "
import socket
s = socket.socket()
s.settimeout(0.5)
try:
    s.connect(('127.0.0.1', 5000))
    s.close()
    print('reachable')
except Exception:
    print('unreachable')
" 2>/dev/null | grep -q reachable; then
    echo "WARNING: No server reachable on 127.0.0.1:5000"
    echo "Attack results will be connection failures (expected shape check)."
    SERVER_UP=0
else
    SERVER_UP=1
fi

# Run all attacks
echo ""
echo "--- Running attack simulations ---"
ATTACK_OUTPUT="$ARTIFACTS_DIR/attack_results_${TIMESTAMP}.json"

if [ "$SERVER_UP" = "1" ]; then
    python3 -m attacker.attack_simulator --attack all --json --timeout 3.0 > "$ATTACK_OUTPUT" 2>&1
    ATTACK_EXIT=$?
else
    # Still run attacks against a non-listening port — they'll fail gracefully
    # but exercise the code path for result shape verification
    python3 -m attacker.attack_simulator --attack all --json --timeout 1.0 --port 19999 > "$ATTACK_OUTPUT" 2>&1
    ATTACK_EXIT=$?
fi

echo "Attack exit code: $ATTACK_EXIT"
echo "Output saved to: $ATTACK_OUTPUT"

# Count passed/failed from JSON output
PASSED=$(python3 -c "
import json
with open('$ATTACK_OUTPUT') as f:
    results = json.load(f)
passed = sum(1 for r in results if r.get('success'))
print(passed)
" 2>/dev/null || echo "0")

TOTAL=$(python3 -c "
import json
with open('$ATTACK_OUTPUT') as f:
    results = json.load(f)
print(len(results))
" 2>/dev/null || echo "0")

echo ""
echo "--- Attack results: $PASSED/$TOTAL passed ---"

# Build/update evidence index
EVIDENCE_INDEX="$ARTIFACTS_DIR/evidence_index.json"

if [ -f "$EVIDENCE_INDEX" ]; then
    # Merge with existing index
    python3 -c "
import json
with open('$EVIDENCE_INDEX') as f:
    idx = json.load(f)
if 'attack_results' not in idx.get('artifacts', {}):
    idx.setdefault('artifacts', {})['attack_results'] = '$ATTACK_OUTPUT'
idx.setdefault('results', {})['attack_passed'] = $PASSED
idx.setdefault('results', {})['attack_total'] = $TOTAL
idx.setdefault('results', {})['attack_server_up'] = $SERVER_UP
with open('$EVIDENCE_INDEX', 'w') as f:
    json.dump(idx, f, indent=2)
print('Updated evidence index')
"
else
    # Create new evidence index
    cat > "$EVIDENCE_INDEX" <<JSONEOF
{
  "type": "evidence_index",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "artifacts": {
    "attack_results": "$ATTACK_OUTPUT"
  },
  "results": {
    "attack_passed": $PASSED,
    "attack_total": $TOTAL,
    "attack_server_up": ${SERVER_UP}
  }
}
JSONEOF
fi

echo ""
echo "=== Attack evidence complete ==="
echo "  Results:  $ATTACK_OUTPUT"
echo "  Index:    $EVIDENCE_INDEX"
echo "  Summary:  $PASSED/$TOTAL attack checks passed"
