"""Unit tests for the attacker attack catalog functions."""
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

# Import the attack functions
from attacker.attack_simulator import (
    ATTACKS,
    _check_target,
    attack_plaintext_metric,
    attack_unknown_node,
    attack_bad_psk,
    attack_node_mismatch,
    attack_invalid_metric,
    attack_tampered_frame,
    attack_replay_frame,
)


class AttackCatalogTests(unittest.TestCase):
    """Tests that the attack catalog is properly defined."""

    def test_all_attacks_defined(self) -> None:
        expected = {
            "plaintext-metric", "unknown-node", "bad-psk",
            "node-mismatch", "invalid-metric", "tampered-frame",
            "replay-frame",
        }
        self.assertEqual(set(ATTACKS), expected)

    def test_each_attack_has_required_fields(self) -> None:
        for key, info in ATTACKS.items():
            with self.subTest(key=key):
                self.assertIn("func", info)
                self.assertIn("label", info)
                self.assertIn("description", info)
                self.assertTrue(callable(info["func"]))


class AttackTargetCheckTests(unittest.TestCase):
    """Tests for the local-only target enforcement."""

    def test_localhost_allowed(self) -> None:
        _check_target("127.0.0.1")  # should not raise

    def test_loopback_allowed(self) -> None:
        _check_target("localhost")

    def test_non_local_raises(self) -> None:
        with self.assertRaises(ValueError):
            _check_target("192.168.1.100")

    def test_external_domain_raises(self) -> None:
        with self.assertRaises(ValueError):
            _check_target("example.com")

    def test_env_override_allows_non_local(self) -> None:
        os.environ["ALLOW_NON_LOCAL_ATTACK_TARGET"] = "1"
        try:
            _check_target("192.168.1.100")  # should not raise
        finally:
            del os.environ["ALLOW_NON_LOCAL_ATTACK_TARGET"]


class AttackResultFormatTests(unittest.TestCase):
    """Verify result dict structure returned by each attack function."""

    REQUIRED_FIELDS = {
        "attack_id", "name", "description", "expected_result",
        "success", "server_response", "observed_error",
        "timestamp", "duration_ms", "risk_level_demo", "authorized_scope",
    }

    def _check_result_shape(self, result: dict, attack_name: str) -> None:
        missing = self.REQUIRED_FIELDS - set(result)
        self.assertEqual(
            missing, set(),
            f"{attack_name}: missing fields {missing}",
        )
        self.assertIsInstance(result.get("attack_id"), str)
        self.assertIn("attack-", str(result.get("attack_id", "")))

    def test_plaintext_metric_returns_result_shape(self) -> None:
        # This will fail to connect, but should still return a structured result
        result = attack_plaintext_metric("127.0.0.1", 19999, timeout=0.5)
        self._check_result_shape(result, "plaintext-metric")

    def test_unknown_node_returns_result_shape(self) -> None:
        result = attack_unknown_node("127.0.0.1", 19999, timeout=0.5)
        self._check_result_shape(result, "unknown-node")

    def test_bad_psk_returns_result_shape(self) -> None:
        result = attack_bad_psk("127.0.0.1", 19999, timeout=0.5)
        self._check_result_shape(result, "bad-psk")

    def test_node_mismatch_returns_result_shape(self) -> None:
        result = attack_node_mismatch("127.0.0.1", 19999, timeout=0.5)
        self._check_result_shape(result, "node-mismatch")

    def test_invalid_metric_returns_result_shape(self) -> None:
        result = attack_invalid_metric("127.0.0.1", 19999, timeout=0.5)
        self._check_result_shape(result, "invalid-metric")

    def test_tampered_frame_returns_result_shape(self) -> None:
        result = attack_tampered_frame("127.0.0.1", 19999, timeout=0.5)
        self._check_result_shape(result, "tampered-frame")

    def test_replay_frame_returns_result_shape(self) -> None:
        result = attack_replay_frame("127.0.0.1", 19999, timeout=0.5)
        self._check_result_shape(result, "replay-frame")


