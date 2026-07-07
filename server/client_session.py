import json
import socket
from typing import Any

from server.command_dispatcher import CommandDispatcher
from server.server_config import ServerConfig
from server.server_state import ServerState
from server.auth_handler import (
    encrypt_message,
    decrypt_message,
    encode_encrypted_message,
    decode_encrypted_message,
    load_psk_config,
    get_node_psk,
)
from shared.auth import validate_token
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
        self._buffer = b""
        self.authenticated = False
        self.psk: bytes | None = None

    def run(self) -> None:
        peer = f"{self.address[0]}:{self.address[1]}"
        print(f"[server] client connected from {peer}")

        try:
            # Perform authentication handshake
            if not self._perform_handshake():
                print(f"[server] authentication failed for {peer}")
                return
            
            print(f"[server] {self.node_id} authenticated successfully")
            
            # Process regular messages after authentication
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

    def _perform_handshake(self) -> bool:
        """
        Perform PSK-based authentication handshake:
        1. Receive node_id from client
        2. Lookup PSK and send encrypted challenge
        3. Receive encrypted response from client
        4. Validate response and establish authentication
        """
        peer = f"{self.address[0]}:{self.address[1]}"
        
        # Step 1: Receive node_id from client
        try:
            self.conn.settimeout(5)
            node_id_data = self.conn.recv(4096)
            self.conn.settimeout(None)
        except socket.timeout:
            print(f"[server] handshake timeout waiting for node_id from {peer}")
            return False
        
        if not node_id_data:
            print(f"[server] client disconnected during handshake from {peer}")
            return False
        
        try:
            # Parse node_id message
            node_id_msg = json.loads(node_id_data.decode(self.config.encoding).strip())
            if not isinstance(node_id_msg, dict) or node_id_msg.get("type") != "auth_init":
                print(f"[server] invalid auth_init message from {peer}")
                return False
            
            self.node_id = node_id_msg.get("node_id")
            if not isinstance(self.node_id, str) or not self.node_id:
                print(f"[server] invalid node_id in auth_init from {peer}")
                return False
        except (ValueError, UnicodeDecodeError) as e:
            print(f"[server] error parsing auth_init from {peer}: {e}")
            return False
        
        # Step 2: Load PSK from configuration
        psk_config = load_psk_config()
        self.psk = get_node_psk(self.node_id, psk_config)
        
        if self.psk is None:
            print(f"[server] no PSK configured for node {self.node_id}")
            return False
        
        # Step 3: Send encrypted challenge
        challenge = {"type": "auth_challenge_response", "message": "Please authenticate"}
        
        try:
            ciphertext, nonce, salt = encrypt_message(challenge, self.psk)
            encrypted_line = encode_encrypted_message(ciphertext, nonce, salt)
            self.conn.sendall((encrypted_line + self.config.message_separator).encode(self.config.encoding))
        except Exception as e:
            print(f"[server] error sending encrypted challenge to {self.node_id}: {e}")
            return False
        
        # Step 4: Receive encrypted response from client
        try:
            self.conn.settimeout(5)
            response_data = self.conn.recv(4096)
            self.conn.settimeout(None)
        except socket.timeout:
            print(f"[server] handshake timeout waiting for response from {self.node_id}")
            return False
        
        if not response_data:
            print(f"[server] client disconnected during handshake from {self.node_id}")
            return False
        
        # Step 5: Validate response
        try:
            response_line = response_data.decode(self.config.encoding).strip()
            ciphertext, nonce, salt = decode_encrypted_message(response_line)
            response_msg = decrypt_message(ciphertext, nonce, salt, self.psk)
            
            if response_msg.get("type") != "auth_response":
                print(f"[server] invalid auth_response from {self.node_id}")
                return False
            
            # Verify the response contains the expected acknowledgment
            if response_msg.get("acknowledged") != True:
                print(f"[server] client failed to acknowledge challenge from {self.node_id}")
                return False
        except Exception as e:
            print(f"[server] error validating encrypted response from {self.node_id}: {e}")
            return False
        
        # Authentication successful
        self.authenticated = True
        print(f"[auth] {self.node_id} completed PSK authentication handshake")
        return True

    def _process_buffer(self) -> None:

        separator = self.config.message_separator.encode(self.config.encoding)
        while separator in self._buffer:
            line, self._buffer = self._buffer.split(separator, 1)
            if line:
                self._handle_line(line)

    def _decrypt_line(self, line: bytes) -> dict[str, Any] | None:
        """Decrypt an encrypted message line after authentication"""
        if not self.authenticated or not self.psk:
            return None
        
        try:
            line_str = line.decode(self.config.encoding).strip()
            ciphertext, nonce, salt = decode_encrypted_message(line_str)
            message = decrypt_message(ciphertext, nonce, salt, self.psk)
            return message
        except Exception as e:
            print(f"[server] error decrypting message from {self.node_id}: {e}")
            return None

    def _handle_line(self, line: bytes) -> None:
        try:
            # After authentication, messages are encrypted
            if self.authenticated:
                message = self._decrypt_line(line)
                if message is None:
                    self.send_error("DECRYPT_ERROR", "failed to decrypt message")
                    return
            else:
                # Shouldn't happen, but handle just in case
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
        # Token check
        token = metric.get("token")
        node_id = metric.get("node_id")
        if isinstance(node_id, str) and node_id:
            if not isinstance(token, str) or not validate_token(node_id, token):
                self.send_error("AUTH_FAILED", f"invalid token for node {node_id}")
                return
            self.node_id = node_id
        else:
            self.node_id = f"unknown-{self.address[0]}:{self.address[1]}"

        peer = f"{self.address[0]}:{self.address[1]}"
        seq = metric.get("seq") if isinstance(metric.get("seq"), int) and metric.get("seq",-1) >= 0 else self.send_error("INVALID_MESSAGE", "sequence number must be a non-negative integer") 
        if seq is None:
            return
        self.state.mark_connected(self.node_id, peer, seq)
        self.state.mark_seen(self.node_id, seq)

        if not (metrics := self._extract_metric(metric)):
            return
        cpu,ram,latency_ms,service_web,event_log = metrics
        if self.store is not None and self.node_id is not None:
            self.store.save_metric(self.node_id, seq, cpu, ram, latency_ms, service_web, event_log)
        self._send_orders(cpu,ram,latency_ms,service_web,event_log)
        print(f"[metric] {self.node_id}: {metric}")

    def _handle_ack(self, ack: dict[str, Any]) -> None:
        node_id = ack.get("node_id")
        if isinstance(node_id, str) and node_id:
            token = ack.get("token")
            if not isinstance(token, str) or not validate_token(node_id, token):
                self.send_error("AUTH_FAILED", f"invalid token for node {node_id}")
                return
            self.node_id = node_id

        ack_data = self._extract_ack(ack)
        if not ack_data:
            return
        cid, status = ack_data
        self.state.confirm_command(cid)
        if self.store is not None and self.node_id is not None:
            self.store.save_ack(cid, self.node_id, status)
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
        if event_log and "fallido" in event_log : self.send_command("normalize_node", "failed event detected, please normalize")

    def send_error(self,code,message):
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
        if self.store is not None and self.node_id is not None:
            self.store.save_command(command_id, action, reason, self.node_id)
        self._send(command)
        print(f"[command] {self.node_id}: {command}")

    def _send(self, message: dict[str, Any]) -> None:
        if self.authenticated and self.psk:
            # Encrypt message after authentication
            try:
                ciphertext, nonce, salt = encrypt_message(message, self.psk)
                encrypted_line = encode_encrypted_message(ciphertext, nonce, salt)
                line = encrypted_line + self.config.message_separator
                self.conn.sendall(line.encode(self.config.encoding))
            except Exception as e:
                print(f"[server] error sending encrypted message to {self.node_id}: {e}")
        else:
            # Shouldn't happen, but fallback to unencrypted
            line = json.dumps(message, separators=(",", ":")) + self.config.message_separator
            self.conn.sendall(line.encode(self.config.encoding))

    def _decode_json_line(self, line: bytes) -> dict[str, Any]:
        text = line.decode(self.config.encoding).strip()
        message = json.loads(text)
        if not isinstance(message, dict):
            raise ValueError("message must be a JSON object")
        return message
