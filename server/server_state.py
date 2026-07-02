from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any


@dataclass
class NodeState:
    node_id: str
    address: str
    last_seq: int | None = None
    last_seen: str | None = None
    connected: bool = True


class ServerState:
    def __init__(self) -> None:
        self._nodes: dict[str, NodeState] = {}
        self._lock = Lock()

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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

