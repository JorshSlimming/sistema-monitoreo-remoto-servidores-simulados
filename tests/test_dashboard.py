"""Integration checks for the dashboard HTTP API."""

from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

import frontend.dashboard_server as dashboard
from server.command_dispatcher import CommandDispatcher
from server.connection_manager import ConnectionManager
from server.server_config import ServerConfig
from server.server_state import ServerState
from storage.store import DatabaseStore


class DashboardIntegrationTests(unittest.TestCase):
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
            target=self._manager.serve_forever,
            daemon=True,
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
            target=self._httpd.serve_forever,
            daemon=True,
        )
        self._dashboard_thread.start()
        self._dashboard_url = f"http://127.0.0.1:{self._httpd.server_port}"

    def tearDown(self) -> None:
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

    def test_static_files_and_core_api_endpoints_respond(self) -> None:
        for path in ("/", "/app.js", "/styles.css", "/api/status", "/api/metrics", "/api/events"):
            status, _headers, body = self._get(path)

            self.assertEqual(status, 200, path)
            self.assertGreater(len(body), 0, path)

    def test_scenario_endpoint_runs_real_client_and_reports_success(self) -> None:
        status, _headers, body = self._post(
            "/api/scenario",
            {"scenario": "high-cpu", "node_id": "node-01", "interval": 1.0},
        )

        self.assertEqual(status, 200)
        artifact = json.loads(body.decode("utf-8"))
        details = artifact["details"]
        self.assertTrue(details["success"], details)
        self.assertGreaterEqual(details["db_stats"]["metrics"], 1)
        self.assertGreaterEqual(details["db_stats"]["commands"], 1)
        self.assertGreaterEqual(details["db_stats"]["acks"], 1)

    def _get(self, path: str) -> tuple[int, dict[str, str], bytes]:
        with urllib.request.urlopen(self._dashboard_url + path, timeout=10) as response:
            return response.status, dict(response.headers), response.read()

    def _post(self, path: str, payload: dict) -> tuple[int, dict[str, str], bytes]:
        request = urllib.request.Request(
            self._dashboard_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, dict(response.headers), response.read()


class FakeClientIntegrationTests(unittest.TestCase):
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
            target=self._manager.serve_forever,
            daemon=True,
        )
        self._server_thread.start()
        time.sleep(0.3)

    def tearDown(self) -> None:
        self._manager.stop()
        self._store.close()
        self._server_thread.join(timeout=3)
        if os.path.exists(self._db_path):
            os.unlink(self._db_path)

    def test_fake_client_speaks_plain_json_with_token(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "tests/fake_client.py",
                "--host",
                "127.0.0.1",
                "--port",
                str(self._manager.port),
                "--node-id",
                "node-01",
                "--mode",
                "high-cpu",
            ],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(self._store._count_metrics(), 1)
        self.assertGreaterEqual(self._store._count_commands(), 1)
        self.assertGreaterEqual(self._store._count_acks(), 1)


if __name__ == "__main__":
    unittest.main()
