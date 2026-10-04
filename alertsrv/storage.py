from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol

from .models import Alert, SourceHealth
from .serialization import alert_from_dict, alert_to_dict
import json


class AlertStore(Protocol):
    def load_alerts(self) -> list[Alert]: ...
    def save_alert(self, alert: Alert) -> None: ...
    def event_alert_id(self, event_key: str) -> str | None: ...
    def save_event_mapping(self, event_key: str, alert_id: str) -> None: ...
    def load_source_health(self) -> dict[str, SourceHealth]: ...
    def save_source_health(self, source_id: str, health: SourceHealth) -> None: ...


class SQLiteAlertStore:
    """Small durable SQLite store for alerts and aggregation indexes."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._db = sqlite3.connect(self.path)
        self._db.execute("PRAGMA foreign_keys = ON")
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
                alert_id TEXT NOT NULL REFERENCES alerts(alert_id)
            );
            CREATE TABLE IF NOT EXISTS source_health (
                source_id TEXT PRIMARY KEY,
                health TEXT NOT NULL
            );
            """
        )
        self._db.commit()

    def load_alerts(self) -> list[Alert]:
        rows = self._db.execute("SELECT data_json FROM alerts").fetchall()
        return [alert_from_dict(json.loads(row[0])) for row in rows]

    def save_alert(self, alert: Alert) -> None:
        self._db.execute(
            """
            INSERT INTO alerts(alert_id, correlation_key, state, data_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(alert_id) DO UPDATE SET
                correlation_key=excluded.correlation_key,
                state=excluded.state,
                data_json=excluded.data_json
            """,
            (
                alert.alert_id,
                alert.correlation_key,
                alert.state.value,
                json.dumps(alert_to_dict(alert), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            ),
        )
        self._db.commit()

    def event_alert_id(self, event_key: str) -> str | None:
        row = self._db.execute(
            "SELECT alert_id FROM event_index WHERE event_key = ?", (event_key,)
        ).fetchone()
        return row[0] if row else None

    def save_event_mapping(self, event_key: str, alert_id: str) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO event_index(event_key, alert_id) VALUES (?, ?)",
            (event_key, alert_id),
        )
        self._db.commit()

    def load_source_health(self) -> dict[str, SourceHealth]:
        rows = self._db.execute("SELECT source_id, health FROM source_health").fetchall()
        return {source_id: SourceHealth(health) for source_id, health in rows}

    def save_source_health(self, source_id: str, health: SourceHealth) -> None:
        self._db.execute(
            """
            INSERT INTO source_health(source_id, health) VALUES (?, ?)
            ON CONFLICT(source_id) DO UPDATE SET health=excluded.health
            """,
            (source_id, health.value),
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()
