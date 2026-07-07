#!/usr/bin/env python3
"""Read-only viewer dashboard for the remote monitoring system.

Serves the designer's static frontend from ``frontend/static/`` and
provides read-first JSON API endpoints for charts, logs, and session
state.  Action-oriented POST endpoints are preserved for the bundled
scripts but are *not* the primary UI contract.

Stdlib-only — no external dependencies.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Paths — relative to project root (two levels up from this file)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ARTIFACTS_DIR = _PROJECT_ROOT / "artifacts"
_DEMO_DIR = _ARTIFACTS_DIR / "demo"
_STATIC_DIR = _PROJECT_ROOT / "frontend" / "static"
_DB_PATH = _PROJECT_ROOT / "data" / "monitor.db"
_CAPTURES_DIR = _PROJECT_ROOT / "captures"
_SCREENSHOTS_DIR = _ARTIFACTS_DIR / "screenshots"

# Ensure output dirs exist
for _d in (_ARTIFACTS_DIR, _DEMO_DIR, _STATIC_DIR, _CAPTURES_DIR, _SCREENSHOTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

_DASHBOARD_START = time.time()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    """ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _ts() -> str:
    """Compact local timestamp for filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _db_stats() -> dict:
    """Row counts from the SQLite database (or error dict)."""
    if not _DB_PATH.exists():
        return {"metrics": 0, "commands": 0, "acks": 0}
    try:
        conn = sqlite3.connect(str(_DB_PATH), timeout=2)
        metrics = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
        commands = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
        acks = conn.execute("SELECT COUNT(*) FROM acks").fetchone()[0]
        conn.close()
        return {"metrics": metrics, "commands": commands, "acks": acks}
    except (sqlite3.Error, FileNotFoundError) as exc:
        return {"metrics": -1, "commands": -1, "acks": -1, "error": str(exc)}


def _run_cmd(
    cmd: list[str],
    timeout: int = 30,
    cwd: str | None = None,
) -> dict:
    """Run *cmd* as a subprocess and return result dict."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or str(_PROJECT_ROOT),
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "timeout", "success": False}
    except FileNotFoundError as exc:
        return {"returncode": -1, "stdout": "", "stderr": f"command not found: {exc}", "success": False}


def _run_with_toolenv(cmd: list[str], timeout: int = 30) -> dict:
    """Run a command inside ``bash -c`` that sources ``~/.local/bin/toolenv`` first."""
    joined = " ".join(cmd)
    return _run_cmd(
        ["bash", "-c", f"source ~/.local/bin/toolenv 2>/dev/null; {joined}"],
        timeout=timeout,
    )


