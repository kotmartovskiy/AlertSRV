from __future__ import annotations

import json
from pathlib import Path

from .notifications import Notification


class FileNotificationAdapter:
    """Local JSONL notification sink for integrations and diagnostics."""

    channel = "file"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def send(self, notification: Notification) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "notification_id": notification.notification_id,
            "alert_id": notification.alert_id,
            "channel": notification.channel,
            "title": notification.title,
            "body": notification.body,
            "created_at": notification.created_at.isoformat(),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
