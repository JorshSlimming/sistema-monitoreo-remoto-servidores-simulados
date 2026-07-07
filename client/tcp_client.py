"""Real persistent TCP client for the monitoring system.

Sends periodic metrics, receives commands, and sends ACKs.
Reconnects automatically every 5 seconds on disconnect.
"""

import argparse
import json
import socket
import time
from dataclasses import dataclass
from typing import Any

from shared.auth import get_token

ANOMALY_MODES: dict[str, dict[str, Any]] = {
    "high-cpu": {"cpu": 95.0},
    "high-ram": {"ram": 94.0},
    "high-latency": {"latency_ms": 350},
    "service-failure": {"service_web": "falla"},
    "failed-event": {"event_log": "backup fallido"},
}

_BASE_METRIC: dict[str, Any] = {
    "cpu": 35.0,
    "ram": 45.0,
    "latency_ms": 40,
    "service_web": "ok",
    "event_log": "normal",
}

PROGRESSIVE_FACTOR = 0.35


@dataclass
class ClientState:
    mode: str
    anomaly_active: bool = True
    mitigation_active: bool = False
    mitigation_type: str | None = None
    last_command: dict[str, Any] | None = None
    cpu: float | None = None
    ram: float | None = None
    latency_ms: float | None = None
    service_web: str | None = None
    event_log: str | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "anomaly_active": self.anomaly_active,
            "mitigation_active": self.mitigation_active,
            "mitigation_type": self.mitigation_type,
            "cpu": self.cpu,
            "ram": self.ram,
            "latency_ms": self.latency_ms,
            "service_web": self.service_web,
            "event_log": self.event_log,
        }


def build_initial_state(mode: str) -> dict[str, Any]:
    """Compatibility helper for dict-based callers/tests from origin/main."""
    state = dict(_BASE_METRIC)
    if mode in ANOMALY_MODES:
        state.update(ANOMALY_MODES[mode])
    return state


def apply_command(state: dict[str, Any], action: str) -> None:
    """Compatibility helper for dict-based callers/tests from origin/main."""
    if action == "reduce_cpu":
        state["cpu"] = _BASE_METRIC["cpu"]
    elif action == "reduce_ram":
        state["ram"] = _BASE_METRIC["ram"]
    elif action == "fix_latency":
        state["latency_ms"] = _BASE_METRIC["latency_ms"]
    elif action == "restart_service":
        state["service_web"] = _BASE_METRIC["service_web"]
    elif action == "normalize_node":
        state.update(_BASE_METRIC)


def _progressive_tick(current: float, target: float) -> float:
    return current + (target - current) * PROGRESSIVE_FACTOR


def _progressive_step(state: ClientState) -> None:
    base = _BASE_METRIC
    if state.cpu is not None:
        state.cpu = _progressive_tick(state.cpu, base["cpu"])
        if abs(state.cpu - base["cpu"]) < 1:
            state.cpu = None
    if state.ram is not None:
        state.ram = _progressive_tick(state.ram, base["ram"])
        if abs(state.ram - base["ram"]) < 1:
            state.ram = None
    if state.latency_ms is not None:
        state.latency_ms = _progressive_tick(state.latency_ms, base["latency_ms"])
        if abs(state.latency_ms - base["latency_ms"]) < 1:
            state.latency_ms = None
    if (
        state.cpu is None
        and state.ram is None
        and state.latency_ms is None
        and state.service_web in (None, base["service_web"])
        and state.event_log in (None, base["event_log"])
    ):
        state.mitigation_active = False
        state.mitigation_type = None


def _apply_command(action: str, state: ClientState) -> dict[str, Any]:
    before = state.snapshot()
    state.mitigation_active = True
    state.mitigation_type = action
    state.last_command = {"action": action, "timestamp": time.time()}

    mode = state.mode
    if action == "reduce_cpu":
        state.cpu = ANOMALY_MODES.get(mode, {}).get("cpu", _BASE_METRIC["cpu"])
    elif action == "reduce_ram":
        state.ram = ANOMALY_MODES.get(mode, {}).get("ram", _BASE_METRIC["ram"])
    elif action == "fix_latency":
        state.latency_ms = ANOMALY_MODES.get(mode, {}).get("latency_ms", _BASE_METRIC["latency_ms"])
    elif action == "restart_service":
        state.service_web = "ok"
    elif action == "normalize_node":
        state.anomaly_active = False
        state.cpu = None
        state.ram = None
        state.latency_ms = None
        state.service_web = "ok"
        state.event_log = "normal"
    return before


