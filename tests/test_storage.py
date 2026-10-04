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

    def test_ingest_is_atomic_when_event_index_write_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAlertStore(f"{directory}/alerts.db")
            engine = AlertEngine()
            alert = engine.ingest(event("1", "weather-a"))
            store._db.executescript(
                """
                CREATE TRIGGER fail_event_index
                AFTER INSERT ON event_index
                WHEN NEW.event_key = 'forced-failure'
                BEGIN
                    SELECT RAISE(ABORT, 'forced failure');
                END;
                """
            )
            with self.assertRaises(Exception):
                store.save_ingest(
                    alert,
                    "forced-failure",
                    datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc),
                )

            row = store._db.execute(
                "SELECT 1 FROM alerts WHERE alert_id = ?", (alert.alert_id,)
            ).fetchone()
            self.assertIsNone(row)
            self.assertIsNone(store.event_alert_id("forced-failure"))
            store.close()

    def test_event_index_retention_keeps_active_and_recent_terminal_mappings(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAlertStore(f"{directory}/alerts.db")
            engine = AlertEngine()
            old = engine.ingest(event("old", "weather-old", correlation_key="old"))
            recent = engine.ingest(event("recent", "weather-recent", correlation_key="recent"))
            active = engine.ingest(event("active", "weather-active", correlation_key="active"))
            old.state = AlertState.RESOLVED
            recent.state = AlertState.RESOLVED
            store.save_alert(old)
            store.save_alert(recent)
            store.save_alert(active)

            old_time = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
            recent_time = datetime(2026, 10, 4, 12, 30, tzinfo=timezone.utc)
            store.save_event_mapping("old-key", old.alert_id, old_time)
            store.save_event_mapping("recent-key", recent.alert_id, recent_time)
            store.save_event_mapping("active-key", active.alert_id, old_time)

            cutoff = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
            removed = store.prune_event_index(cutoff)
            self.assertEqual(removed, 1)
            self.assertIsNone(store.event_alert_id("old-key"))
            self.assertIsNotNone(store.event_alert_id("recent-key"))
            self.assertIsNotNone(store.event_alert_id("active-key"))
            store.close()


if __name__ == "__main__":
    unittest.main()
