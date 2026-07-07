import json
from numbers import Number
import socket
from typing import Any

from server.command_dispatcher import CommandDispatcher
from server.server_config import ServerConfig
from server.server_state import ServerState


class ClientSession:
    def __init__(
        self,
        conn: socket.socket,
        address: tuple[str, int],
        config: ServerConfig,
        state: ServerState,
        dispatcher: CommandDispatcher,
    ) -> None:
        self.conn = conn
        self.address = address
        self.config = config
        self.state = state
        self.dispatcher = dispatcher
        self.node_id: str | None = None
        self._buffer = b""

    def run(self) -> None:
        peer = f"{self.address[0]}:{self.address[1]}"
        print(f"[server] client connected from {peer}")

        try:
            while True:
                chunk = self.conn.recv(4096)
                if not chunk:
                    break
                self._buffer += chunk
                if len(self._buffer) > self.config.max_line_bytes:
                    print(f"[server] message too large from {peer}; dropping buffer")
                    self._buffer = b""
                    continue
                self._process_buffer()
        except ConnectionResetError:
            print(f"[server] connection reset by {peer}")
        finally:
            self.state.mark_disconnected(self.node_id)
            self.conn.close()
            print(f"[server] client disconnected from {peer}")

    def _process_buffer(self) -> None:

        separator = self.config.message_separator.encode(self.config.encoding)
        while separator in self._buffer:
            line, self._buffer = self._buffer.split(separator, 1)
            if line:
                self._handle_line(line)

    def _handle_line(self, line: bytes) -> None:
        try:
            message = self._decode_json_line(line)
        except ValueError as exc:
            print(f"[server] invalid JSON from {self.address[0]}:{self.address[1]}: {exc}")
            self.send_error("INVALID_JSON", "received malformed JSON")
            return

        message_type = message.get("type")
        if message_type == "metric":
            self._handle_metric(message)
        elif message_type == "ack":
            self._handle_ack(message)
        else:
            print(f"[server] received message type={message_type!r}: {message}")

    def _handle_metric(self, metric: dict[str, Any]) -> None:
        node_id = metric.get("node_id")
        if isinstance(node_id, str) and node_id:
            self.node_id = node_id
        else:
            self.node_id = f"unknown-{self.address[0]}:{self.address[1]}"

        peer = f"{self.address[0]}:{self.address[1]}"
        seq = metric.get("seq") if isinstance(metric.get("seq"), int) and metric.get("seq",-1) > 0 else self.send_error("INVALID_MESSAGE", "sequence number must be a positive integer") 
        if not seq:
            return
        self.state.mark_connected(self.node_id, peer, seq)
        self.state.mark_seen(self.node_id, seq)

        if not (metrics := self._extract_metric(metric)):
            return
        cpu,ram,latency_ms,service_web,event_log = metrics
        self._send_orders(cpu,ram,latency_ms,service_web,event_log)
        print(f"[metric] {self.node_id}: {metric}")

    def _handle_ack(self, ack: dict[str, Any]) -> None:
        node_id = ack.get("node_id")
        if isinstance(node_id, str) and node_id:
            self.node_id = node_id

        ack_data = self._extract_ack(ack)
        if not ack_data:
            return
        cid, status = ack_data
        self.state.confirm_command(cid)
        print(f"[ack] {ack}")

    def _extract_metric(self, metric: dict[str,Any]) -> tuple[float,float,float,str,str | None] | None:
        cpu = metric.get("cpu")
        if not isinstance(cpu,(int,float)):
            self.send_error("INVALID_MESSAGE", "cpu must be a number")
            return None 
        if cpu < 0 or cpu > 100:
            self.send_error("INVALID_MESSAGE", "cpu must be between 0 and 100")
            return None 

        ram = metric.get("ram")
        if not isinstance(ram,(int,float)):
            self.send_error("INVALID_MESSAGE", "ram must be a number")
            return None 
        if ram < 0 or ram > 100:
            self.send_error("INVALID_MESSAGE", "ram must be between 0 and 100")
            return None 

        latency_ms = metric.get("latency_ms")
        if not isinstance(latency_ms,(int,float)):
            self.send_error("INVALID_MESSAGE", "latency must be a number")
            return None 
        if latency_ms < 0:
            self.send_error("INVALID_MESSAGE", "latency must be greater or equal to 0")
            return None 

        service_web = metric.get("service_web", "invalid")
        if not isinstance(service_web,str) or service_web not in ["ok", "falla"]:
            self.send_error("INVALID_MESSAGE", "invalid service_web value")
            return None

        return cpu,ram,latency_ms,service_web, metric.get("event_log")

    def _extract_ack(self, ack: dict[str,Any]) -> tuple[int,str] | None:
        cid = ack.get("command_id")
        if not isinstance(cid,int):
            self.send_error("INVALID_MESSAGE", "invalid command id")
            return None
        if not cid in self.state.sent_commands:
            self.send_error("INVALID_MESSAGE", "repeated ack or ack for nonexistent command")
            return None
        status = ack.get("status")
        if status not in ["applied","failed"]:
            self.send_error("INVALID_MESSAGE", "invalid status code")
            return None 

        return cid,status


    def _send_orders(self, cpu:float,ram:float,latency_ms:float,service_web:str,event_log: str | None):
        if cpu > 90 : self.send_command("reduce_cpu","cpu above 90")
        if ram > 90 : self.send_command("reduce_ram","ram above 90")
        if latency_ms > 200 : self.send_command("fix_latency", "latency above 200")
        if service_web == "falla" : self.send_command("restart_service", "failing web service, please restart")

    def send_error(self,code,message):
        error = {"type": "error", "code": code, "message": message}
        self._send(error)
        print(f"[error] {self.node_id}: {error}")

    def send_command(self, action: str, reason: str) -> None:
        command, command_id = self.dispatcher.build_command(action, reason)
        if self.state.is_action_pending(action,self.node_id):
            print(f"[command] {self.node_id} has {action} action pending, canceled command")
            return
        self.state.register_command(command_id, action, self.node_id)
        self._send(command)
        print(f"[command] {self.node_id}: {command}")

    def _send(self, message: dict[str, Any]) -> None:
        line = json.dumps(message, separators=(",", ":")) + self.config.message_separator
        self.conn.sendall(line.encode(self.config.encoding))

    def _decode_json_line(self, line: bytes) -> dict[str, Any]:
        text = line.decode(self.config.encoding).strip()
        message = json.loads(text)
        if not isinstance(message, dict):
            raise ValueError("message must be a JSON object")
        return message
