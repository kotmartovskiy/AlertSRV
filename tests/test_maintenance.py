import sqlite3
import tempfile
import unittest
from pathlib import Path

from alertsrv.maintenance import backup_database, restore_database, timestamped_backup_path, verify_database
from alertsrv.storage import SQLiteAlertStore


class MaintenanceTests(unittest.TestCase):
    def test_fresh_store_records_schema_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "alerts.db"
            store = SQLiteAlertStore(path)
            self.assertEqual(store.schema_version, 2)
            store.close()

    def test_legacy_schema_is_migrated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.db"
            db = sqlite3.connect(path)
            db.executescript(
                """
                CREATE TABLE alerts (
                    alert_id TEXT PRIMARY KEY,
                    correlation_key TEXT NOT NULL,
                    state TEXT NOT NULL,
                    data_json TEXT NOT NULL
                );
                CREATE TABLE event_index (
                    event_key TEXT PRIMARY KEY,
                    alert_id TEXT NOT NULL REFERENCES alerts(alert_id)
                );
                CREATE TABLE source_health (
                    source_id TEXT PRIMARY KEY,
                    health TEXT NOT NULL
                );
                """
            )
            db.commit()
            db.close()
            store = SQLiteAlertStore(path)
            self.assertEqual(store.schema_version, 2)
            columns = {row[1] for row in store._db.execute("PRAGMA table_info(event_index)")}
            self.assertIn("received_at", columns)
            store.close()

    def test_backup_verify_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "alerts.db"
            backup = root / "backup" / "alerts.db"
            restored = root / "restored.db"
            store = SQLiteAlertStore(source)
            store._db.execute("INSERT INTO source_health VALUES (?, ?)", ("source-a", "healthy"))
            store._db.commit()
            store.close()

            backup_database(source, backup)
            self.assertTrue(verify_database(backup))
            restore_database(backup, restored)
            self.assertTrue(verify_database(restored))
            restored_store = SQLiteAlertStore(restored)
            self.assertEqual(restored_store.load_source_health()["source-a"].value, "healthy")
            restored_store.close()

    def test_corrupt_backup_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad = root / "bad.db"
            bad.write_bytes(b"not sqlite")
            with self.assertRaises(ValueError):
                restore_database(bad, root / "restored.db")

    def test_timestamped_backup_path_is_deterministic_format(self):
        with tempfile.TemporaryDirectory() as directory:
            path = timestamped_backup_path(directory)
            self.assertTrue(path.name.startswith("alerts-"))
            self.assertTrue(path.name.endswith(".db"))


if __name__ == "__main__":
    unittest.main()