class AttackBehaviorAgainstRealServerTests(unittest.TestCase):
    """Starts a real server and runs attack functions against it."""

    def setUp(self) -> None:
        self._db_fd, self._db_path = tempfile.mkstemp(suffix=".db")
        os.close(self._db_fd)
        self._store = DatabaseStore(self._db_path)
        self._state = ServerState()
        self._dispatcher = CommandDispatcher()
        self._config = ServerConfig(
            host="127.0.0.1", port=0, db_path=self._db_path,
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

    def test_plaintext_metric_detected_by_server(self) -> None:
        result = attack_plaintext_metric("127.0.0.1", self._port, timeout=2.0)
        self.assertTrue(result["success"],
                        f"plaintext metric should be rejected: {result.get('server_response')}")

    def test_unknown_node_detected(self) -> None:
        result = attack_unknown_node("127.0.0.1", self._port, timeout=2.0)
        self.assertTrue(result["success"],
                        f"unknown node should be rejected: {result.get('server_response')}")

    def test_bad_psk_detected(self) -> None:
        result = attack_bad_psk("127.0.0.1", self._port, timeout=2.0)
        self.assertTrue(result["success"],
                        f"bad PSK should be rejected: {result.get('server_response')}")

    def test_node_mismatch_detected(self) -> None:
        result = attack_node_mismatch("127.0.0.1", self._port, timeout=2.0)
        self.assertTrue(result["success"],
                        f"node mismatch should be rejected: {result.get('server_response')}")

    def test_invalid_metric_detected(self) -> None:
        result = attack_invalid_metric("127.0.0.1", self._port, timeout=2.0)
        self.assertTrue(result["success"],
                        f"invalid metric should be rejected: {result.get('server_response')}")

    def test_tampered_frame_detected(self) -> None:
        result = attack_tampered_frame("127.0.0.1", self._port, timeout=2.0)
        self.assertTrue(result["success"],
                        f"tampered frame should be rejected: {result.get('server_response')}")

    def test_replay_frame_detected(self) -> None:
        result = attack_replay_frame("127.0.0.1", self._port, timeout=2.0)
        self.assertTrue(result["success"],
                        f"replay frame should be rejected: {result.get('server_response')}")


class AttackMetricsNotPersistedTests(unittest.TestCase):
    """Verify that attacks do not result in invalid metrics being persisted."""

    def setUp(self) -> None:
        self._db_fd, self._db_path = tempfile.mkstemp(suffix=".db")
        os.close(self._db_fd)
        self._store = DatabaseStore(self._db_path)
        self._state = ServerState()
        self._dispatcher = CommandDispatcher()
        self._config = ServerConfig(
            host="127.0.0.1", port=0, db_path=self._db_path,
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

    def _db_metrics_count(self) -> int:
        return self._store._count_metrics()

    def _db_commands_count(self) -> int:
        return self._store._count_commands()

    def test_tampered_frame_does_not_persist_metric(self) -> None:
        """The tampered frame itself should not be persisted as a valid metric.
        The attack sends one valid metric first (which is expected to persist),
        then a tampered frame which must NOT add a second metric."""
        before = self._db_metrics_count()
        result = attack_tampered_frame("127.0.0.1", self._port, timeout=2.0)
        time.sleep(0.3)
        after = self._db_metrics_count()
        # The valid metric sent during the attack gets persisted (+1).
        # The tampered frame must NOT add an additional metric.
        self.assertLessEqual(after, before + 1,
                             f"tampered frame added extra metrics: {after - before} increase (expected <=1)")

    def test_plaintext_metric_does_not_persist(self) -> None:
        before = self._db_metrics_count()
        attack_plaintext_metric("127.0.0.1", self._port, timeout=2.0)
        time.sleep(0.2)
        after = self._db_metrics_count()
        self.assertEqual(after, before,
                         "plaintext metric should not result in persisted metric")

    def test_replay_frame_does_not_create_second_metric(self) -> None:
        """Verify replay does not create a second valid metric entry.
        The attack sends one valid metric then replays it.  Only the first
        should be persisted."""
        import socket as sk
        from shared.secure_channel import client_handshake

        # Baseline — send a valid metric through a real connection.
        sock = sk.create_connection(("127.0.0.1", self._port), timeout=5)
        secure = client_handshake(sock, "node-01")
        secure.send_message({
            "type": "metric", "node_id": "node-01", "seq": 10,
            "cpu": 35.0, "ram": 45.0, "latency_ms": 30,
            "service_web": "ok", "event_log": "normal",
            "token": get_token("node-01") or "unknown",
        })
        time.sleep(0.3)
        try:
            secure.recv_message()
        except Exception:
            pass
        sock.close()

        metrics_after_valid = self._db_metrics_count()
        self.assertGreaterEqual(metrics_after_valid, 1,
                                "valid metric should be persisted")

        # Run the replay attack — sends 2 valid metrics (one per session)
        # then replays a captured frame (which is rejected).
        attack_replay_frame("127.0.0.1", self._port, timeout=2.0)
        time.sleep(0.4)
        metrics_after_replay = self._db_metrics_count()
        # Attack sends 2 valid metrics (session A: seq=1, session B: dummy seq=10).
        # The replayed frame is rejected and adds nothing.
        expected_max = metrics_after_valid + 2
        self.assertLessEqual(
            metrics_after_replay, expected_max,
            f"replay added {metrics_after_replay - metrics_after_valid} metrics (expected <=2)",
        )
        # Critical: verify the replay did NOT add an extra metric beyond the 2 valid ones.
        self.assertEqual(
            metrics_after_replay, metrics_after_valid + 2,
            "replay attack should persist exactly 2 valid metrics and 0 invalid ones",
        )


if __name__ == "__main__":
    unittest.main()
