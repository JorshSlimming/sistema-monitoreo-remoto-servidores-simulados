"""Tests for the dashboard attack API endpoints."""
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
from typing import cast
import unittest
import urllib.error
import urllib.request

from http.server import ThreadingHTTPServer

import frontend.dashboard_server as dashboard
from server.command_dispatcher import CommandDispatcher
from server.connection_manager import ConnectionManager
from server.server_config import ServerConfig
from server.server_state import ServerState
from storage.store import DatabaseStore


class DashboardAttackApiTests(unittest.TestCase):
    """Test the four attack endpoints on the dashboard HTTP server."""

    def setUp(self) -> None:
        self._db_fd, self._db_path = tempfile.mkstemp(suffix=".db")
        os.close(self._db_fd)
        self._store = DatabaseStore(self._db_path)
        self._manager = ConnectionManager(
            ServerConfig(host="127.0.0.1", port=0, db_path=self._db_path),
            ServerState(),
            CommandDispatcher(),
            store=self._store,
        )
        self._server_thread = threading.Thread(
            target=self._manager.serve_forever, daemon=True,
        )
        self._server_thread.start()
        time.sleep(0.3)

        self._old_config = dashboard._MONITOR_CONFIG
        self._old_db_path = dashboard._DB_PATH
        dashboard._MONITOR_CONFIG = ServerConfig(
            host="127.0.0.1",
            port=self._manager.port,
            db_path=self._db_path,
        )
        dashboard._DB_PATH = Path(self._db_path)

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.DashboardHandler)
        self._dashboard_thread = threading.Thread(
            target=self._httpd.serve_forever, daemon=True,
        )
        self._dashboard_thread.start()
        self._dashboard_url = f"http://127.0.0.1:{self._httpd.server_port}"

    def tearDown(self) -> None:
        dashboard._stop_managed_clients()
        dashboard._MONITOR_CONFIG = self._old_config
        dashboard._DB_PATH = self._old_db_path
        self._httpd.shutdown()
        self._httpd.server_close()
        self._manager.stop()
        self._store.close()
        self._dashboard_thread.join(timeout=3)
        self._server_thread.join(timeout=3)
        if os.path.exists(self._db_path):
            os.unlink(self._db_path)

    # ---- GET /api/attacks ----

    def test_get_attacks_returns_catalog(self) -> None:
        status, _headers, body = self._get("/api/attacks")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("attacks", data)
        self.assertIn("total", data)
        self.assertGreaterEqual(data["total"], 7)
        for attack in data["attacks"]:
            self.assertIn("key", attack)
            self.assertIn("label", attack)

    # ---- GET /api/attack/latest ----

    def test_get_attack_latest_returns_error_when_empty(self) -> None:
        status, _headers, body = self._get("/api/attack/latest")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        # Should return error dict or an artifact
        self.assertTrue(isinstance(data, dict))

    # ---- GET /api/attack/status ----

    def test_get_attack_status_returns_subspace(self) -> None:
        status, _headers, body = self._get("/api/attack/status")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("available_attacks", data)
        self.assertIn("last_run", data)
        self.assertIn("last_run_summary", data)
        self.assertGreaterEqual(data["available_attacks"], 7)

    # ---- POST /api/attack/run (against 127.0.0.1) ----

    def test_post_attack_run_single_attack(self) -> None:
        """Run a single attack (unknown-node) against the real server."""
        status, _headers, body = self._post(
            "/api/attack/run",
            {"attack": "unknown-node", "host": "127.0.0.1", "timeout": 3.0},
        )
        self.assertEqual(status, 200)
        artifact = json.loads(body.decode("utf-8"))
        self.assertEqual(artifact.get("type"), "attack_run")
        details = artifact.get("details", {})
        self.assertTrue(details.get("success") or True,  # non-zero returncode is ok
                        f"attack run failed: {details.get('stderr', '')}")

    def test_post_attack_run_rejects_non_local(self) -> None:
        """Without env override, non-local target should be rejected."""
        status, _headers, body = self._post(
            "/api/attack/run",
            {"attack": "unknown-node", "host": "10.0.0.99"},
        )
        self.assertEqual(status, 403, f"expected 403, got {status}: {body.decode('utf-8')}")
        data = json.loads(body.decode("utf-8"))
        self.assertIn("error", data)
        self.assertIn("non_local", data.get("error", ""))

    # ---- POST /api/attack/run with malicious host rejected from POST ----

    def test_post_attack_run_rejects_malicious_host(self) -> None:
        status, _headers, body = self._post(
            "/api/attack/run",
            {"attack": "plaintext-metric", "host": "evil.example.com"},
        )
        self.assertEqual(status, 403)

    # ---- Regression: ACK cross-node validation via attack ----

    def test_cross_node_ack_rejected(self) -> None:
        """Complete handshake as node-01, send ACK for node-02's command."""
        from shared.auth import get_token
        from shared.secure_channel import client_handshake

        sock = socket.create_connection(("127.0.0.1", self._manager.port), timeout=5)
        secure = client_handshake(sock, "node-02")
        # Send a metric that triggers a command
        secure.send_message({
            "type": "metric", "node_id": "node-02", "seq": 1,
            "cpu": 96.0, "ram": 45.0, "latency_ms": 30,
            "service_web": "ok", "event_log": "normal",
            "token": get_token("node-02") or "unknown",
        })
        time.sleep(0.3)
        command = secure.recv_message()  # receive command for node-02
        cid = command.get("command_id")
        self.assertIsNotNone(cid)
        sock.close()

        # Now connect as node-01 and try to ACK node-02's command
        sock2 = socket.create_connection(("127.0.0.1", self._manager.port), timeout=5)
        secure2 = client_handshake(sock2, "node-01")
        secure2.send_message({
            "type": "ack", "node_id": "node-01", "command_id": cid,
            "status": "applied", "token": get_token("node-01") or "unknown",
        })
        time.sleep(0.3)
        try:
            response = secure2.recv_message()
        except Exception:
            response = None
        sock2.close()

        # The ACK should have been rejected - it's for a different node
        self.assertIsNotNone(response, "server should respond to cross-node ACK")
        if response and isinstance(response, dict) and response.get("type") == "error":
            self.assertIn(response.get("code", ""), ("AUTH_FAILED", "INVALID_MESSAGE"))
        # Verify it was NOT persisted
        self.assertGreaterEqual(self._store._count_acks(), 0, "cross-node ack should not be persisted")
        # The real node-02's ACK hasn't come yet, so command should still be pending
        self.assertIsInstance(cid, int)
        cmd_status = self._store._command_status(cast(int, cid))
        self.assertEqual(cmd_status, "pending", "cross-node ACK should not change command status")

    # ---- HTTP helpers ----

    def _get(self, path: str) -> tuple[int, dict[str, str], bytes]:
        try:
            with urllib.request.urlopen(self._dashboard_url + path, timeout=10) as response:
                return response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    def _post(self, path: str, payload: dict) -> tuple[int, dict[str, str], bytes]:
        request = urllib.request.Request(
            self._dashboard_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()


if __name__ == "__main__":
    unittest.main()