def build_metric(
    node_id: str,
    seq: int,
    mode: str,
    state: ClientState | dict[str, Any] | None = None,
) -> dict[str, Any]:
    token = get_token(node_id)
    if token is None:
        print(f"[client] WARNING: unknown node_id {node_id}, using fallback token")
        token = "unknown"
    metric: dict[str, Any] = {
        "type": "metric",
        "node_id": node_id,
        "seq": seq,
        **_BASE_METRIC,
        "token": token,
    }
    if mode in ANOMALY_MODES and (state is None or not isinstance(state, ClientState) or state.anomaly_active):
        metric.update(ANOMALY_MODES[mode])
    if isinstance(state, dict):
        metric.update(state)
        return metric
    if isinstance(state, ClientState):
        if state.cpu is not None:
            metric["cpu"] = state.cpu
        if state.ram is not None:
            metric["ram"] = state.ram
        if state.latency_ms is not None:
            metric["latency_ms"] = state.latency_ms
        if state.service_web is not None:
            metric["service_web"] = state.service_web
        if state.event_log is not None:
            metric["event_log"] = state.event_log
        metric["scenario"] = state.mode
        metric["anomaly_active"] = state.anomaly_active
        metric["mitigation_active"] = state.mitigation_active
        metric["mitigation_type"] = state.mitigation_type or ""
        if state.last_command:
            metric["last_command"] = state.last_command.get("action", "")
    return metric


def encode_message(message: dict[str, Any]) -> bytes:
    return (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")


def decode_message(raw_line: bytes) -> dict[str, Any]:
    message = json.loads(raw_line.decode("utf-8").strip())
    if not isinstance(message, dict):
        raise ValueError("message must be a JSON object")
    return message


def _drain_socket(
    sock: socket.socket,
    node_id: str,
    client_state: ClientState | None = None,
) -> None:
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            for raw_line in chunk.split(b"\n"):
                if not raw_line:
                    continue
                try:
                    message = decode_message(raw_line)
                except (json.JSONDecodeError, ValueError) as exc:
                    print(f"[client] decode error: {exc}")
                    continue
                msg_type = message.get("type")
                if msg_type == "command":
                    action = str(message.get("action", ""))
                    ack: dict[str, Any] = {
                        "type": "ack",
                        "node_id": node_id,
                        "command_id": message["command_id"],
                        "status": "applied",
                        "token": get_token(node_id) or "unknown",
                        "command": action,
                        "timestamp": time.time(),
                        "message": f"ack {action}",
                    }
                    if client_state is not None:
                        before = _apply_command(action, client_state)
                        ack["before"] = before
                        ack["after"] = client_state.snapshot()
                    sock.sendall(encode_message(ack))
                    print(f"[client] ack sent for command {message['command_id']}: {action or '?'}")
                elif msg_type == "error":
                    print(f"[client] server error: {message}")
                else:
                    print(f"[client] received: {message}")
    except socket.timeout:
        pass
    except ConnectionResetError:
        raise


def run_client(host: str, port: int, node_id: str, interval: float, mode: str) -> None:
    print(f"[client] starting as {node_id} (mode={mode}, interval={interval}s)")
    state = ClientState(mode=mode, anomaly_active=(mode != "normal"))
    seq = 0
    while True:
        try:
            with socket.create_connection((host, port), timeout=5) as sock:
                sock.settimeout(1.0)
                print(f"[client] connected to {host}:{port}")
                while True:
                    _progressive_step(state)
                    metric = build_metric(node_id, seq, mode, state)
                    sock.sendall(encode_message(metric))
                    print(
                        f"[client] sent metric seq={seq} "
                        f"cpu={metric['cpu']} ram={metric['ram']} "
                        f"latency={metric['latency_ms']} service={metric['service_web']}"
                    )
                    seq += 1
                    _drain_socket(sock, node_id, state)
                    time.sleep(interval)
        except (ConnectionRefusedError, ConnectionResetError, OSError, socket.timeout) as exc:
            print(f"[client] connection lost ({exc}); reconnecting in 5s...")
            time.sleep(5)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Persistent monitoring client")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=5000, help="Server port")
    parser.add_argument("--node-id", default="node-01", help="Node identifier")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between metrics")
    parser.add_argument(
        "--mode",
        choices=["normal", *sorted(ANOMALY_MODES)],
        default="normal",
        help="Anomaly mode for demo",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_client(args.host, args.port, args.node_id, args.interval, args.mode)


if __name__ == "__main__":
    main()
