import tempfile
import unittest
from datetime import datetime, timezone

from alertsrv.engine import AlertEngine
from alertsrv.models import AlertState, SourceHealth
from alertsrv.serialization import alert_to_dict, alert_to_json
from alertsrv.storage import SQLiteAlertStore
from tests.test_engine import event


class SerializationTests(unittest.TestCase):
    def test_alert_serialization_is_json_safe_and_stable(self):
        engine = AlertEngine()
        alert = engine.ingest(event("1", "weather-a"))
        first = alert_to_json(alert)
        second = alert_to_json(alert)
        self.assertEqual(first, second)
        self.assertEqual(alert_to_dict(alert)["state"], "active")


class SQLitePersistenceTests(unittest.TestCase):
    def test_alert_and_dedup_index_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = f"{directory}/alerts.db"
            store = SQLiteAlertStore(path)
            engine = AlertEngine(store=store)
            first = engine.ingest(event("1", "weather-a"))
            engine.set_source_health("weather-a", SourceHealth.DEGRADED)
            store.close()

            store = SQLiteAlertStore(path)
            restored = AlertEngine(store=store)
            self.assertEqual(restored.get(first.alert_id).state, AlertState.ACTIVE)
            self.assertEqual(len(restored.get(first.alert_id).evidence), 1)
            self.assertEqual(restored.source_health("weather-a"), SourceHealth.DEGRADED)

            duplicate = restored.ingest(event("1", "weather-a", confidence=0.99))
            self.assertEqual(duplicate.alert_id, first.alert_id)
            self.assertEqual(len(duplicate.evidence), 1)
            store.close()

    def test_resolve_and_expire_are_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = f"{directory}/alerts.db"
            store = SQLiteAlertStore(path)
            engine = AlertEngine(store=store)
            alert = engine.ingest(event("1", "weather-a", expires_offset=10))
            engine.expire(now=datetime(2026, 10, 4, 12, 10, tzinfo=timezone.utc))
            self.assertEqual(alert.state, AlertState.EXPIRED)
            store.close()

            store = SQLiteAlertStore(path)
            restored = AlertEngine(store=store)
            self.assertEqual(restored.get(alert.alert_id).state, AlertState.EXPIRED)
            store.close()


if __name__ == "__main__":
    unittest.main()
