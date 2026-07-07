"""Unit tests for client.tcp_client."""

import json
import time
import unittest

from client.tcp_client import (
    ANOMALY_MODES,
    _BASE_METRIC,
    PROGRESSIVE_FACTOR,
    ClientState,
    _apply_command,
    _chaos_anomaly,
    _progressive_step,
    apply_command,
    build_initial_state,
    build_metric,
    decode_message,
    encode_message,
)


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

    def test_command_mitigation_changes_next_metric(self) -> None:
        state = build_initial_state("high-cpu")
        self.assertAlmostEqual(build_metric("node-01", 0, "high-cpu", state=state)["cpu"], 95.0)

        apply_command(state, "reduce_cpu")
        metric = build_metric("node-01", 1, "high-cpu", state=state)

        self.assertAlmostEqual(metric["cpu"], 35.0)


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


class ClientStateTests(unittest.TestCase):
    """ClientState dataclass and command application."""

    def test_default_state(self) -> None:
        s = ClientState(mode="high-cpu")
        self.assertEqual(s.mode, "high-cpu")
        self.assertTrue(s.anomaly_active)
        self.assertFalse(s.mitigation_active)
        self.assertIsNone(s.mitigation_type)
        self.assertIsNone(s.cpu)

    def test_snapshot_returns_copy(self) -> None:
        s = ClientState(mode="normal", cpu=95.0)
        snap = s.snapshot()
        self.assertEqual(snap["cpu"], 95.0)
        s.cpu = 50.0
        self.assertEqual(snap["cpu"], 95.0)  # unchanged

    def test_apply_reduce_cpu_sets_cpu(self) -> None:
        s = ClientState(mode="high-cpu")
        _apply_command("reduce_cpu", s)
        self.assertTrue(s.mitigation_active)
        self.assertEqual(s.mitigation_type, "reduce_cpu")
        self.assertIsNotNone(s.cpu)
        # Should be initialized to the anomaly value
        self.assertAlmostEqual(s.cpu, ANOMALY_MODES["high-cpu"]["cpu"])

    def test_apply_reduce_ram_sets_ram(self) -> None:
        s = ClientState(mode="high-ram")
        _apply_command("reduce_ram", s)
        self.assertIsNotNone(s.ram)
        self.assertAlmostEqual(s.ram, ANOMALY_MODES["high-ram"]["ram"])

    def test_apply_fix_latency_sets_latency(self) -> None:
        s = ClientState(mode="high-latency")
        _apply_command("fix_latency", s)
        self.assertIsNotNone(s.latency_ms)
        self.assertEqual(s.latency_ms, ANOMALY_MODES["high-latency"]["latency_ms"])

    def test_apply_restart_service_restores_service(self) -> None:
        s = ClientState(mode="service-failure")
        self.assertEqual(s.service_web, None)  # defaults to None
        _apply_command("restart_service", s)
        self.assertEqual(s.service_web, "ok")

    def test_apply_normalize_node_clears_all(self) -> None:
        s = ClientState(mode="high-cpu", cpu=95.0, ram=80.0, mitigation_active=True)
        _apply_command("normalize_node", s)
        self.assertFalse(s.anomaly_active)
        self.assertIsNone(s.cpu)
        self.assertIsNone(s.ram)
        self.assertIsNone(s.latency_ms)
        self.assertEqual(s.service_web, "ok")
        self.assertEqual(s.event_log, "normal")
        self.assertTrue(s.mitigation_active)  # Still active until step clears it

    def test_apply_returns_before_snapshot(self) -> None:
        s = ClientState(mode="high-cpu")
        before = _apply_command("normalize_node", s)
        self.assertTrue(before["anomaly_active"])
        self.assertFalse(s.anomaly_active)


