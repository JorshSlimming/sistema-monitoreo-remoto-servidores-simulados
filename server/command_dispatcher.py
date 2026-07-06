from itertools import count
from threading import Lock
from typing import Any


class CommandDispatcher:
    def __init__(self) -> None:
        self._counter = count(1)
        self._lock = Lock()

    def build_command(self, action: str, reason: str) -> tuple[dict[str, Any],int]:
        command_id = self._next_command_id()
        return {
            "type": "command",
            "command_id": command_id,
            "action": action,
            "reason": reason,
        }, command_id

    def _next_command_id(self) -> int:
        with self._lock:
            return next(self._counter)
