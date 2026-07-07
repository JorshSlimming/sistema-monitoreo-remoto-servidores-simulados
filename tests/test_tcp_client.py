"""Unit tests for client.tcp_client."""

import json
import unittest

from client.tcp_client import ANOMALY_MODES, build_metric, decode_message, encode_message


class BuildMetricTests(unittest.TestCase):
    """build_metric produces correct shapes for all modes."""

    def test_normal_mode(self) -> None:
        metric = build_metric("node-01", 0, "normal")
        self.assertEqual(metric["type"], "metric")
        self.assertEqual(metric["node_id"], "node-01")
        self.assertEqual(metric["seq"], 0)
        self.assertEqual(metric["token"], "node-01-secret")
        self.assertAlmostEqual(metric["cpu"], 35.0)
        self.assertAlmostEqual(metric["ram"], 45.0)
        self.assertEqual(metric["latency_ms"], 40)
        self.assertEqual(metric["service_web"], "ok")
        self.assertEqual(metric["event_log"], "normal")

    def test_high_cpu_overrides(self) -> None:
        metric = build_metric("node-01", 1, "high-cpu")
        self.assertAlmostEqual(metric["cpu"], 95.0)
        self.assertAlmostEqual(metric["ram"], 45.0)  # unchanged

    def test_high_ram_overrides(self) -> None:
        metric = build_metric("node-01", 2, "high-ram")
        self.assertAlmostEqual(metric["ram"], 94.0)

    def test_high_latency_overrides(self) -> None:
        metric = build_metric("node-01", 3, "high-latency")
        self.assertEqual(metric["latency_ms"], 350)

    def test_service_failure_overrides(self) -> None:
        metric = build_metric("node-01", 4, "service-failure")
        self.assertEqual(metric["service_web"], "falla")

    def test_failed_event_overrides(self) -> None:
        metric = build_metric("node-01", 5, "failed-event")
        self.assertEqual(metric["event_log"], "backup fallido")

    def test_unknown_node_uses_fallback_token(self) -> None:
        metric = build_metric("unknown-node", 0, "normal")
        self.assertEqual(metric["token"], "unknown")

    def test_all_anomaly_modes_exist(self) -> None:
        modes = {
            "high-cpu",
            "high-ram",
            "high-latency",
            "service-failure",
            "failed-event",
        }
        self.assertEqual(set(ANOMALY_MODES), modes)

    def test_seq_increments(self) -> None:
        m1 = build_metric("node-01", 10, "normal")
        m2 = build_metric("node-01", 11, "normal")
        self.assertEqual(m1["seq"], 10)
        self.assertEqual(m2["seq"], 11)


class EncodeDecodeTests(unittest.TestCase):
    """encode_message / decode_message round-trip."""

    def test_round_trip(self) -> None:
        original = {"type": "ack", "node_id": "node-01", "command_id": 1, "status": "applied"}
        encoded = encode_message(original)
        self.assertTrue(encoded.endswith(b"\n"))
        decoded = decode_message(encoded)
        self.assertEqual(decoded, original)

    def test_encode_is_compact(self) -> None:
        encoded = encode_message({"a": 1, "b": "hello"})
        text = encoded.decode("utf-8").strip()
        self.assertNotIn(" ", text)

    def test_decode_bad_type_raises(self) -> None:
        with self.assertRaises(ValueError):
            decode_message(b'["not", "a", "dict"]')

    def test_decode_invalid_json_raises(self) -> None:
        with self.assertRaises(json.JSONDecodeError):
            decode_message(b"{bad json}")


if __name__ == "__main__":
    unittest.main()