class ProgressiveMitigationTests(unittest.TestCase):
    """Progressive recovery ticks move values toward baseline."""

    def test_progressive_tick_moves_toward_target(self) -> None:
        from client.tcp_client import _progressive_tick

        result = _progressive_tick(95.0, 35.0)
        expected = 95.0 + (35.0 - 95.0) * PROGRESSIVE_FACTOR
        self.assertAlmostEqual(result, expected)

    def test_progressive_step_reduces_cpu(self) -> None:
        s = ClientState(mode="high-cpu", cpu=95.0)
        _progressive_step(s)
        expected = 95.0 + (35.0 - 95.0) * PROGRESSIVE_FACTOR
        self.assertAlmostEqual(s.cpu, expected)  # type: ignore[arg-type]

    def test_progressive_step_clears_when_close(self) -> None:
        s = ClientState(
            mode="high-cpu", cpu=_BASE_METRIC["cpu"] + 0.5  # within 1.0
        )
        _progressive_step(s)
        self.assertIsNone(s.cpu)

    def test_progressive_step_clears_mitigation_when_done(self) -> None:
        s = ClientState(
            mode="high-cpu",
            cpu=_BASE_METRIC["cpu"] + 0.5,
            mitigation_active=True,
            mitigation_type="reduce_cpu",
        )
        _progressive_step(s)
        self.assertIsNone(s.cpu)
        self.assertFalse(s.mitigation_active)
        self.assertIsNone(s.mitigation_type)

    def test_multiple_steps_reach_baseline(self) -> None:
        s = ClientState(mode="high-cpu")
        _apply_command("reduce_cpu", s)
        initial_cpu = s.cpu
        self.assertIsNotNone(initial_cpu)
        for _ in range(10):
            _progressive_step(s)
            if s.cpu is None:
                break
        self.assertIsNone(s.cpu)


class BuildMetricEnrichmentTests(unittest.TestCase):
    """build_metric with ClientState adds enrichment fields and applies overrides."""

    def test_no_state_returns_basic_metric(self) -> None:
        metric = build_metric("node-01", 0, "normal")
        self.assertNotIn("scenario", metric)
        self.assertNotIn("mitigation_active", metric)

    def test_with_state_adds_enrichment_fields(self) -> None:
        s = ClientState(mode="high-cpu")
        metric = build_metric("node-01", 0, "high-cpu", state=s)
        self.assertIn("scenario", metric)
        self.assertEqual(metric["scenario"], "high-cpu")
        self.assertIn("anomaly_active", metric)
        self.assertIn("mitigation_active", metric)

    def test_mitigation_overrides_cpu(self) -> None:
        s = ClientState(mode="high-cpu", cpu=60.0, mitigation_active=True)
        metric = build_metric("node-01", 0, "high-cpu", state=s)
        self.assertAlmostEqual(metric["cpu"], 60.0)

    def test_anomaly_inactive_uses_base_values(self) -> None:
        s = ClientState(mode="high-cpu", anomaly_active=False)
        metric = build_metric("node-01", 0, "high-cpu", state=s)
        # anomaly overlay skipped → base value
        self.assertAlmostEqual(metric["cpu"], _BASE_METRIC["cpu"])

    def test_normalize_clears_completely(self) -> None:
        s = ClientState(mode="high-cpu")
        _apply_command("normalize_node", s)
        metric = build_metric("node-01", 0, "high-cpu", state=s)
        self.assertAlmostEqual(metric["cpu"], _BASE_METRIC["cpu"])
        self.assertEqual(metric["service_web"], _BASE_METRIC["service_web"])
        self.assertEqual(metric["event_log"], _BASE_METRIC["event_log"])


class ChaosModeTests(unittest.TestCase):
    """Chaos mode cycles through all anomaly types deterministically."""

    def test_chaos_cycles_through_all_anomalies(self) -> None:
        """Each seq picks the next anomaly in sorted-key order."""
        keys = sorted(ANOMALY_MODES)
        for seq, expected_key in enumerate(keys * 2):  # two full cycles
            metric = build_metric("node-07", seq, "chaos")
            expected = ANOMALY_MODES[expected_key]
            for field, value in expected.items():
                self.assertEqual(
                    metric.get(field),
                    value,
                    f"seq={seq}, expected anomaly={expected_key}",
                )

    def test_chaos_is_deterministic(self) -> None:
        """Same seq produces identical metric."""
        m1 = build_metric("node-07", 0, "chaos")
        m2 = build_metric("node-07", 0, "chaos")
        self.assertEqual(m1, m2)

    def test_chaos_anomaly_helper_direct(self) -> None:
        """_chaos_anomaly returns the correct anomaly dict per seq."""
        keys = sorted(ANOMALY_MODES)
        for seq, expected_key in enumerate(keys):
            result = _chaos_anomaly(seq)
            self.assertEqual(result, ANOMALY_MODES[expected_key])


if __name__ == "__main__":
    unittest.main()
