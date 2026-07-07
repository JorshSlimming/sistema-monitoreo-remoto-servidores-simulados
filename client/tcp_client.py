"""Real persistent TCP client for the monitoring system.

Sends periodic metrics, receives commands, and sends ACKs.
Reconnects automatically every 5 seconds on disconnect.
"""

import argparse
import json
import socket
import time
from typing import Any

from shared.auth import get_token

# ponytail: static modes; extend with config file or CLI if needed
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


def build_metric(node_id: str, seq: int, mode: str) -> dict[str, Any]:
    """Build a metric dict for *node_id* with sequence *seq* in *mode*."""
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
    if mode in ANOMALY_MODES:
        metric.update(ANOMALY_MODES[mode])
    return metric


def encode_message(message: dict[str, Any]) -> bytes:
    """Encode *message* as newline-terminated JSON bytes."""
    return (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")


def decode_message(raw_line: bytes) -> dict[str, Any]:
    """Decode a single newline-terminated JSON line."""
    message = json.loads(raw_line.decode("utf-8").strip())
    if not isinstance(message, dict):
        raise ValueError("message must be a JSON object")
    return message


def _drain_socket(sock: socket.socket, node_id: str) -> None:
    """Read and process all pending messages from the server."""
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
                    ack = {
                        "type": "ack",
                        "node_id": node_id,
                        "command_id": message["command_id"],
                        "status": "applied",
                        "token": get_token(node_id) or "unknown",
                    }
                    sock.sendall(encode_message(ack))
                    print(
                        f"[client] ack sent for command {message['command_id']}: "
                        f"{message.get('action', '?')}"
                    )
                elif msg_type == "error":
                    print(f"[client] server error: {message}")
                else:
                    print(f"[client] received: {message}")
    except socket.timeout:
        pass  # expected — no more messages pending
    except ConnectionResetError:
        raise


def run_client(
    host: str,
    port: int,
    node_id: str,
    interval: float,
    mode: str,
) -> None:
    """Run the persistent client loop.

    Connects to *host*:*port*, sends a metric every *interval* seconds,
    processes incoming commands, and reconnects every 5 seconds on failure.
    """
    print(f"[client] starting as {node_id} (mode={mode}, interval={interval}s)")
    seq = 0
    while True:
        try:
            with socket.create_connection((host, port), timeout=5) as sock:
                sock.settimeout(1.0)  # short drain timeout
                print(f"[client] connected to {host}:{port}")
                while True:
                    metric = build_metric(node_id, seq, mode)
                    sock.sendall(encode_message(metric))
                    print(f"[client] sent metric seq={seq} mode={mode}")
                    seq += 1
                    _drain_socket(sock, node_id)
                    time.sleep(interval)
        except (ConnectionRefusedError, ConnectionResetError, OSError, socket.timeout) as exc:
            print(f"[client] connection lost ({exc}); reconnecting in 5s...")
            time.sleep(5)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Persistent monitoring client")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=5000, help="Server port")
    parser.add_argument("--node-id", default="node-01", help="Node identifier")
    parser.add_argument(
        "--interval", type=float, default=5.0, help="Seconds between metrics"
    )
    parser.add_argument(
        "--mode",
        choices=["normal", *sorted(ANOMALY_MODES)],
        default="normal",
        help="Anomaly mode for demo",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for ``python -m client.tcp_client``."""
    args = parse_args()
    run_client(args.host, args.port, args.node_id, args.interval, args.mode)


if __name__ == "__main__":
    main()
