import argparse
import json
from pathlib import Path
import socket
import sys
import time
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.auth import get_token
from shared.secure_channel import SecureProtocolError, SecureSocket, client_handshake


def build_metric(node_id: str, seq: int, mode: str) -> dict[str, Any]:
    token = get_token(node_id) or "unknown"
    metric = {
        "type": "metric",
        "node_id": node_id,
        "seq": seq,
        "cpu": 35.0,
        "ram": 45.0,
        "latency_ms": 40,
        "service_web": "ok",
        "event_log": "normal",
        "token": token,
    }

    if mode == "high-cpu":
        metric["cpu"] = 95.0
    elif mode == "high-ram":
        metric["ram"] = 94.0
    elif mode == "high-latency":
        metric["latency_ms"] = 350
    elif mode == "service-failure":
        metric["service_web"] = "falla"
    elif mode == "failed-event":
        metric["event_log"] = "backup fallido"
    return metric


def _drain_socket(secure: SecureSocket, node_id: str) -> None:
    try:
        while True:
            message = secure.recv_message()
            print(f"[fake-client] received: {message}")
            if message.get("type") == "command":
                ack = {
                    "type": "ack",
                    "node_id": node_id,
                    "command_id": message["command_id"],
                    "status": "applied",
                    "token": get_token(node_id) or "unknown",
                }
                time.sleep(0.2)
                secure.send_message(ack)
                print(f"[fake-client] ack sent for {message['command_id']}")
    except socket.timeout:
        pass
    except (ConnectionResetError, EOFError, SecureProtocolError):
        raise


def run_client(
    host: str,
    port: int,
    node_id: str,
    mode: str,
    interval: float,
    max_metrics: int = 0,
) -> None:
    print(f"[fake-client] starting as {node_id} (mode={mode}, interval={interval}s)")
    seq = 0
    while True:
        try:
            with socket.create_connection((host, port), timeout=5) as sock:
                sock.settimeout(2)
                print(f"[fake-client] connected to {host}:{port}")
                secure = client_handshake(sock, node_id)
                print(f"[fake-client] secure channel established for {node_id}")
                while True:
                    seq += 1
                    metric = build_metric(node_id, seq, mode)
                    print(f"[fake-client] sending metric seq={seq} mode={mode}")
                    secure.send_message(metric)
                    _drain_socket(secure, node_id)
                    if max_metrics > 0 and seq >= max_metrics:
                        return
                    time.sleep(interval)
        except (ConnectionRefusedError, ConnectionResetError, OSError, socket.timeout, SecureProtocolError) as exc:
            if max_metrics > 0 and seq >= max_metrics:
                return
            print(f"[fake-client] connection lost ({exc}); reconnecting in 5s...")
            time.sleep(5)


def encode_message(message: dict[str, Any]) -> bytes:
    return (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")


def decode_message(raw_line: bytes) -> dict[str, Any]:
    message = json.loads(raw_line.decode("utf-8").strip())
    if not isinstance(message, dict):
        raise ValueError("message must be a JSON object")
    return message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fake client for integration tests")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--node-id", default="node-01")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between metrics")
    parser.add_argument(
        "--max-metrics",
        type=int,
        default=0,
        help="Stop after this many metrics; 0 means run persistently",
    )
    parser.add_argument(
        "--mode",
        choices=[
            "normal",
            "high-cpu",
            "high-ram",
            "high-latency",
            "service-failure",
            "failed-event",
        ],
        default="normal",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_client(args.host, args.port, args.node_id, args.mode, args.interval, args.max_metrics)
