from __future__ import annotations

import json
import sqlite3
from threading import RLock
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .models import Alert, AlertState, SourceHealth
from .serialization import alert_from_dict, alert_to_dict


class AlertStore(Protocol):
    def load_alerts(self) -> list[Alert]: ...
    def save_alert(self, alert: Alert) -> None: ...
    def save_ingest(self, alert: Alert, event_key: str, received_at: datetime) -> None: ...
    def event_alert_id(self, event_key: str) -> str | None: ...
    def save_event_mapping(self, event_key: str, alert_id: str, received_at: datetime | None = None) -> None: ...
    def prune_event_index(self, cutoff: datetime) -> int: ...
    def load_source_health(self) -> dict[str, SourceHealth]: ...
    def save_source_health(self, source_id: str, health: SourceHealth) -> None: ...


class SQLiteAlertStore:
    """Small durable SQLite store for alerts and aggregation indexes."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._lock = RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA busy_timeout = 5000")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                correlation_key TEXT NOT NULL,
                state TEXT NOT NULL,
                data_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS event_index (
                event_key TEXT PRIMARY KEY,
                alert_id TEXT NOT NULL REFERENCES alerts(alert_id),
                received_at TEXT
            );
            CREATE TABLE IF NOT EXISTS source_health (
                source_id TEXT PRIMARY KEY,
                health TEXT NOT NULL
            );
            """
        )
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(event_index)")}
        if "received_at" not in columns:
            self._db.execute("ALTER TABLE event_index ADD COLUMN received_at TEXT")
        self._db.commit()

    def load_alerts(self) -> list[Alert]:
        with self._lock:
            rows = self._db.execute("SELECT data_json FROM alerts").fetchall()
            return [alert_from_dict(json.loads(row[0])) for row in rows]

    @staticmethod
    def _alert_json(alert: Alert) -> str:
        return json.dumps(
            alert_to_dict(alert),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def save_alert(self, alert: Alert) -> None:
        with self._lock:
            self._db.execute(
            """
            INSERT INTO alerts(alert_id, correlation_key, state, data_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(alert_id) DO UPDATE SET
                correlation_key=excluded.correlation_key,
                state=excluded.state,
                data_json=excluded.data_json
            """,
            (alert.alert_id, alert.correlation_key, alert.state.value, self._alert_json(alert)),
        )
            self._db.commit()

    def save_ingest(self, alert: Alert, event_key: str, received_at: datetime) -> None:
        """Persist the final alert state and its dedup index atomically."""
        with self._lock, self._db:
            self._db.execute(
                """
                INSERT INTO alerts(alert_id, correlation_key, state, data_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(alert_id) DO UPDATE SET
                    correlation_key=excluded.correlation_key,
                    state=excluded.state,
                    data_json=excluded.data_json
                """,
                (alert.alert_id, alert.correlation_key, alert.state.value, self._alert_json(alert)),
            )
            self._db.execute(
                """
                INSERT OR IGNORE INTO event_index(event_key, alert_id, received_at)
                VALUES (?, ?, ?)
                """,
                (event_key, alert.alert_id, received_at.isoformat()),
            )

    def event_alert_id(self, event_key: str) -> str | None:
        with self._lock:
            row = self._db.execute(
            "SELECT alert_id FROM event_index WHERE event_key = ?", (event_key,)
            ).fetchone()
            return row[0] if row else None

    def save_event_mapping(
        self, event_key: str, alert_id: str, received_at: datetime | None = None
    ) -> None:
        with self._lock:
            self._db.execute(
            """
            INSERT OR IGNORE INTO event_index(event_key, alert_id, received_at)
            VALUES (?, ?, ?)
            """,
            (event_key, alert_id, received_at.isoformat() if received_at else None),
        )
            self._db.commit()

    def prune_event_index(self, cutoff: datetime) -> int:
        """Remove old dedup mappings only when their alert is terminal."""
        terminal = tuple(state.value for state in (
            AlertState.RESOLVED,
            AlertState.EXPIRED,
            AlertState.CANCELLED,
            AlertState.SUPERSEDED,
        ))
        placeholders = ",".join("?" for _ in terminal)
        with self._lock, self._db:
            cursor = self._db.execute(
                f"""
                DELETE FROM event_index
                WHERE received_at IS NOT NULL
                  AND received_at < ?
                  AND alert_id IN (
                      SELECT alert_id FROM alerts
                      WHERE state IN ({placeholders})
                  )
                """,
                (cutoff.isoformat(), *terminal),
            )
        return cursor.rowcount

    def load_source_health(self) -> dict[str, SourceHealth]:
        with self._lock:
            rows = self._db.execute("SELECT source_id, health FROM source_health").fetchall()
            return {source_id: SourceHealth(health) for source_id, health in rows}

    def save_source_health(self, source_id: str, health: SourceHealth) -> None:
        with self._lock:
            self._db.execute(
            """
            INSERT INTO source_health(source_id, health) VALUES (?, ?)
            ON CONFLICT(source_id) DO UPDATE SET health=excluded.health
            """,
            (source_id, health.value),
        )
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()
