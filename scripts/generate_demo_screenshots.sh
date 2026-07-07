#!/usr/bin/env bash
# Generate screenshots of the dashboard using Playwright.
#
# Starts the dashboard server if it isn't already running, takes
# screenshots via the ``playwright`` CLI, and saves them under
# artifacts/screenshots/.
set -euo pipefail

cd "$(dirname "$0")/.."

SCREENSHOTS_DIR="artifacts/screenshots"
mkdir -p "$SCREENSHOTS_DIR"

render_fallback_pngs() {
python3 - <<'PY'
import json
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path('.').resolve()
shots = root / 'artifacts' / 'screenshots'
shots.mkdir(parents=True, exist_ok=True)
demo = root / 'artifacts' / 'demo'
artifacts = []
for path in sorted(demo.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
    try:
        artifacts.append(json.loads(path.read_text()))
    except Exception:
        pass

def make_image(title: str, lines: list[str], out: Path) -> None:
    img = Image.new('RGB', (1600, 1000), '#f4f6fa')
    draw = ImageDraw.Draw(img)
    title_font = ImageFont.load_default()
    body_font = ImageFont.load_default()
    draw.rounded_rectangle((40, 40, 1560, 960), radius=24, fill='#ffffff', outline='#e2e8f0', width=2)
    draw.text((80, 80), title, fill='#0f172a', font=title_font)
    y = 140
    for line in lines[:28]:
        draw.text((80, y), line, fill='#475569', font=body_font)
        y += 28
    img.save(out)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
summary_lines = [
    'Panel local · evidencia generada',
    f'Proyecto: sistema de monitoreo remoto',
    f'Artefactos: {len(artifacts)}',
    '',
]
for item in artifacts[:10]:
    details = item.get('details', {})
    state = details.get('status') or ('success' if details.get('success', True) else 'error')
    summary_lines.append(f"- {item.get('type','?')} · {state} · {item.get('timestamp','')}")

files_lines = ['Snapshot local · últimos artefactos', '']
for item in artifacts[:12]:
    files_lines.append(f"[{item.get('type','?')}] {item.get('label','')}")
    details = item.get('details', {})
    for key in ('path', 'output'):
        value = details.get(key)
        if value:
            files_lines.append(f"    {key}: {value}")
    for key in ('files', 'screenshots'):
        values = details.get(key)
        if isinstance(values, list):
            for value in values[:3]:
                files_lines.append(f"    file: {value}")

make_image('Dashboard demo summary', summary_lines, shots / f'dashboard_{timestamp}.png')
make_image('Snapshot demo summary', files_lines, shots / f'snapshot_{timestamp}.png')
print('fallback-render: ok')
PY
}

echo "=== Generate Demo Screenshots ==="

# Start dashboard if not already running
DASHBOARD_PID=""
cleanup() {
    if [ -n "$DASHBOARD_PID" ]; then
        kill "$DASHBOARD_PID" 2>/dev/null || true
        wait "$DASHBOARD_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

if ! curl -sf http://127.0.0.1:8080/api/status >/dev/null 2>&1; then
    echo "Starting dashboard server on :8080 …"
    python3 frontend/dashboard_server.py &
    DASHBOARD_PID=$!
    sleep 1
fi

echo "Dashboard is up. Taking screenshots …"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# prepare snapshot with fresh evidence
curl -sf -X POST http://127.0.0.1:8080/api/demo-bundle >/dev/null || true
curl -sf -X POST http://127.0.0.1:8080/api/nmap >/dev/null || true
curl -sf -X POST http://127.0.0.1:8080/api/tshark-capture >/dev/null || true
sleep 1

# ponytail: playwright screenshot CLI — simplest available path
if command -v playwright &>/dev/null; then
    if playwright screenshot \
        --full-page \
        "http://127.0.0.1:8080/" \
        "$SCREENSHOTS_DIR/dashboard_${TIMESTAMP}.png" \
        2>&1; then
      :
    else
      echo "WARNING: playwright screenshot failed; using Pillow fallback"
      render_fallback_pngs
      exit 0
    fi
    if playwright screenshot \
        --full-page \
        "http://127.0.0.1:8080/snapshot.html" \
        "$SCREENSHOTS_DIR/snapshot_${TIMESTAMP}.png" \
        2>&1; then
      :
    else
      echo "WARNING: playwright snapshot screenshot failed; using Pillow fallback"
      render_fallback_pngs
      exit 0
    fi
    echo "  → $SCREENSHOTS_DIR/dashboard_${TIMESTAMP}.png"
    echo "  → $SCREENSHOTS_DIR/snapshot_${TIMESTAMP}.png"
else
    echo "WARNING: 'playwright' CLI not usable — using Pillow fallback"
    render_fallback_pngs
fi

echo ""
echo "=== Screenshots saved to $SCREENSHOTS_DIR/ ==="
