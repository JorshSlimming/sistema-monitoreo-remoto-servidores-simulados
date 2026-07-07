"""PSK challenge-response handshake and symmetric encrypted JSON frames.

This module uses only the Python standard library so the demo remains
reproducible without installing external crypto packages. It provides
confidentiality with an HMAC-SHA256-derived keystream and integrity with
HMAC-SHA256 tags. For production, replace this construction with TLS or
an audited AEAD such as AES-GCM.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import socket
from typing import Any

from shared.auth import get_pre_shared_key


SEPARATOR = b"\n"
NONCE_BYTES = 16
MAX_LINE_BYTES = 131_072


class SecureProtocolError(ValueError):
    """Raised when the secure protocol handshake or frame validation fails."""


def encode_plain(message: dict[str, Any]) -> bytes:
    return (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")


def decode_plain(raw_line: bytes) -> dict[str, Any]:
    message = json.loads(raw_line.decode("utf-8").strip())
    if not isinstance(message, dict):
        raise SecureProtocolError("message must be a JSON object")
    return message


class LineSocket:
    def __init__(self, sock: socket.socket, max_line_bytes: int = MAX_LINE_BYTES) -> None:
        self.sock = sock
        self.max_line_bytes = max_line_bytes
        self._buffer = b""

    def read_line(self) -> bytes:
        while SEPARATOR not in self._buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise EOFError("connection closed")
            self._buffer += chunk
            if len(self._buffer) > self.max_line_bytes:
                self._buffer = b""
                raise SecureProtocolError("message too large")
        line, self._buffer = self._buffer.split(SEPARATOR, 1)
        return line

    def read_plain(self) -> dict[str, Any]:
        return decode_plain(self.read_line())

    def send_plain(self, message: dict[str, Any]) -> None:
        self.sock.sendall(encode_plain(message))


class SecureSocket:
    def __init__(self, sock: socket.socket, session_key: bytes, max_line_bytes: int = MAX_LINE_BYTES) -> None:
        self.sock = sock
        self._lines = LineSocket(sock, max_line_bytes=max_line_bytes)
        self._enc_key = _mac(session_key, b"enc")
        self._mac_key = _mac(session_key, b"mac")
        self._send_seq = 0
        self._recv_seq = 0

    def send_message(self, message: dict[str, Any]) -> None:
        plaintext = json.dumps(message, separators=(",", ":")).encode("utf-8")
        nonce = secrets.token_bytes(NONCE_BYTES)
        ciphertext = _xor_bytes(plaintext, _keystream(self._enc_key, nonce, len(plaintext)))
        seq = self._send_seq
        self._send_seq += 1
        tag = _frame_tag(self._mac_key, seq, nonce, ciphertext)
        frame = {
            "type": "secure",
            "seq": seq,
            "nonce": _b64(nonce),
            "ciphertext": _b64(ciphertext),
            "tag": _b64(tag),
        }
        self.sock.sendall(encode_plain(frame))

    def recv_message(self) -> dict[str, Any]:
        frame = self._lines.read_plain()
        if frame.get("type") != "secure":
            raise SecureProtocolError("expected secure frame")
        seq = frame.get("seq")
        if not isinstance(seq, int) or seq != self._recv_seq:
            raise SecureProtocolError("invalid secure frame sequence")
        nonce = _unb64_field(frame, "nonce")
        ciphertext = _unb64_field(frame, "ciphertext")
        tag = _unb64_field(frame, "tag")
        expected_tag = _frame_tag(self._mac_key, seq, nonce, ciphertext)
        if not hmac.compare_digest(tag, expected_tag):
            raise SecureProtocolError("invalid secure frame tag")
        self._recv_seq += 1
        plaintext = _xor_bytes(ciphertext, _keystream(self._enc_key, nonce, len(ciphertext)))
        return decode_plain(plaintext)


def client_handshake(sock: socket.socket, node_id: str, max_line_bytes: int = MAX_LINE_BYTES) -> SecureSocket:
    psk = get_pre_shared_key(node_id)
    if psk is None:
        raise SecureProtocolError(f"no PSK configured for node {node_id}")
    psk_bytes = psk.encode("utf-8")
    lines = LineSocket(sock, max_line_bytes=max_line_bytes)
    lines.send_plain({"type": "hello", "node_id": node_id})
    challenge = lines.read_plain()
    if challenge.get("type") != "challenge" or challenge.get("node_id") != node_id:
        raise SecureProtocolError("invalid server challenge")
    server_nonce = _unb64_field(challenge, "nonce")
    client_nonce = secrets.token_bytes(NONCE_BYTES)
    proof = _auth_proof(psk_bytes, node_id, server_nonce, client_nonce)
    lines.send_plain(
        {
            "type": "challenge_response",
            "node_id": node_id,
            "client_nonce": _b64(client_nonce),
            "proof": _b64(proof),
        }
    )
    ready = lines.read_plain()
    if ready.get("type") != "ready":
        raise SecureProtocolError(str(ready.get("message", "secure handshake failed")))
    session_key = _session_key(psk_bytes, node_id, server_nonce, client_nonce)
    return SecureSocket(sock, session_key, max_line_bytes=max_line_bytes)


def server_handshake(sock: socket.socket, max_line_bytes: int = MAX_LINE_BYTES) -> tuple[str, SecureSocket]:
    lines = LineSocket(sock, max_line_bytes=max_line_bytes)
    try:
        hello = lines.read_plain()
    except (json.JSONDecodeError, UnicodeDecodeError, SecureProtocolError) as exc:
        lines.send_plain({"type": "error", "code": "INVALID_JSON", "message": "received malformed JSON"})
        raise SecureProtocolError(str(exc)) from exc
    if hello.get("type") != "hello":
        lines.send_plain({"type": "error", "code": "HANDSHAKE_REQUIRED", "message": "expected hello"})
        raise SecureProtocolError("expected hello")
    node_id = hello.get("node_id")
    if not isinstance(node_id, str) or not node_id:
        lines.send_plain({"type": "error", "code": "INVALID_NODE", "message": "invalid node_id"})
        raise SecureProtocolError("invalid node_id")
    psk = get_pre_shared_key(node_id)
    if psk is None:
        lines.send_plain({"type": "error", "code": "AUTH_FAILED", "message": f"unknown node {node_id}"})
        raise SecureProtocolError("unknown node")
    psk_bytes = psk.encode("utf-8")
    server_nonce = secrets.token_bytes(NONCE_BYTES)
    lines.send_plain({"type": "challenge", "node_id": node_id, "nonce": _b64(server_nonce)})
    response = lines.read_plain()
    if response.get("type") != "challenge_response" or response.get("node_id") != node_id:
        lines.send_plain({"type": "error", "code": "AUTH_FAILED", "message": "invalid challenge response"})
        raise SecureProtocolError("invalid challenge response")
    client_nonce = _unb64_field(response, "client_nonce")
    proof = _unb64_field(response, "proof")
    expected = _auth_proof(psk_bytes, node_id, server_nonce, client_nonce)
    if not hmac.compare_digest(proof, expected):
        lines.send_plain({"type": "error", "code": "AUTH_FAILED", "message": "invalid PSK proof"})
        raise SecureProtocolError("invalid PSK proof")
    lines.send_plain({"type": "ready", "node_id": node_id})
    session_key = _session_key(psk_bytes, node_id, server_nonce, client_nonce)
    return node_id, SecureSocket(sock, session_key, max_line_bytes=max_line_bytes)


def _auth_proof(psk: bytes, node_id: str, server_nonce: bytes, client_nonce: bytes) -> bytes:
    return _mac(psk, b"auth|" + node_id.encode("utf-8") + b"|" + server_nonce + b"|" + client_nonce)


def _session_key(psk: bytes, node_id: str, server_nonce: bytes, client_nonce: bytes) -> bytes:
    return _mac(psk, b"session|" + node_id.encode("utf-8") + b"|" + server_nonce + b"|" + client_nonce)


def _frame_tag(mac_key: bytes, seq: int, nonce: bytes, ciphertext: bytes) -> bytes:
    return _mac(mac_key, b"frame|" + str(seq).encode("ascii") + b"|" + nonce + b"|" + ciphertext)


def _mac(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    output = bytearray()
    counter = 0
    while len(output) < length:
        block = _mac(key, nonce + counter.to_bytes(8, "big"))
        output.extend(block)
        counter += 1
    return bytes(output[:length])


def _xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right))


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _unb64_field(message: dict[str, Any], field: str) -> bytes:
    value = message.get(field)
    if not isinstance(value, str):
        raise SecureProtocolError(f"missing {field}")
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except Exception as exc:
        raise SecureProtocolError(f"invalid base64 field {field}") from exc
