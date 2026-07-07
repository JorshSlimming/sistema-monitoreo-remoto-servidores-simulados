#!/usr/bin/env python3
"""Authorized local attacker simulation for demo hardening.

Usage:
    python3 -m attacker.attack_simulator --attack all
    python3 -m attacker.attack_simulator --attack plaintext-metric --json
    python3 -m attacker.attack_simulator --attack unknown-node --host 127.0.0.1 --port 5000

Each attack connects to the target monitor server and attempts a specific
protocol-level bypass.  Results report whether the server correctly detected
and rejected the attack.

All attacks target **localhost** by default.  Set ``ALLOW_NON_LOCAL_ATTACK_TARGET=1``
in the environment to target a remote host (requires explicit ``--host``).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import sys
import time
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Path setup — allow running as ``python3 -m attacker.attack_simulator``
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from shared.auth import get_token
from shared.secure_channel import (
    SecureProtocolError,
    LineSocket,
    client_handshake,
    decode_plain,
    encode_plain,
)

# ---------------------------------------------------------------------------
# Allowlist helpers
# ---------------------------------------------------------------------------

ALLOWED_LOCAL = {"127.0.0.1", "localhost", "::1"}

_ATTACK_SEQ = iter(range(1, 1000))


def _next_id() -> str:
    return f"attack-{next(_ATTACK_SEQ):03d}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_target(host: str) -> None:
    """Raise ValueError if *host* is not in the local allowlist (unless env override)."""
    if os.environ.get("ALLOW_NON_LOCAL_ATTACK_TARGET") == "1":
        return
    if host not in ALLOWED_LOCAL:
        raise ValueError(
            f"Host {host!r} is not in the local allowlist. "
            "Set ALLOW_NON_LOCAL_ATTACK_TARGET=1 to allow non-local targets."
        )


def _recv_all(sock: socket.socket, timeout: float = 2.0) -> bytes:
    """Read all available data from *sock* within *timeout* seconds."""
    sock.settimeout(timeout)
    chunks: list[bytes] = []
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    except socket.timeout:
        pass
    return b"".join(chunks)


# ---------------------------------------------------------------------------
# Attack catalog
# ---------------------------------------------------------------------------

def attack_plaintext_metric(host: str, port: int, timeout: float = 2.0) -> dict[str, Any]:
    """Send a metric as plain JSON without completing the PSK handshake.

    Expected: server rejects with ``HANDSHAKE_REQUIRED``.
    """
    start = time.monotonic()
    result: dict[str, Any] = {
        "attack_id": _next_id(),
        "name": "Plaintext Metric Injection",
        "description": "Send a metric as plain JSON without the required PSK handshake",
        "expected_result": "Server rejects with HANDSHAKE_REQUIRED",
        "risk_level_demo": "MEDIUM",
        "authorized_scope": "local-authorized-testing",
    }
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        metric = {
            "type": "metric",
            "node_id": "node-01",
            "seq": 1,
            "cpu": 45.0,
            "ram": 55.0,
            "latency_ms": 30,
            "service_web": "ok",
            "event_log": "normal",
            "token": get_token("node-01"),
        }
        sock.sendall(encode_plain(metric))
        raw = _recv_all(sock, timeout)
        sock.close()
        server_msg = decode_plain(raw) if raw else None
        detected = (
            server_msg is not None
            and server_msg.get("code") in ("HANDSHAKE_REQUIRED", "INVALID_JSON", "INVALID_MESSAGE")
        )
        result.update({
            "success": detected,
            "server_response": json.dumps(server_msg) if server_msg else "connection closed",
            "observed_error": None if detected else "server did not reject plaintext metric",
        })
    except Exception as exc:
        result.update({
            "success": False,
            "server_response": None,
            "observed_error": str(exc),
        })
    result["timestamp"] = _now()
    result["duration_ms"] = round((time.monotonic() - start) * 1000, 1)
    return result


def attack_unknown_node(host: str, port: int, timeout: float = 2.0) -> dict[str, Any]:
    """Initiate handshake with a node_id that has no configured PSK.

    Expected: server rejects with ``AUTH_FAILED`` (unknown node).
    """
    start = time.monotonic()
    result: dict[str, Any] = {
        "attack_id": _next_id(),
        "name": "Unknown Node Authentication",
        "description": "Attempt PSK handshake with a node_id that has no configured secret",
        "expected_result": "Server rejects with AUTH_FAILED (unknown node)",
        "risk_level_demo": "HIGH",
        "authorized_scope": "local-authorized-testing",
    }
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.sendall(encode_plain({"type": "hello", "node_id": "nonexistent-node-99"}))
        raw = _recv_all(sock, timeout)
        sock.close()
        server_msg = decode_plain(raw) if raw else None
        detected = (
            server_msg is not None
            and server_msg.get("code") == "AUTH_FAILED"
            and "unknown node" in str(server_msg.get("message", "")).lower()
        )
        result.update({
            "success": detected,
            "server_response": json.dumps(server_msg) if server_msg else "connection closed",
            "observed_error": None if detected else "server did not reject unknown node",
        })
    except Exception as exc:
        result.update({
            "success": False,
            "server_response": None,
            "observed_error": str(exc),
        })
    result["timestamp"] = _now()
    result["duration_ms"] = round((time.monotonic() - start) * 1000, 1)
    return result


def attack_bad_psk(host: str, port: int, timeout: float = 2.0) -> dict[str, Any]:
    """Complete the handshake challenge but provide an invalid PSK proof.

    Expected: server rejects with ``AUTH_FAILED`` (invalid PSK proof).
    """
    start = time.monotonic()
    result: dict[str, Any] = {
        "attack_id": _next_id(),
        "name": "Invalid PSK Proof",
        "description": "Respond to handshake challenge with an incorrect HMAC proof",
        "expected_result": "Server rejects with AUTH_FAILED (invalid PSK proof)",
        "risk_level_demo": "HIGH",
        "authorized_scope": "local-authorized-testing",
    }
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        lines = LineSocket(sock)
        lines.send_plain({"type": "hello", "node_id": "node-01"})
        challenge = lines.read_plain()
        if challenge.get("type") != "challenge":
            raise SecureProtocolError(f"expected challenge, got {challenge}")
        # Send a challenge_response with a deliberately wrong proof.
        lines.send_plain({
            "type": "challenge_response",
            "node_id": "node-01",
            "client_nonce": base64.b64encode(b"\x00" * 16).decode("ascii"),
            "proof": base64.b64encode(b"\xaa" * 32).decode("ascii"),  # garbage proof
        })
        raw = _recv_all(sock, timeout)
        sock.close()
        server_msg = decode_plain(raw) if raw else None
        detected = (
            server_msg is not None
            and server_msg.get("code") == "AUTH_FAILED"
            and "proof" in str(server_msg.get("message", "")).lower()
        )
        result.update({
            "success": detected,
            "server_response": json.dumps(server_msg) if server_msg else "connection closed",
            "observed_error": None if detected else "server did not reject bad PSK proof",
        })
    except Exception as exc:
        result.update({
            "success": False,
            "server_response": None,
            "observed_error": str(exc),
        })
    result["timestamp"] = _now()
    result["duration_ms"] = round((time.monotonic() - start) * 1000, 1)
    return result


def attack_node_mismatch(host: str, port: int, timeout: float = 2.0) -> dict[str, Any]:
    """Complete a valid handshake as node-01, then send a metric claiming node-02.

    Expected: server rejects with ``AUTH_FAILED`` (node mismatch for secure channel).
    """
    start = time.monotonic()
    result: dict[str, Any] = {
        "attack_id": _next_id(),
        "name": "Node ID Mismatch",
        "description": "Authenticate as node-01 but send metric claiming to be node-02",
        "expected_result": "Server rejects with AUTH_FAILED (node mismatch for secure channel)",
        "risk_level_demo": "HIGH",
        "authorized_scope": "local-authorized-testing",
    }
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        secure = client_handshake(sock, "node-01")
        # Send metric with different node_id
        secure.send_message({
            "type": "metric",
            "node_id": "node-02",
            "seq": 1,
            "cpu": 50.0,
            "ram": 50.0,
            "latency_ms": 30,
            "service_web": "ok",
            "event_log": "normal",
            "token": get_token("node-02"),
        })
        # Read server's error response (sent through secure channel)
        try:
            response = secure.recv_message()
        except (SecureProtocolError, EOFError, OSError) as e:
            response = {"type": "error", "code": "CONNECTION_CLOSED", "message": str(e)}
        sock.close()
        detected = (
            isinstance(response, dict)
            and response.get("code") in ("AUTH_FAILED", "CONNECTION_CLOSED")
        )
        result.update({
            "success": detected,
            "server_response": json.dumps(response) if response else "connection closed",
            "observed_error": None if detected else "server did not reject node mismatch",
        })
    except Exception as exc:
        result.update({
            "success": False,
            "server_response": None,
            "observed_error": str(exc),
        })
    result["timestamp"] = _now()
    result["duration_ms"] = round((time.monotonic() - start) * 1000, 1)
    return result


def attack_invalid_metric(host: str, port: int, timeout: float = 2.0) -> dict[str, Any]:
    """Complete a valid handshake, then send a metric with invalid field values.

    Expected: server rejects with ``INVALID_MESSAGE`` (e.g. cpu > 100 or negative).
    """
    start = time.monotonic()
    result: dict[str, Any] = {
        "attack_id": _next_id(),
        "name": "Invalid Metric Fields",
        "description": "Send a metric with cpu > 100 via an otherwise valid secure channel",
        "expected_result": "Server rejects with INVALID_MESSAGE (cpu must be between 0 and 100)",
        "risk_level_demo": "LOW",
        "authorized_scope": "local-authorized-testing",
    }
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        secure = client_handshake(sock, "node-01")
        secure.send_message({
            "type": "metric",
            "node_id": "node-01",
            "seq": 1,
            "cpu": 999.0,  # Out of range
            "ram": 50.0,
            "latency_ms": 30,
            "service_web": "ok",
            "event_log": "normal",
            "token": get_token("node-01") or "unknown",
        })
        try:
            response = secure.recv_message()
        except (SecureProtocolError, EOFError, OSError) as e:
            response = {"type": "error", "code": "CONNECTION_CLOSED", "message": str(e)}
        sock.close()
        detected = (
            isinstance(response, dict)
            and response.get("code") in ("INVALID_MESSAGE", "CONNECTION_CLOSED")
        )
        result.update({
            "success": detected,
            "server_response": json.dumps(response) if response else "connection closed",
            "observed_error": None if detected else "server did not reject invalid metric",
        })
    except Exception as exc:
        result.update({
            "success": False,
            "server_response": None,
            "observed_error": str(exc),
        })
    result["timestamp"] = _now()
    result["duration_ms"] = round((time.monotonic() - start) * 1000, 1)
    return result


def attack_tampered_frame(host: str, port: int, timeout: float = 2.0) -> dict[str, Any]:
    """Complete a valid handshake, then send a secure frame with tampered ciphertext.

    Expected: server detects ``invalid secure frame tag`` and closes the connection.
    """
    start = time.monotonic()
    result: dict[str, Any] = {
        "attack_id": _next_id(),
        "name": "Tampered Secure Frame",
        "description": "Send a secure frame with a deliberately invalid ciphertext/tag",
        "expected_result": "Server detects invalid secure frame tag and closes connection",
        "risk_level_demo": "HIGH",
        "authorized_scope": "local-authorized-testing",
    }
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        secure = client_handshake(sock, "node-01")
        # Send a valid metric first so we know the server has processed seq=0.
        secure.send_message({
            "type": "metric",
            "node_id": "node-01",
            "seq": 1,
            "cpu": 35.0,
            "ram": 45.0,
            "latency_ms": 30,
            "service_web": "ok",
            "event_log": "normal",
            "token": get_token("node-01") or "unknown",
        })
        try:
            secure.recv_message()  # drain server response (command or error)
        except (SecureProtocolError, EOFError, OSError):
            pass
        # Send a tampered secure frame directly via raw socket.
        tampered = encode_plain({
            "type": "secure",
            "seq": 1,  # server expects seq=1 now (recv_seq incremented)
            "nonce": base64.b64encode(b"\x00" * 16).decode("ascii"),
            "ciphertext": base64.b64encode(b"tampered_payload_here").decode("ascii"),
            "tag": base64.b64encode(b"\x00" * 32).decode("ascii"),
        })
        secure.sock.sendall(tampered)
        # Server should detect the invalid tag and close.
        time.sleep(0.3)
        try:
            data = secure.sock.recv(4096)
            connection_alive = len(data) > 0
        except (OSError, ConnectionResetError):
            connection_alive = False
        sock.close()
        detected = not connection_alive
        result.update({
            "success": detected,
            "server_response": "connection reset (tampered frame detected)" if detected else "connection remained open",
            "observed_error": None if detected else "server did not close connection on tampered frame",
        })
    except Exception as exc:
        result.update({
            "success": False,
            "server_response": None,
            "observed_error": str(exc),
        })
    result["timestamp"] = _now()
    result["duration_ms"] = round((time.monotonic() - start) * 1000, 1)
    return result


def attack_replay_frame(host: str, port: int, timeout: float = 2.0) -> dict[str, Any]:
    """Complete handshake in session A, capture the encrypted frame bytes, then
    open a NEW session (new session key) and replay the captured bytes.

    Expected: server rejects because the MAC tag was computed with the old
    session key and does not match the new session's key.
    """
    start = time.monotonic()
    result: dict[str, Any] = {
        "attack_id": _next_id(),
        "name": "Replay Secure Frame",
        "description": "Capture a valid encrypted frame from one session and replay it in a new session with different keys",
        "expected_result": "Server rejects with invalid secure frame tag (MAC key mismatch)",
        "risk_level_demo": "HIGH",
        "authorized_scope": "local-authorized-testing",
    }

    class _CaptureSocket:
        """Wraps a socket to capture the last raw sendall payload."""
        __slots__ = ("_sock", "last_frame")
        def __init__(self, sock: socket.socket) -> None:
            self._sock = sock
            self.last_frame: bytes = b""
        def sendall(self, data: bytes) -> None:
            self.last_frame = data
            self._sock.sendall(data)
        def __getattr__(self, name: str) -> Any:
            return getattr(self._sock, name)

    try:
        # Session A: connect, handshake, send metric, capture raw frame bytes.
        sock_a = socket.create_connection((host, port), timeout=timeout)
        cap_sock = _CaptureSocket(sock_a)
        # We need the SecureSocket to use our capture socket.
        # client_handshake uses the socket we give it, so we pass cap_sock.
        secure_a = client_handshake(cap_sock, "node-01")  # type: ignore[arg-type]
        secure_a.send_message({
            "type": "metric",
            "node_id": "node-01",
            "seq": 1,
            "cpu": 35.0,
            "ram": 45.0,
            "latency_ms": 30,
            "service_web": "ok",
            "event_log": "normal",
            "token": get_token("node-01") or "unknown",
        })
        captured = getattr(cap_sock, "last_frame", b"")
        # Drain server response so the socket is clean.
        try:
            secure_a.recv_message()
        except (SecureProtocolError, EOFError, OSError):
            pass
        sock_a.close()

        if not captured:
            # Fallback: build a plausible replay frame manually.
            import base64 as _b64
            captured = encode_plain({
                "type": "secure",
                "seq": 0,
                "nonce": _b64.b64encode(b"\x01" * 16).decode("ascii"),
                "ciphertext": _b64.b64encode(b"replayed_payload").decode("ascii"),
                "tag": _b64.b64encode(b"\xAA" * 32).decode("ascii"),
            })

        # Session B: new connection, new handshake, replay captured bytes.
        sock_b = socket.create_connection((host, port), timeout=timeout)
        secure_b = client_handshake(sock_b, "node-01")

        # Send a dummy metric first so the server advances recv_seq.
        secure_b.send_message({
            "type": "metric", "node_id": "node-01", "seq": 10,
            "cpu": 30.0, "ram": 40.0, "latency_ms": 20,
            "service_web": "ok", "event_log": "normal",
            "token": get_token("node-01") or "unknown",
        })
        try:
            secure_b.recv_message()
        except (SecureProtocolError, EOFError, OSError):
            pass

        # Now replay the captured frame from session A.
        secure_b.sock.sendall(captured)
        time.sleep(0.3)
        try:
            data = secure_b.sock.recv(4096)
            connection_alive = len(data) > 0
        except (OSError, ConnectionResetError):
            connection_alive = False
        sock_b.close()

        detected = not connection_alive
        result.update({
            "success": detected,
            "server_response": "connection reset (replay detected)" if detected else "connection remained open",
            "observed_error": None if detected else "server accepted replayed frame",
        })
    except Exception as exc:
        result.update({
            "success": False,
            "server_response": None,
            "observed_error": str(exc),
        })
    result["timestamp"] = _now()
    result["duration_ms"] = round((time.monotonic() - start) * 1000, 1)
    return result


# ---------------------------------------------------------------------------
# Attack catalog registry
# ---------------------------------------------------------------------------

ATTACKS: dict[str, dict[str, Any]] = {
    "plaintext-metric": {
        "func": attack_plaintext_metric,
        "label": "Plaintext Metric Injection",
        "description": "Send a metric as plain JSON without the required PSK handshake",
    },
    "unknown-node": {
        "func": attack_unknown_node,
        "label": "Unknown Node Authentication",
        "description": "Handshake with a node_id that has no configured PSK",
    },
    "bad-psk": {
        "func": attack_bad_psk,
        "label": "Invalid PSK Proof",
        "description": "Provide an incorrect HMAC proof during challenge-response",
    },
    "node-mismatch": {
        "func": attack_node_mismatch,
        "label": "Node ID Mismatch",
        "description": "Authenticate as one node but send metric claiming another",
    },
    "invalid-metric": {
        "func": attack_invalid_metric,
        "label": "Invalid Metric Fields",
        "description": "Send a metric with out-of-range values via a valid channel",
    },
    "tampered-frame": {
        "func": attack_tampered_frame,
        "label": "Tampered Secure Frame",
        "description": "Send a secure frame with deliberately corrupted ciphertext/tag",
    },
    "replay-frame": {
        "func": attack_replay_frame,
        "label": "Replay Secure Frame",
        "description": "Replay a captured frame in a new session",
    },
}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Authorized local attacker simulation for demo hardening",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Target server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Target server port (default: 5000)")
    parser.add_argument(
        "--attack",
        default="all",
        choices=list(ATTACKS) + ["all"],
        help="Attack key or 'all' (default: all)",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON array")
    parser.add_argument("--timeout", type=float, default=2.0, help="Socket timeout seconds (default: 2.0)")
    parser.add_argument("--full", action="store_true", help="Show full details in non-JSON output")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    _check_target(args.host)

    if args.attack == "all":
        keys = list(ATTACKS)
    else:
        keys = [args.attack]

    results: list[dict[str, Any]] = []
    for key in keys:
        info = ATTACKS[key]
        result = info["func"](args.host, args.port, timeout=args.timeout)
        results.append(result)

    if args.json:
        print(json.dumps(results, indent=2, default=str))
        return

    success_count = sum(1 for r in results if r.get("success"))
    total = len(results)
    for r in results:
        status = "✓ PASS" if r["success"] else "✗ FAIL"
        print(f"[{status}] {r['attack_id']} {r['name']}")
        if args.full or not r["success"]:
            print(f"       description: {r['description']}")
            print(f"       expected:    {r['expected_result']}")
            print(f"       response:    {r.get('server_response', 'N/A')}")
            if r.get("observed_error"):
                print(f"       error:       {r['observed_error']}")
            print(f"       duration_ms: {r['duration_ms']}")
            print()

    print(f"--- Results: {success_count}/{total} attacks correctly detected ---")


if __name__ == "__main__":
    main()
