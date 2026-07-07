"""Integration test: real server, real client, verify SQLite persistence."""

import json
import os
import socket
import tempfile
import threading
import time
import unittest

from server.server_config import ServerConfig
from server.server_state import ServerState
from server.command_dispatcher import CommandDispatcher
from server.connection_manager import ConnectionManager
from storage.store import DatabaseStore
from shared.auth import get_token


def _encode(msg: dict) -> bytes:
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


class PersistenceIntegrationTest(unittest.TestCase):
    """Starts a real server in a thread, sends a real client interaction,
    and asserts rows are written to the database."""

    def setUp(self) -> None:
        self._db_fd, self._db_path = tempfile.mkstemp(suffix=".db")
        os.close(self._db_fd)

        self._store = DatabaseStore(self._db_path)
        self._state = ServerState()
        self._dispatcher = CommandDispatcher()
        self._config = ServerConfig(
            host="127.0.0.1",
            port=0,  # ephemeral — OS assigns
            db_path=self._db_path,
        )

        self._manager = ConnectionManager(
            self._config, self._state, self._dispatcher, store=self._store,
        )

        self._server_thread = threading.Thread(
            target=self._manager.serve_forever, daemon=True,
        )
        self._server_thread.start()
        time.sleep(0.3)
        self._port = self._manager.port

    def tearDown(self) -> None:
        self._manager.stop()
        self._server_thread.join(timeout=3)
        self._store.close()
        if os.path.exists(self._db_path):
            os.unlink(self._db_path)

    # ----------------------------------------------------------------
    # Tests
    # ----------------------------------------------------------------

    def test_metric_persisted(self) -> None:
        """Send a normal metric, verify it lands in the metrics table."""
        sock = self._open_connection()
        self._send_metric(sock, "node-01", 1, cpu=35.0, ram=45.0)
        time.sleep(0.2)
        sock.close()
        time.sleep(0.1)

        self.assertGreaterEqual(self._store._count_metrics(), 1)

    def test_command_persisted(self) -> None:
        """Send a metric that triggers a command, verify the command is persisted."""
        sock = self._open_connection()
        self._send_metric(sock, "node-01", 1, cpu=95.0, ram=45.0)
        time.sleep(0.3)
        try:
            sock.recv(4096)
        except socket.timeout:
            pass
        sock.close()
        time.sleep(0.1)

        self.assertGreaterEqual(self._store._count_commands(), 1)

    def test_ack_persisted(self) -> None:
        """Send a metric that triggers a command, ack it, verify ack persisted."""
        sock = self._open_connection()
        self._send_metric(sock, "node-01", 1, cpu=95.0, ram=45.0)

        time.sleep(0.3)
        raw = sock.recv(4096)
        command = None
        for line in raw.split(b"\n"):
            if not line:
                continue
            msg = json.loads(line.decode("utf-8").strip())
            if msg.get("type") == "command":
                command = msg
                break

        self.assertIsNotNone(command)
        assert command is not None
        cid = command["command_id"]

        ack = {
            "type": "ack",
            "node_id": "node-01",
            "command_id": cid,
            "status": "applied",
            "token": get_token("node-01") or "unknown",
        }
        sock.sendall(_encode(ack))
        time.sleep(0.2)
        sock.close()
        time.sleep(0.1)

        self.assertGreaterEqual(self._store._count_acks(), 1)

    def test_command_status_updated_on_ack(self) -> None:
        """After ack, command status transitions to 'confirmed' in the DB."""
        sock = self._open_connection()
        self._send_metric(sock, "node-01", 1, cpu=95.0, ram=45.0)

        time.sleep(0.3)
        raw = sock.recv(4096)
        command = None
        for line in raw.split(b"\n"):
            if not line:
                continue
            msg = json.loads(line.decode("utf-8").strip())
            if msg.get("type") == "command":
                command = msg
                break

        self.assertIsNotNone(command)
        assert command is not None
        cid = command["command_id"]

        ack = {
            "type": "ack",
            "node_id": "node-01",
            "command_id": cid,
            "status": "applied",
            "token": get_token("node-01") or "unknown",
        }
        sock.sendall(_encode(ack))
        time.sleep(0.2)

        # Verify command status was updated in DB
        status_rows = []
        with self._store._lock:
            cursor = self._store._conn.execute(
                "SELECT status FROM commands WHERE command_id = ?", (cid,)
            )
            status_rows = cursor.fetchall()
        self.assertEqual(len(status_rows), 1)
        self.assertEqual(status_rows[0][0], "confirmed")

        sock.close()
        time.sleep(0.1)

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    def _open_connection(self) -> socket.socket:
        sock = socket.create_connection(("127.0.0.1", self._port), timeout=5)
        sock.settimeout(2)
        return sock

    def _send_metric(
        self,
        sock: socket.socket,
        node_id: str,
        seq: int,
        cpu: float = 35.0,
        ram: float = 45.0,
    ) -> None:
        token = get_token(node_id) or "unknown"
        metric = {
            "type": "metric",
            "node_id": node_id,
            "seq": seq,
            "cpu": cpu,
            "ram": ram,
            "latency_ms": 40,
            "service_web": "ok",
            "event_log": "normal",
            "token": token,
        }
        sock.sendall(_encode(metric))


if __name__ == "__main__":
    unittest.main()
