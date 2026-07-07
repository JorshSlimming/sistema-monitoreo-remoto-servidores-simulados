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


def _drain_socket(sock: socket.socket, node_id: str) -> None:
    """Read and handle all available messages from the socket (non-blocking via timeout)."""
    try:
        while True:
            response = sock.recv(4096)
            if not response:
                break
            for raw_line in response.split(b"\n"):
                if not raw_line:
                    continue
                try:
                    message = decode_message(raw_line)
                except Exception:
                    continue
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
                    sock.sendall(encode_message(ack))
                    print(f"[fake-client] ack sent for {message['command_id']}")
    except socket.timeout:
        pass
    except ConnectionResetError:
        raise


def run_client(host: str, port: int, node_id: str, mode: str, interval: float) -> None:
    print(f"[fake-client] starting as {node_id} (mode={mode}, interval={interval}s)")
    seq = 0
    while True:
        try:
            with socket.create_connection((host, port), timeout=5) as sock:
                sock.settimeout(2)
                print(f"[fake-client] connected to {host}:{port}")
                while True:
                    seq += 1
                    metric = build_metric(node_id, seq, mode)
                    print(f"[fake-client] sending metric seq={seq} mode={mode}")
                    sock.sendall(encode_message(metric))
                    _drain_socket(sock, node_id)
                    time.sleep(interval)
        except (ConnectionRefusedError, ConnectionResetError, OSError, socket.timeout) as exc:
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
    parser = argparse.ArgumentParser(description="Fake client for Rol A initial base")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--node-id", default="node-01")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between metrics")
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
    run_client(args.host, args.port, args.node_id, args.mode, args.interval)