def _start_monitor_server() -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "server.tcp_server"],
        cwd=str(_PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _stop_process(proc: subprocess.Popen[str] | None) -> None:
    if proc is None:
        return
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _save_artifact(artifact_type: str, label: str, details: dict) -> dict:
    """Write a machine-readable JSON artifact and return its metadata."""
    filename = f"{artifact_type}_{_ts()}.json"
    path = _DEMO_DIR / filename
    artifact: dict = {
        "type": artifact_type,
        "timestamp": _now(),
        "label": label,
        "details": details,
    }
    path.write_text(json.dumps(artifact, indent=2, default=str))
    return {
        "filename": filename,
        "path": str(path.relative_to(_PROJECT_ROOT)),
        **artifact,
    }


def _list_artifacts() -> list[dict]:
    """Return all artifacts newest-first."""
    items: list[dict] = []
    if not _DEMO_DIR.exists():
        return items
    for fpath in sorted(_DEMO_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if fpath.suffix == ".json":
            try:
                items.append(json.loads(fpath.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
    return items


def _latest_artifact(prefix: str) -> dict | None:
    for item in _list_artifacts():
        if str(item.get("type", "")).startswith(prefix):
            return item
    return None


def _artifact_paths(artifact: dict | None) -> list[str]:
    if not artifact:
        return []
    details = artifact.get("details", {}) if isinstance(artifact, dict) else {}
    paths: list[str] = []
    for key in ("screenshots", "files", "paths"):
        value = details.get(key)
        if isinstance(value, list):
            paths.extend(str(v) for v in value)
    for key in ("output", "path"):
        value = details.get(key)
        if isinstance(value, str) and value:
            paths.append(value)
    return paths


def _build_status_payload() -> dict:
    tests = _latest_artifact("tests")
    nmap = _latest_artifact("nmap")
    tshark = _latest_artifact("tshark") or _latest_artifact("tshark_blocked") or _latest_artifact("tshark_error")
    shots = _latest_artifact("screenshots")
    bundle = _latest_artifact("demo_bundle")

    db_stats = _db_stats()
    total_records = sum(v for v in db_stats.values() if isinstance(v, int) and v >= 0)

    tests_summary: dict[str, object] = {}
    if tests:
        details = tests.get("details", {})
        stdout = str(details.get("stdout", ""))
        total = stdout.count("... ok") + stdout.count("... FAIL") + stdout.count("... ERROR")
        failed = stdout.count("... FAIL") + stdout.count("... ERROR")
        tests_summary = {
            "passed": max(total - failed, 0),
            "failed": failed,
            "total": total,
            "timestamp": tests.get("timestamp"),
        }

    evidence_total = len([x for x in (tests, nmap, tshark, shots, bundle) if x])
    evidence_last = next((x.get("timestamp") for x in (shots, tshark, nmap, bundle, tests) if x), None)

    return {
        "status": "ok",
        "server": {
            "host": "127.0.0.1",
            "port": int(os.environ.get("DASHBOARD_PORT", 8080)),
            "running": True,
        },
        "database": {
            "path": str(_DB_PATH.relative_to(_PROJECT_ROOT)),
            "records": total_records,
        },
        "db_stats": db_stats,
        "tests": tests_summary,
        "evidence": {
            "total": evidence_total,
            "timestamp": evidence_last,
        },
        "artifact_count": len(_list_artifacts()),
    }


def _build_artifacts_payload() -> dict:
    artifacts = _list_artifacts()
    tests = _latest_artifact("tests")
    nmap = _latest_artifact("nmap")
    tshark = _latest_artifact("tshark") or _latest_artifact("tshark_blocked") or _latest_artifact("tshark_error")
    shots = _latest_artifact("screenshots")
    bundle = _latest_artifact("demo_bundle")

    def artifact_state(artifact: dict | None) -> str | None:
        if not artifact:
            return None
        details = artifact.get("details", {})
        if artifact.get("type") == "tshark_blocked":
            return "blocked"
        return "success" if details.get("success", True) else "error"

    return {
        "generated_at": _now(),
        "project": "Sistema de monitoreo remoto",
        "server": {
            "host": "127.0.0.1",
            "port": 8080,
            "running": True,
        },
        "tests": {
            "timestamp": tests.get("timestamp") if tests else None,
            "passed": _build_status_payload().get("tests", {}).get("passed", 0),
            "failed": _build_status_payload().get("tests", {}).get("failed", 0),
            "total": _build_status_payload().get("tests", {}).get("total", 0),
        },
        "nmap": {
            "timestamp": nmap.get("timestamp") if nmap else None,
            "state": artifact_state(nmap),
            "path": _artifact_paths(nmap)[0] if _artifact_paths(nmap) else None,
        },
        "tshark": {
            "timestamp": tshark.get("timestamp") if tshark else None,
            "state": artifact_state(tshark),
            "blocked": artifact_state(tshark) == "blocked",
            "path": _artifact_paths(tshark)[0] if _artifact_paths(tshark) else None,
        },
        "screenshots": {
            "timestamp": shots.get("timestamp") if shots else None,
            "files": _artifact_paths(shots),
        },
        "bundle": {
            "timestamp": bundle.get("timestamp") if bundle else None,
            "files": _artifact_paths(bundle),
        },
        "artifacts": artifacts,
    }


def _fetch_metrics(limit: int = 200, nodes: tuple[str, ...] | None = None) -> list[dict]:
    """Return recent metrics from SQLite, newest first.

    Each row is a flat dict ready for charting.
    """
    if not _DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(_DB_PATH), timeout=2)
        query = "SELECT node_id, seq, cpu, ram, latency_ms, service_web, event_log, received_at FROM metrics"
        params: list[str] = []
        if nodes:
            placeholders = ",".join("?" for _ in nodes)
            query += f" WHERE node_id IN ({placeholders})"
            params.extend(nodes)
        query += " ORDER BY received_at DESC LIMIT ?"
        params.append(str(limit))
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [
            {
                "node_id": row[0],
                "seq": row[1],
                "cpu": row[2],
                "ram": row[3],
                "latency_ms": row[4],
                "service_web": row[5],
                "event_log": row[6],
                "received_at": row[7],
            }
            for row in rows
        ]
    except (sqlite3.Error, FileNotFoundError):
        return []


def _fetch_commands(limit: int = 100) -> list[dict]:
    """Return recent commands/acks from SQLite, newest first."""
    if not _DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(_DB_PATH), timeout=2)
        rows = conn.execute(
            "SELECT command_id, action, reason, node_id, status, issued_at "
            "FROM commands ORDER BY issued_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            {"command_id": r[0], "action": r[1], "reason": r[2],
             "node_id": r[3], "status": r[4], "issued_at": r[5]}
            for r in rows
        ]
    except (sqlite3.Error, FileNotFoundError):
        return []


def _tail_log(source: str, max_lines: int = 200) -> list[dict]:
    """Tail a log file, returning up to *max_lines* entries.

    *source* is ``"server"``, ``"panel"``, or ``"all"``.
    """
    log_paths: dict[str, Path] = {
        "server": _PROJECT_ROOT / "logs" / "server.log",
        "panel": _PROJECT_ROOT / "logs" / "panel.log",
    }
    sources_to_read = [source] if source in log_paths else list(log_paths)
    entries: list[dict] = []

    for src in sources_to_read:
        path = log_paths[src]
        if not path.exists():
            continue
        try:
            # Read last ~64 KB, split into lines, take the tail
            with path.open("rb") as fh:
                fh.seek(0, 2)                     # seek to end
                size = fh.tell()
                chunk_size = min(size, 65_536)     # 64 KB window
                fh.seek(size - chunk_size)
                raw = fh.read(chunk_size)
            lines = raw.decode("utf-8", errors="replace").splitlines()
            for line in lines[-max_lines:]:
                entries.append({"source": src, "line": line})
        except OSError:
            pass

    # Reverse so newest entries come first (matches "log tail" intuition)
    entries.reverse()
    return entries


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler — API routes + static file fallback."""

    # Make the handler serve from frontend/static/ by default
    def translate_path(self, path: str) -> str:
        """Override to serve static files from ``frontend/static/``."""
        # Strip leading slash
        relative = path.lstrip("/")
        candidate = _STATIC_DIR / relative
        if candidate.exists() or relative == "":
            return str(candidate)
        # Fallback to the static dir root (serves index.html)
        return str(_STATIC_DIR / relative)

    # ---- GET ----

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = self._parse_query()

        if path == "/api/status":
            payload = _build_status_payload()
            payload["uptime_seconds"] = int(time.time() - _DASHBOARD_START)
            self._send_json(payload)
        elif path == "/api/artifacts":
            self._send_json(_build_artifacts_payload())
        elif path == "/api/metrics":
            limit = int(qs.get("limit", ["200"])[0])
            nodes_raw = qs.get("nodes", [None])[0]
            nodes = tuple(n.strip() for n in nodes_raw.split(",")) if nodes_raw else None
            metrics = _fetch_metrics(limit=limit, nodes=nodes)
            node_ids = sorted({m["node_id"] for m in metrics})
            self._send_json({
                "count": len(metrics),
                "nodes": node_ids,
                "metrics": metrics,
            })
        elif path == "/api/logs":
            max_lines = int(qs.get("lines", ["100"])[0])
            source = qs.get("source", ["all"])[0]
            if source not in ("server", "panel", "all"):
                source = "all"
            logs = _tail_log(source, max_lines=max_lines)
            self._send_json({"count": len(logs), "logs": logs})
        else:
            super().do_GET()

    # ---- POST ----

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        handlers = {
            "/api/reset": self._handle_reset,
            "/api/tests": self._handle_tests,
            "/api/scenario": self._handle_scenario,
            "/api/demo-bundle": self._handle_demo_bundle,
            "/api/nmap": self._handle_nmap,
            "/api/tshark-capture": self._handle_tshark,
            "/api/screenshots": self._handle_screenshots,
        }
        handler = handlers.get(path)
        if handler:
            handler(body)
        else:
            self._send_json({"error": "not_found"}, status=404)

    # ---- Per-endpoint logic ----

    def _handle_reset(self, body: dict | None = None) -> None:
        result = _run_cmd(["bash", "scripts/reset_environment.sh"], timeout=15)
        artifact = _save_artifact("reset", "Environment reset", {
            "success": result["success"],
            "returncode": result["returncode"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        })
        self._send_json(artifact)

    def _handle_tests(self, body: dict | None = None) -> None:
        result = _run_cmd(
            ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
            timeout=120,
        )
        artifact = _save_artifact("tests", "Test suite run", {
            "success": result["success"],
            "returncode": result["returncode"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "db_stats": _db_stats(),
        })
        self._send_json(artifact)

    def _handle_scenario(self, body: dict | None = None) -> None:
        scenario = (body or {}).get("scenario", "normal")
        node_id = (body or {}).get("node_id", "node-01")
        interval = (body or {}).get("interval", 3.0)

        result = _run_cmd(
            ["bash", "scripts/run_scenario.sh", scenario],
            timeout=60,
        )
        artifact = _save_artifact(f"scenario_{scenario}", f"Scenario: {scenario}", {
            "scenario": scenario,
            "node_id": node_id,
            "interval": interval,
            "success": result["success"],
            "returncode": result["returncode"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "db_stats": _db_stats(),
        })
        self._send_json(artifact)

    def _handle_demo_bundle(self, body: dict | None = None) -> None:
        """Reset → run several scenarios → collect final stats."""
        results: dict[str, object] = {}

        # 1. Reset
        r = _run_cmd(["bash", "scripts/reset_environment.sh"], timeout=15)
        results["reset"] = {"success": r["success"], "returncode": r["returncode"]}
        if not r["success"]:
            self._send_json(_save_artifact("demo_bundle", "Demo bundle (failed at reset)", results))
            return

        # 2. Run scenarios sequentially
        scenarios = ["normal", "high-cpu", "high-ram"]
        for sc in scenarios:
            r = _run_cmd(["bash", "scripts/run_scenario.sh", sc], timeout=60)
            results[sc] = {"success": r["success"], "returncode": r["returncode"]}
        results["scenarios_run"] = scenarios

        # 3. Final DB stats
        results["db_stats"] = _db_stats()

        artifact = _save_artifact("demo_bundle", "Full demo bundle", results)
        self._send_json(artifact)

    def _handle_nmap(self, body: dict | None = None) -> None:
        server = _start_monitor_server()
        time.sleep(1.0)
        try:
            result = _run_with_toolenv(
                ["nmap", "-p", "5000", "-T4", "127.0.0.1"],
                timeout=30,
            )
        finally:
            _stop_process(server)
        artifact = _save_artifact("nmap", "Nmap localhost scan", {
            "status": "success" if result["success"] else "error",
            "message": "Escaneo Nmap completado" if result["success"] else "No se pudo ejecutar Nmap",
            "target": "127.0.0.1",
            "ports": "5000",
            "success": result["success"],
            "returncode": result["returncode"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        })
        self._send_json(artifact)

    def _handle_tshark(self, body: dict | None = None) -> None:
        """Attempt a 5-second capture on loopback port 5000.

        If dumpcap permissions are missing the error is returned in a
        ``tshark_blocked`` artifact with a resolution hint — the dashboard
        stays operational.
        """
        output = f"captures/tshark_{_ts()}.pcapng"
        server = _start_monitor_server()
        client = None
        try:
            time.sleep(1.0)
            client = subprocess.Popen(
                [sys.executable, "-m", "client.tcp_client", "--node-id", "node-01", "--mode", "high-cpu", "--interval", "1.0"],
                cwd=str(_PROJECT_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            result = _run_with_toolenv(
                ["dumpcap", "-i", "lo", "-a", "duration:5", "-w", output],
                timeout=15,
            )
        finally:
            _stop_process(client)
            _stop_process(server)

        stderr_lower = result["stderr"].lower()
        if not result["success"] and (
            "permission" in stderr_lower
            or "operation not permitted" in stderr_lower
            or "couldn't run" in stderr_lower
        ):
            artifact = _save_artifact(
                "tshark_blocked",
                "TShark capture blocked — no OS permission",
                {
                    "status": "blocked",
                    "message": "Captura bloqueada por permisos del sistema",
                    "target": "lo:5000",
                    "success": False,
                    "error": "dumpcap/tshark lacks permission to capture on loopback",
                    "detail": result["stderr"],
                    "resolution": (
                        "Run as root, or set capabilities: "
                        "sudo setcap cap_net_raw,cap_net_admin=eip /usr/bin/dumpcap"
                    ),
                    "preflight_stdout": result["stdout"],
                },
            )
        elif not result["success"]:
            artifact = _save_artifact("tshark_error", "TShark capture failed", {
                "status": "error",
                "message": "La captura falló",
                "target": "lo:5000",
                "success": False,
                "error": result["stderr"],
                "stdout": result["stdout"],
            })
        else:
            artifact = _save_artifact("tshark", "TShark capture", {
                "status": "success",
                "message": "Captura generada",
                "target": "lo:5000",
                "success": True,
                "output": output,
                "path": output,
                "stdout": result["stdout"],
            })
        self._send_json(artifact)

    def _handle_screenshots(self, body: dict | None = None) -> None:
        """Run the screenshot generation script."""
        result = _run_cmd(
            ["bash", "scripts/generate_demo_screenshots.sh"],
            timeout=120,
        )
        # Collect any screenshot files
        screenshots: list[str] = []
        if _SCREENSHOTS_DIR.exists():
            for fpath in sorted(_SCREENSHOTS_DIR.iterdir()):
                if fpath.suffix in (".png", ".jpg", ".jpeg", ".webp"):
                    screenshots.append(fpath.name)

        artifact = _save_artifact("screenshots", "Demo screenshots", {
            "status": "success" if result["success"] else "error",
            "message": "Capturas generadas" if result["success"] else "No se pudieron generar las capturas",
            "success": result["success"],
            "returncode": result["returncode"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "screenshots": screenshots,
            "files": [str((_SCREENSHOTS_DIR / name).relative_to(_PROJECT_ROOT)) for name in screenshots],
        })
        self._send_json(artifact)

    # ---- Wire helpers ----

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _parse_query(self) -> dict[str, list[str]]:
        from urllib.parse import parse_qs
        return parse_qs(urlparse(self.path).query)  # type: ignore[arg-type]

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — matches BaseHTTPRequestHandler signature
        """Suppress noise from API polling; still log static-file requests."""
        if not self.path.startswith("/api/"):
            super().log_message(format, *args)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the dashboard HTTP server."""
    port = int(os.environ.get("DASHBOARD_PORT", 8080))
    host = os.environ.get("DASHBOARD_HOST", "127.0.0.1")

    # Ensure a placeholder index exists so the server has something to serve
    index = _STATIC_DIR / "index.html"
    if not index.exists():
        index.write_text(
            "<!DOCTYPE html>\n<html><head><title>Monitor Dashboard</title></head>\n"
            "<body><h1>Dashboard</h1><p>Waiting for designer content…</p></body></html>\n"
        )

    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"[dashboard] listening on http://{host}:{port}")
    print(f"[dashboard] static files → {_STATIC_DIR}")
    print(f"[dashboard] artifacts       → {_DEMO_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[dashboard] shutdown")
        server.server_close()


if __name__ == "__main__":
    main()
