import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from alertsrv.engine import AlertEngine
from alertsrv.models import NormalizedEvent, Severity
from alertsrv.notifications import DeliveryState, NotificationDispatcher
from alertsrv.notifications_file import FileNotificationAdapter

UTC = timezone.utc
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


class FileNotificationTests(unittest.TestCase):
    def test_file_adapter_appends_jsonl_record(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notifications" / "events.jsonl"
            alert = AlertEngine().ingest(
                NormalizedEvent(
                    event_id="warning",
                    source_id="source",
                    event_type="weather.warning",
                    title="Storm warning",
                    severity=Severity.WARNING,
                    confidence=0.9,
                    occurred_at=NOW,
                    received_at=NOW,
                    correlation_key="weather:storm",
                )
            )
            dispatcher = NotificationDispatcher()
            result = dispatcher.dispatch(
                alert,
                adapters=[FileNotificationAdapter(path)],
                body="Warning",
                now=NOW,
            )

            self.assertEqual(result[0].state, DeliveryState.SENT)
            record = json.loads(path.read_text(encoding="utf-8").strip())
            self.assertEqual(record["alert_id"], alert.alert_id)
            self.assertEqual(record["channel"], "file")
            self.assertEqual(record["body"], "Warning")

    def test_file_adapter_preserves_multiple_notifications(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            adapter = FileNotificationAdapter(path)
            alert = AlertEngine().ingest(
                NormalizedEvent(
                    event_id="warning",
                    source_id="source",
                    event_type="weather.warning",
                    title="Storm warning",
                    severity=Severity.WARNING,
                    confidence=0.9,
                    occurred_at=NOW,
                    received_at=NOW,
                    correlation_key="weather:storm",
                )
            )
            dispatcher = NotificationDispatcher()
            dispatcher.dispatch(alert, adapters=[adapter], body="one", now=NOW)
            dispatcher.dispatch(alert, adapters=[adapter], body="two", now=NOW.replace(minute=1))

            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[1])["body"], "two")


if __name__ == "__main__":
    unittest.main()
