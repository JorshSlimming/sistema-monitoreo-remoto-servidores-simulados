from itertools import count
from threading import Lock
from typing import Any


class CommandDispatcher:
    def __init__(self) -> None:
        self._counter = count(1)
        self._lock = Lock()

    def build_command(self, action: str, reason: str) -> dict[str, Any]:
        return {
            "type": "command",
            "command_id": self._next_command_id(),
            "action": action,
            "reason": reason,
        }

    def _next_command_id(self) -> str:
        with self._lock:
            return f"cmd-{next(self._counter):06d}"
