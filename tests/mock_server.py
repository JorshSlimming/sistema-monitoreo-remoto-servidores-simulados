import json
import socket


def run_mock_server(host: str = "127.0.0.1", port: int = 5001) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))
        server_socket.listen(1)
        print(f"[mock-server] listening on {host}:{port}")
        conn, address = server_socket.accept()
        with conn:
            print(f"[mock-server] client connected from {address[0]}:{address[1]}")
            raw = conn.recv(4096)
            metric = decode_message(raw.strip())
            print(f"[mock-server] received: {metric}")
            if float(metric.get("cpu", 0)) > 90:
                command = {
                    "type": "command",
                    "command_id": "cmd-mock-001",
                    "action": "reduce_cpu",
                    "reason": "cpu_above_90",
                }
                conn.sendall(encode_message(command))


def encode_message(message: dict) -> bytes:
    return (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")


def decode_message(raw_line: bytes) -> dict:
    message = json.loads(raw_line.decode("utf-8").strip())
    if not isinstance(message, dict):
        raise ValueError("message must be a JSON object")
    return message


if __name__ == "__main__":
    run_mock_server()
