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


def run_client(host: str, port: int) -> None:
    print("Corriendo test de JSON malformado")
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.settimeout(2)
        for message in messages:
            sock.sendall(message)

            try:
                response = sock.recv(4096)
            except (socket.timeout, ConnectionResetError):
                print(f"TEST NO PASADO | Mensaje : {message} | Razon: No hubo respuesta")
                return

            for raw_line in response.split(b"\n"):
                if not raw_line:
                    continue
                message = decode_message(raw_line)
                print(f"[fake-client] received: {message}")
                if message.get("type") == "error":
                    if message.get("code") == "INVALID_JSON":
                        print("Test pasado exitosamente") 
                print(message)


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

messages = [b"HJDASDJAHADADA", b""]

if __name__ == "__main__":
    args = parse_args()
    run_client(args.host, args.port)
