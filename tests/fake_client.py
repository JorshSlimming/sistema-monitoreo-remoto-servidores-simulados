import argparse
import json
import socket
import time
from typing import Any


TOKENS = {
    "node-01": "node-01-secret",
    "node-02": "node-02-secret",
    "node-03": "node-03-secret",
}


def build_metric(node_id: str, seq: int, mode: str) -> dict[str, Any]:
    metric = {
        "type": "metric",
        "node_id": node_id,
        "seq": seq,
        "cpu": 35.0,
        "ram": 45.0,
        "latency_ms": 40,
        "service_web": "ok",
        "event_log": "normal",
        "token": TOKENS.get(node_id, "unknown-token"),
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


def run_client(host: str, port: int, node_id: str, mode: str) -> None:
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.settimeout(2)
        metric = build_metric(node_id, 1, mode)
        print(f"[fake-client] sending metric mode={mode}")
        sock.sendall(encode_message(metric))

        try:
            response = sock.recv(4096)
        except (socket.timeout, ConnectionResetError):
            print("[fake-client] no response received")
            return

        for raw_line in response.split(b"\n"):
            if not raw_line:
                continue
            message = decode_message(raw_line)
            print(f"[fake-client] received: {message}")
            if message.get("type") == "command":
                ack = {
                    "type": "ack",
                    "node_id": node_id,
                    "command_id": message["command_id"],
                    "status": "applied",
                    "token": TOKENS.get(node_id, "unknown-token"),
                }
                time.sleep(0.2)
                sock.sendall(encode_message(ack))
                print(f"[fake-client] ack sent for {message['command_id']}")


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
    run_client(args.host, args.port, args.node_id, args.mode)
