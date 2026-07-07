"""Tests for PSK handshake and encrypted frames."""

import socket
import threading
import unittest

from shared.secure_channel import (
    SecureProtocolError,
    client_handshake,
    decode_plain,
    encode_plain,
    server_handshake,
)


class SecureChannelTests(unittest.TestCase):
    def test_psk_handshake_encrypts_and_decrypts_messages(self) -> None:
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        result: dict[str, object] = {}

        def server_side() -> None:
            node_id, secure = server_handshake(right)
            result["node_id"] = node_id
            result["message"] = secure.recv_message()
            secure.send_message({"type": "command", "command_id": 1, "action": "reduce_cpu"})

        thread = threading.Thread(target=server_side)
        thread.start()
        secure = client_handshake(left, "node-01")
        secure.send_message({"type": "metric", "node_id": "node-01", "seq": 1})
        command = secure.recv_message()
        thread.join(timeout=3)

        self.assertEqual(result["node_id"], "node-01")
        self.assertEqual(result["message"], {"type": "metric", "node_id": "node-01", "seq": 1})
        self.assertEqual(command["type"], "command")
        self.assertEqual(command["action"], "reduce_cpu")

    def test_last_configured_demo_node_can_handshake(self) -> None:
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        result: dict[str, str] = {}

        def server_side() -> None:
            node_id, _secure = server_handshake(right)
            result["node_id"] = node_id

        thread = threading.Thread(target=server_side)
        thread.start()
        secure = client_handshake(left, "node-32")
        secure.sock.close()
        thread.join(timeout=3)

        self.assertEqual(result["node_id"], "node-32")

    def test_unknown_node_cannot_start_handshake(self) -> None:
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)

        left.sendall(encode_plain({"type": "hello", "node_id": "unknown-node"}))
        with self.assertRaises(SecureProtocolError):
            server_handshake(right)
        response = decode_plain(left.recv(4096))

        self.assertEqual(response["type"], "error")
        self.assertEqual(response["code"], "AUTH_FAILED")


if __name__ == "__main__":
    unittest.main()
