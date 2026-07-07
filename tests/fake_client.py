import argparse
import json
import socket
import time
import base64
import sys
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, '/home/maxi/codigo/sistema-monitoreo-remoto-servidores-simulados')

from server.auth_handler import (
    encrypt_message,
    decrypt_message,
    decode_encrypted_message,
    encode_encrypted_message,
    load_psk_config,
    get_node_psk,
)


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
    # Load PSK configuration
    psk_config = load_psk_config()
    psk = get_node_psk(node_id, psk_config)
    
    if psk is None:
        print(f"[fake-client] error: no PSK configured for {node_id}")
        return
    
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.settimeout(2)
        
        # Step 1: Send auth_init with node_id
        auth_init = {"type": "auth_init", "node_id": node_id}
        print(f"[fake-client] sending auth_init: {node_id}")
        sock.sendall(encode_message(auth_init))
        
        # Step 2: Receive encrypted challenge
        try:
            challenge_data = sock.recv(4096)
            if not challenge_data:
                print("[fake-client] server closed connection during handshake")
                return
        except socket.timeout:
            print("[fake-client] timeout waiting for challenge")
            return
        
        try:
            challenge_line = challenge_data.decode("utf-8").strip()
            ciphertext, nonce, salt = decode_encrypted_message(challenge_line)
            challenge_msg = decrypt_message(ciphertext, nonce, salt, psk)
            print(f"[fake-client] received challenge: {challenge_msg.get('type')}")
            
        except Exception as e:
            print(f"[fake-client] error decrypting challenge: {e}")
            return
        
        # Step 3: Send encrypted response
        response = {"type": "auth_response", "acknowledged": True}
        try:
            encrypted_response = encrypt_message(response, psk)
            response_line = encode_encrypted_message(*encrypted_response)
            sock.sendall((response_line + "\n").encode("utf-8"))
            print(f"[fake-client] sent encrypted auth response")
        except Exception as e:
            print(f"[fake-client] error sending encrypted response: {e}")
            return
        
        # Step 4: Send metric after successful authentication (ENCRYPTED)
        time.sleep(0.2)
        metric = build_metric(node_id, 1, mode)
        print(f"[fake-client] sending encrypted metric mode={mode}")
        try:
            encrypted_metric = encrypt_message(metric, psk)
            metric_line = encode_encrypted_message(*encrypted_metric)
            sock.sendall((metric_line + "\n").encode("utf-8"))
        except Exception as e:
            print(f"[fake-client] error sending encrypted metric: {e}")
            return

        try:
            response = sock.recv(4096)
        except (socket.timeout, ConnectionResetError):
            print("[fake-client] no response received")
            return

        for raw_line in response.split(b"\n"):
            if not raw_line:
                continue
            try:
                # Try to decrypt the response
                encrypted_line = raw_line.decode("utf-8").strip()
                ciphertext, nonce, salt = decode_encrypted_message(encrypted_line)
                message = decrypt_message(ciphertext, nonce, salt, psk)
            except Exception:
                # If decryption fails, try plain JSON
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
                }
                time.sleep(0.2)
                try:
                    encrypted_ack = encrypt_message(ack, psk)
                    ack_line = encode_encrypted_message(*encrypted_ack)
                    sock.sendall((ack_line + "\n").encode("utf-8"))
                except Exception as e:
                    print(f"[fake-client] error sending encrypted ack: {e}")
                    return
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
