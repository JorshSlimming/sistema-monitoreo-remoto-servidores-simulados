"""Thread-safe SQLite persistence for metrics, commands, and acks."""

import os
import sqlite3
import threading
from datetime import datetime, timezone


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS metrics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id     TEXT    NOT NULL,
    seq         INTEGER NOT NULL,
    cpu         REAL    NOT NULL,
    ram         REAL    NOT NULL,
    latency_ms  REAL    NOT NULL,
    service_web TEXT    NOT NULL,
    event_log   TEXT,
    received_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS commands (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id  INTEGER NOT NULL,
    action      TEXT    NOT NULL,
    reason      TEXT    NOT NULL,
    node_id     TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'pending',
    issued_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS acks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id  INTEGER NOT NULL,
    node_id     TEXT    NOT NULL,
    status      TEXT    NOT NULL,
    received_at TEXT    NOT NULL
);
"""

# ponytail: additive columns; safe to run against existing databases
_EXTRA_COLUMNS = [
    ("scenario", "TEXT", "''"),
    ("anomaly_active", "INTEGER", "1"),
    ("mitigation_active", "INTEGER", "0"),
    ("mitigation_type", "TEXT", "''"),
    ("last_command", "TEXT", "''"),
]


def _migrate_metrics_schema(conn: sqlite3.Connection) -> None:
    """Add enrichment columns to ``metrics`` if they do not exist yet."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(metrics)")}
    for col_name, col_type, default in _EXTRA_COLUMNS:
        if col_name not in existing:
            conn.execute(
                f"ALTER TABLE metrics ADD COLUMN {col_name} {col_type} DEFAULT {default}"
            )


class DatabaseStore:
    """Thread-safe SQLite store for the monitoring server.

    One instance shared across all client sessions is safe because every
    public method serialises through a single :class:`threading.Lock`.
    """

    def __init__(self, db_path: str = "data/monitor.db") -> None:
        self.db_path = db_path
        self._lock = threading.Lock()

        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA_SQL)
        _migrate_metrics_schema(self._conn)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_metric(
        self,
        node_id: str,
        seq: int,
        cpu: float,
        ram: float,
        latency_ms: float,
        service_web: str,
        event_log: str | None = None,
        scenario: str = "",
        anomaly_active: bool = True,
        mitigation_active: bool = False,
        mitigation_type: str = "",
        last_command: str = "",
    ) -> None:
        now = _now()
        with self._lock:
            self._conn.execute(
                "INSERT INTO metrics "
                "(node_id, seq, cpu, ram, latency_ms, service_web, event_log, received_at, "
                "scenario, anomaly_active, mitigation_active, mitigation_type, last_command) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    node_id,
                    seq,
                    cpu,
                    ram,
                    latency_ms,
                    service_web,
                    event_log,
                    now,
                    scenario,
                    int(anomaly_active),
                    int(mitigation_active),
                    mitigation_type,
                    last_command,
                ),
            )
            self._conn.commit()

    def save_command(
        self,
        command_id: int,
        action: str,
        reason: str,
        node_id: str,
    ) -> None:
        now = _now()
        with self._lock:
            self._conn.execute(
                "INSERT INTO commands (command_id, action, reason, node_id, status, issued_at) "
                "VALUES (?, ?, ?, ?, 'pending', ?)",
                (command_id, action, reason, node_id, now),
            )
            self._conn.commit()

    def save_ack(
        self,
        command_id: int,
        node_id: str,
        status: str,
    ) -> None:
        now = _now()
        with self._lock:
            self._conn.execute(
                "INSERT INTO acks (command_id, node_id, status, received_at) "
                "VALUES (?, ?, ?, ?)",
                (command_id, node_id, status, now),
            )
            self._conn.commit()

    def update_command_status(self, command_id: int, status: str) -> None:
        """Update the status of a previously persisted command."""
        with self._lock:
            self._conn.execute(
                "UPDATE commands SET status = ? WHERE command_id = ?",
                (status, command_id),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ponytail: row-count helpers for testing, not a full query API
    def _count_metrics(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]

    def _count_commands(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]

    def _count_acks(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM acks").fetchone()[0]

    def __enter__(self) -> "DatabaseStore":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
