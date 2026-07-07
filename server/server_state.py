from dataclasses import dataclass
from datetime import datetime, timezone
import time
from threading import Lock
from typing import Any


@dataclass
class NodeState:
    node_id: str
    address: str
    last_seq: int | None = None
    last_seen: str | None = None
    connected: bool = True

@dataclass
class ActionData:
    action: str
    timestamp: float
    node_id: str
    status: str

class ServerState:
    def __init__(self) -> None:
        self._nodes: dict[str, NodeState] = {}
        self._lock = Lock()
        self.sent_commands: dict[int, ActionData] = {}
        self.command_timeout = 20  # segundos

    def mark_connected(self, node_id: str, address: str, seq: int | None = None) -> None:
        with self._lock:
            self._nodes[node_id] = NodeState(
                node_id=node_id,
                address=address,
                last_seq=seq,
                last_seen=_now(),
                connected=True,
            )

    def mark_seen(self, node_id: str, seq: int | None = None) -> None:
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return
            node.last_seq = seq
            node.last_seen = _now()
            node.connected = True

    def mark_disconnected(self, node_id: str | None) -> None:
        if not node_id:
            return
        with self._lock:
            node = self._nodes.get(node_id)
            if node is not None:
                node.connected = False
                node.last_seen = _now()

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                node_id: {
                    "address": node.address,
                    "last_seq": node.last_seq,
                    "last_seen": node.last_seen,
                    "connected": node.connected,
                }
                for node_id, node in self._nodes.items()
            }
    def register_command(self, cid: int, action: str, node_id: str) -> None:
        with self._lock:
            self.sent_commands[cid] = ActionData(
                action=action,
                node_id=node_id,
                timestamp=time.time(),
                status="pending",
            )

    def is_action_pending(self, action: str, node_id: str) -> bool:
        with self._lock:
            now = time.time()
            for cid, cmd in self.sent_commands.items():
                if cmd.action != action or cmd.node_id != node_id:
                    continue
                if cmd.status != "pending":
                    continue
                if now - cmd.timestamp > self.command_timeout:
                    print(f"[warning] Command {cid} ({action}) timed out after {self.command_timeout}s. Expiring.")
                    cmd.status = "timed_out"
                    continue
                return True
            return False

    def confirm_command(self, cid: int) -> bool:
        with self._lock:
            command = self.sent_commands.get(cid)
            if command is None:
                return False
            command.status = "confirmed"
            return True



def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

