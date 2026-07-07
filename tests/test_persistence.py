"""Integration test: real server, secure client, verify SQLite persistence."""

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
from shared.secure_channel import SecureSocket, client_handshake


class PersistenceIntegrationTest(unittest.TestCase):
    """Starts a real server in a thread, sends a real encrypted interaction,
    and asserts rows are written to the database."""

    def setUp(self) -> None:
        self._db_fd, self._db_path = tempfile.mkstemp(suffix=".db")
        os.close(self._db_fd)

        self._store = DatabaseStore(self._db_path)
        self._state = ServerState()
        self._dispatcher = CommandDispatcher()
        self._config = ServerConfig(
            host="127.0.0.1",
            port=0,
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

    def test_metric_persisted(self) -> None:
        secure = self._open_connection("node-01")
        self._send_metric(secure, "node-01", 1, cpu=35.0, ram=45.0)
        time.sleep(0.2)
        secure.sock.close()

        self.assertGreaterEqual(self._store._count_metrics(), 1)

    def test_command_persisted(self) -> None:
        secure = self._open_connection("node-01")
        self._send_metric(secure, "node-01", 1, cpu=95.0, ram=45.0)
        time.sleep(0.3)
        try:
            secure.recv_message()
        except socket.timeout:
            pass
        secure.sock.close()

        self.assertGreaterEqual(self._store._count_commands(), 1)

    def test_ack_persisted(self) -> None:
        secure, command = self._send_high_cpu_and_recv_command()
        cid = command["command_id"]

        secure.send_message(
            {
                "type": "ack",
                "node_id": "node-01",
                "command_id": cid,
                "status": "applied",
                "token": get_token("node-01") or "unknown",
            }
        )
        time.sleep(0.2)
        secure.sock.close()

        self.assertGreaterEqual(self._store._count_acks(), 1)
        self.assertEqual(self._store._command_status(cid), "confirmed")

    def test_command_status_updated_on_ack(self) -> None:
        secure, command = self._send_high_cpu_and_recv_command()
        cid = command["command_id"]

        secure.send_message(
            {
                "type": "ack",
                "node_id": "node-01",
                "command_id": cid,
                "status": "applied",
                "token": get_token("node-01") or "unknown",
            }
        )
        time.sleep(0.2)

        with self._store._lock:
            status_rows = self._store._conn.execute(
                "SELECT status FROM commands WHERE command_id = ?",
                (cid,),
            ).fetchall()
        self.assertEqual(len(status_rows), 1)
        self.assertEqual(status_rows[0][0], "confirmed")

        secure.sock.close()

    def test_failed_ack_marks_command_failed(self) -> None:
        secure, command = self._send_high_cpu_and_recv_command()
        cid = command["command_id"]

        secure.send_message(
            {
                "type": "ack",
                "node_id": "node-01",
                "command_id": cid,
                "status": "failed",
                "token": get_token("node-01") or "unknown",
            }
        )
        time.sleep(0.2)

        self.assertEqual(self._store._command_status(cid), "failed")
        self.assertEqual(self._state.sent_commands[cid].status, "failed")

        secure.sock.close()

    def _send_high_cpu_and_recv_command(self) -> tuple[SecureSocket, dict]:
        secure = self._open_connection("node-01")
        self._send_metric(secure, "node-01", 1, cpu=95.0, ram=45.0)
        time.sleep(0.3)
        command = secure.recv_message()
        self.assertEqual(command.get("type"), "command")
        return secure, command

    def _open_connection(self, node_id: str) -> SecureSocket:
        sock = socket.create_connection(("127.0.0.1", self._port), timeout=5)
        sock.settimeout(2)
        return client_handshake(sock, node_id)

    def _send_metric(
        self,
        secure: SecureSocket,
        node_id: str,
        seq: int,
        cpu: float = 35.0,
        ram: float = 45.0,
    ) -> None:
        secure.send_message(
            {
                "type": "metric",
                "node_id": node_id,
                "seq": seq,
                "cpu": cpu,
                "ram": ram,
                "latency_ms": 40,
                "service_web": "ok",
                "event_log": "normal",
                "token": get_token(node_id) or "unknown",
            }
        )


if __name__ == "__main__":
    unittest.main()
