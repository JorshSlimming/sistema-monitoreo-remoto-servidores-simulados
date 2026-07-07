"""Tests for the dashboard /api/state payload builder."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import frontend.dashboard_server as dashboard_server  # pyright: ignore[reportMissingImports]
from server.server_config import ServerConfig
from storage.store import DatabaseStore


class DashboardStatePayloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.db_path = Path(self._tmpdir.name) / "monitor.db"
        self.store = DatabaseStore(str(self.db_path))
        self.addCleanup(self.store.close)

        self._old_db_path = dashboard_server._DB_PATH
        self._old_monitor_config = dashboard_server._MONITOR_CONFIG
        dashboard_server._DB_PATH = self.db_path
        self.addCleanup(self._restore_db_path)

    def _restore_db_path(self) -> None:
        dashboard_server._DB_PATH = self._old_db_path
        dashboard_server._MONITOR_CONFIG = self._old_monitor_config

    def test_build_state_payload_includes_nodes_series_commands_and_acks(self) -> None:
        self.store.save_metric(
            "node-02",
            7,
            74.0,
            45.0,
            40.0,
            "ok",
            "normal",
            scenario="high-cpu",
            anomaly_active=True,
            mitigation_active=True,
            mitigation_type="reduce_cpu",
            last_command="reduce_cpu",
        )
        self.store.save_command(11, "reduce_cpu", "cpu above 90", "node-02")
        self.store.update_command_status(11, "confirmed")
        self.store.save_ack(11, "node-02", "applied")

        payload = dashboard_server._build_state_payload()

        self.assertIn("server", payload)
        self.assertIn("nodes", payload)
        self.assertIn("series", payload)
        self.assertIn("commands", payload)
        self.assertIn("acks", payload)
        self.assertIn("events", payload)
        self.assertIn("logs", payload)

        self.assertIn("node-02", payload["nodes"])
        node = payload["nodes"]["node-02"]
        self.assertEqual(node["scenario"], "high-cpu")
        self.assertTrue(node["anomaly_active"])
        self.assertTrue(node["mitigation_active"])
        self.assertEqual(node["mitigation_type"], "reduce_cpu")
        self.assertEqual(node["last_command"], "reduce_cpu")
        self.assertIsInstance(node["staleness_seconds"], float)
        self.assertGreaterEqual(node["staleness_seconds"], 0.0)

        series = payload["series"]["node-02"]
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0]["seq"], 7)
        self.assertEqual(series[0]["cpu"], 74.0)

        self.assertEqual(payload["commands"][0]["status"], "confirmed")
        self.assertEqual(payload["acks"][0]["status"], "applied")
        event_types = {event["type"] for event in payload["events"]}
        self.assertIn("command", event_types)
        self.assertIn("ack", event_types)

    def test_build_state_payload_uses_latest_metric_for_node_snapshot(self) -> None:
        self.store.save_metric(
            "node-03",
            1,
            95.0,
            45.0,
            40.0,
            "ok",
            "normal",
            scenario="high-cpu",
            anomaly_active=True,
            mitigation_active=False,
            mitigation_type="",
            last_command="",
        )
        self.store.save_metric(
            "node-03",
            2,
            74.0,
            45.0,
            40.0,
            "ok",
            "normal",
            scenario="high-cpu",
            anomaly_active=True,
            mitigation_active=True,
            mitigation_type="reduce_cpu",
            last_command="reduce_cpu",
        )

        payload = dashboard_server._build_state_payload()
        node = payload["nodes"]["node-03"]

        self.assertEqual(node["cpu"], 74.0)
        self.assertTrue(node["mitigation_active"])
        self.assertEqual(node["mitigation_type"], "reduce_cpu")
        self.assertEqual(node["last_command"], "reduce_cpu")

    def test_state_payload_reports_tcp_server_reachability(self) -> None:
        dashboard_server._MONITOR_CONFIG = ServerConfig(
            host="127.0.0.1",
            port=9,
            db_path=str(self.db_path),
        )

        payload = dashboard_server._build_state_payload()

        self.assertFalse(payload["server"]["running"])


if __name__ == "__main__":
    unittest.main()
