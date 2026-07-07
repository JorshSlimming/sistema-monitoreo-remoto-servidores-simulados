import json
import socket
from typing import Any

from server.command_dispatcher import CommandDispatcher
from server.server_config import ServerConfig
from server.server_state import ServerState
from shared.auth import validate_token
from shared.secure_channel import SecureProtocolError, SecureSocket, server_handshake
from storage.store import DatabaseStore


class ClientSession:
    def __init__(
        self,
        conn: socket.socket,
        address: tuple[str, int],
        config: ServerConfig,
        state: ServerState,
        dispatcher: CommandDispatcher,
        store: DatabaseStore | None = None,
    ) -> None:
        self.conn = conn
        self.address = address
        self.config = config
        self.state = state
        self.dispatcher = dispatcher
        self.store = store
        self.node_id: str | None = None
        self.secure: SecureSocket | None = None

    def run(self) -> None:
        peer = f"{self.address[0]}:{self.address[1]}"
        print(f"[server] client connected from {peer}")

        try:
            self.node_id, self.secure = server_handshake(
                self.conn,
                max_line_bytes=self.config.max_line_bytes,
            )
            print(f"[server] secure channel established for {self.node_id} from {peer}")
            while True:
                message = self.secure.recv_message()
                self._handle_message(message)
        except EOFError:
            pass
        except SecureProtocolError as exc:
            print(f"[server] secure protocol error from {peer}: {exc}")
        except ConnectionResetError:
            print(f"[server] connection reset by {peer}")
        finally:
            self.state.mark_disconnected(self.node_id)
            self.conn.close()
            print(f"[server] client disconnected from {peer}")

    def _handle_message(self, message: dict[str, Any]) -> None:
        message_type = message.get("type")
        if message_type == "metric":
            self._handle_metric(message)
        elif message_type == "ack":
            self._handle_ack(message)
        else:
            print(f"[server] received message type={message_type!r}: {message}")

    def _handle_metric(self, metric: dict[str, Any]) -> None:
        token = metric.get("token")
        node_id = metric.get("node_id")
        if isinstance(node_id, str) and node_id:
            if node_id != self.node_id:
                self.send_error("AUTH_FAILED", f"node mismatch for secure channel {self.node_id}")
                return
            if not isinstance(token, str) or not validate_token(node_id, token):
                self.send_error("AUTH_FAILED", f"invalid token for node {node_id}")
                return
        else:
            self.send_error("INVALID_MESSAGE", "node_id is required")
            return

        current_node_id = self.node_id
        if current_node_id is None:
            self.send_error("AUTH_FAILED", "secure channel is not bound to a node")
            return

        peer = f"{self.address[0]}:{self.address[1]}"
        seq = metric.get("seq")
        if not isinstance(seq, int) or seq < 0:
            self.send_error("INVALID_MESSAGE", "sequence number must be a non-negative integer")
            return
        self.state.mark_connected(current_node_id, peer, seq)
        self.state.mark_seen(current_node_id, seq)
        if seq % 10 == 0:
            self.state.cleanup_expired()

        metrics = self._extract_metric(metric)
        if metrics is None:
            return
        cpu, ram, latency_ms, service_web, event_log = metrics
        if self.store is not None and self.node_id is not None:
            self.store.save_metric(
                self.node_id,
                seq,
                cpu,
                ram,
                latency_ms,
                service_web,
                event_log,
                scenario=str(metric.get("scenario", "")),
                anomaly_active=bool(metric.get("anomaly_active", True)),
                mitigation_active=bool(metric.get("mitigation_active", False)),
                mitigation_type=str(metric.get("mitigation_type", "")),
                last_command=str(metric.get("last_command", "")),
            )
        self._send_orders(cpu, ram, latency_ms, service_web, event_log)
        print(f"[metric] {current_node_id}: {metric}")

    def _handle_ack(self, ack: dict[str, Any]) -> None:
        node_id = ack.get("node_id")
        if isinstance(node_id, str) and node_id:
            token = ack.get("token")
            if node_id != self.node_id:
                self.send_error("AUTH_FAILED", f"node mismatch for secure channel {self.node_id}")
                return
            if not isinstance(token, str) or not validate_token(node_id, token):
                self.send_error("AUTH_FAILED", f"invalid token for node {node_id}")
                return

        ack_data = self._extract_ack(ack)
        if not ack_data:
            return
        cid, status = ack_data
        self.state.finish_command(cid, status)
        if self.store is not None and self.node_id is not None:
            self.store.save_ack(cid, self.node_id, status)
        print(f"[ack] {ack}")

    def _extract_metric(self, metric: dict[str, Any]) -> tuple[float, float, float, str, str | None] | None:
        cpu = metric.get("cpu")
        if not isinstance(cpu, (int, float)):
            self.send_error("INVALID_MESSAGE", "cpu must be a number")
            return None
        if cpu < 0 or cpu > 100:
            self.send_error("INVALID_MESSAGE", "cpu must be between 0 and 100")
            return None

        ram = metric.get("ram")
        if not isinstance(ram, (int, float)):
            self.send_error("INVALID_MESSAGE", "ram must be a number")
            return None
        if ram < 0 or ram > 100:
            self.send_error("INVALID_MESSAGE", "ram must be between 0 and 100")
            return None

        latency_ms = metric.get("latency_ms")
        if not isinstance(latency_ms, (int, float)):
            self.send_error("INVALID_MESSAGE", "latency must be a number")
            return None
        if latency_ms < 0:
            self.send_error("INVALID_MESSAGE", "latency must be greater or equal to 0")
            return None

        service_web = metric.get("service_web", "invalid")
        if not isinstance(service_web, str) or service_web not in ["ok", "falla"]:
            self.send_error("INVALID_MESSAGE", "invalid service_web value")
            return None

        event_log = metric.get("event_log")
        return float(cpu), float(ram), float(latency_ms), service_web, event_log if isinstance(event_log, str) else None

    def _extract_ack(self, ack: dict[str, Any]) -> tuple[int, str] | None:
        cid = ack.get("command_id")
        if not isinstance(cid, int):
            self.send_error("INVALID_MESSAGE", "invalid command id")
            return None
        if cid not in self.state.sent_commands:
            self.send_error("INVALID_MESSAGE", "repeated ack or ack for nonexistent command")
            return None
        # Cross-node protection: reject ACK for a command that was sent to a different node.
        cmd = self.state.sent_commands[cid]
        if cmd.node_id != self.node_id:
            self.send_error("AUTH_FAILED", f"command {cid} was sent to {cmd.node_id}, not {self.node_id}")
            return None
        status = ack.get("status")
        if status not in ["applied", "failed"]:
            self.send_error("INVALID_MESSAGE", "invalid status code")
            return None

        return cid, status

    def _send_orders(self, cpu: float, ram: float, latency_ms: float, service_web: str, event_log: str | None) -> None:
        if cpu > 90:
            self.send_command("reduce_cpu", "cpu above 90")
        if ram > 90:
            self.send_command("reduce_ram", "ram above 90")
        if latency_ms > 200:
            self.send_command("fix_latency", "latency above 200")
        if service_web == "falla":
            self.send_command("restart_service", "failing web service, please restart")
        if event_log and "fallido" in event_log:
            self.send_command("normalize_node", "failed event detected, please normalize")

    def send_error(self, code: str, message: str) -> None:
        error = {"type": "error", "code": code, "message": message}
        self._send(error)
        print(f"[error] {self.node_id}: {error}")

    def send_command(self, action: str, reason: str) -> None:
        if self.node_id is None:
            return
        command, command_id = self.dispatcher.build_command(action, reason)
        if self.state.is_action_pending(action, self.node_id):
            print(f"[command] {self.node_id} has {action} action pending, canceled command")
            return
        self.state.register_command(command_id, action, self.node_id)
        if self.store is not None:
            self.store.save_command(command_id, action, reason, self.node_id)
        self._send(command)
        print(f"[command] {self.node_id}: {command}")

    def _send(self, message: dict[str, Any]) -> None:
        if self.secure is None:
            line = json.dumps(message, separators=(",", ":")) + self.config.message_separator
            self.conn.sendall(line.encode(self.config.encoding))
            return
        self.secure.send_message(message)

    def _decode_json_line(self, line: bytes) -> dict[str, Any]:
        text = line.decode(self.config.encoding).strip()
        message = json.loads(text)
        if not isinstance(message, dict):
            raise ValueError("message must be a JSON object")
        return message
