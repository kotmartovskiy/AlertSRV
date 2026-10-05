import threading
import unittest
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import urlopen

from alertsrv.api import create_server
from alertsrv.engine import AlertEngine
from alertsrv.service import AlertService
from alertsrv.regions.scheduler import PollHistoryEntry, RegionalScheduler, ScheduledSource
from alertsrv.regions.base import RegionModule, RegionSourceSpec
from alertsrv.poller import PollResult, PollStatus
from alertsrv.models import SourceHealth
from tests.test_engine import event


class UITests(unittest.TestCase):
    def setUp(self):
        self.service = AlertService(AlertEngine())
        self.server = create_server(self.service)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def get(self, path):
        with urlopen(self.base + path, timeout=2) as response:
            return response.status, response.read().decode("utf-8")

    def test_ui_route_renders(self):
        source = event("ui-1", "mchs-37")
        source.payload.update({
            "scope": "region",
            "region_code": "37",
            "affected_areas": [{"level": "municipality", "name": "Лежневский район"}],
        })
        self.service.accept(source)
        status, body = self.get("/ui")
        self.assertEqual(status, 200)
        self.assertIn("AlertSRV", body)
        self.assertIn("Лежневский район", body)
        self.assertIn("/ui/alerts/", body)

    def test_ui_alert_detail_renders_timeline_and_sources(self):
        source = event("ui-detail-1", "mchs-37")
        source.payload.update({
            "scope": "region",
            "region_code": "37",
            "affected_areas": [{"level": "municipality", "name": "Лежневский район"}],
        })
        alert = self.service.accept(source)
        status, body = self.get("/ui/alerts/" + quote(alert.alert_id))
        self.assertEqual(status, 200)
        self.assertIn("Лежневский район", body)
        self.assertIn("mchs-37", body)
        self.assertIn("Хронология", body)

    def test_ui_alert_detail_missing_returns_404(self):
        try:
            self.get("/ui/alerts/not-found")
        except Exception as exc:
            self.assertEqual(getattr(exc, "code", None), 404)
        else:
            self.fail("expected HTTP 404")

    def test_ui_sources_route_renders_scheduler_state(self):
        class FakeScheduler:
            regions = ()
            def enabled_sources(self):
                return (ScheduledSource("37", "mchs-ivanovo", 300),)
            def last_results(self):
                return {("37", "mchs-ivanovo"): PollResult("mchs-ivanovo", SourceHealth.HEALTHY, PollStatus.SUCCESS, ())}
            def history(self, region_code, source_id, limit=None):
                return (PollHistoryEntry(
                    datetime.now(timezone.utc),
                    PollResult(source_id, SourceHealth.HEALTHY, PollStatus.SUCCESS, ()),
                    0.125,
                ),)
        self.service.attach_scheduler(FakeScheduler())
        status, body = self.get("/ui/sources")
        self.assertEqual(status, 200)
        self.assertIn("mchs-ivanovo", body)
        self.assertIn("Успешно", body)
        self.assertIn("Ивановская область", body)
        self.assertIn("/ui/sources/37/mchs-ivanovo", body)

    def test_ui_sources_distinguishes_empty_and_unavailable(self):
        class FakeScheduler:
            regions = ()
            def enabled_sources(self):
                return (
                    ScheduledSource("37", "empty-source", 60),
                    ScheduledSource("37", "down-source", 120),
                )
            def last_results(self):
                return {
                    ("37", "empty-source"): PollResult(
                        "empty-source", SourceHealth.HEALTHY, PollStatus.EMPTY, ()
                    ),
                    ("37", "down-source"): PollResult(
                        "down-source", SourceHealth.UNAVAILABLE, PollStatus.UNAVAILABLE, (),
                        "ConnectionError: offline",
                    ),
                }
            def history(self, region_code, source_id, limit=None):
                return ()

        self.service.engine.set_source_health("empty-source", SourceHealth.HEALTHY)
        self.service.engine.set_source_health("down-source", SourceHealth.UNAVAILABLE)
        self.service.attach_scheduler(FakeScheduler())
        status, body = self.get("/ui/sources")
        self.assertEqual(status, 200)
        self.assertIn("Пусто", body)
        self.assertIn("Недоступны", body)
        self.assertIn("ConnectionError: offline", body)

    def test_ui_source_detail_renders_history(self):
        class FakeScheduler:
            regions = ()
            def enabled_sources(self):
                return (ScheduledSource("37", "mchs-ivanovo", 300),)
            def last_results(self):
                return {("37", "mchs-ivanovo"): PollResult(
                    "mchs-ivanovo", SourceHealth.HEALTHY, PollStatus.SUCCESS, ()
                )}
            def history(self, region_code, source_id, limit=None):
                return (PollHistoryEntry(
                    datetime(2026, 10, 6, 20, 30, 0, tzinfo=timezone.utc),
                    PollResult(source_id, SourceHealth.HEALTHY, PollStatus.SUCCESS, ()),
                    0.125,
                ),)

        self.service.attach_scheduler(FakeScheduler())
        status, body = self.get("/ui/sources/37/mchs-ivanovo")
        self.assertEqual(status, 200)
        self.assertIn("История опросов", body)
        self.assertIn("125 мс", body)
        self.assertIn("Успешно", body)

    def test_ui_source_detail_missing_returns_404(self):
        class FakeScheduler:
            regions = ()
            def enabled_sources(self):
                return ()
            def last_results(self):
                return {}
            def history(self, region_code, source_id, limit=None):
                return ()

        self.service.attach_scheduler(FakeScheduler())
        try:
            self.get("/ui/sources/37/missing")
        except Exception as exc:
            self.assertEqual(getattr(exc, "code", None), 404)
        else:
            self.fail("expected HTTP 404")

    def test_ui_filters_region_and_municipality(self):
        first = event("ui-2", "mchs-37")
        first.payload.update({
            "scope": "region",
            "region_code": "37",
            "affected_areas": [{"level": "municipality", "name": "Лежневский район"}],
        })
        second = event("ui-3", "mchs-76")
        second.payload.update({
            "scope": "region",
            "region_code": "76",
            "affected_areas": [{"level": "municipality", "name": "Другой район"}],
        })
        self.service.accept(first)
        self.service.accept(second)
        status, body = self.get("/ui?region=37&municipality=" + quote("Лежневский район"))
        self.assertEqual(status, 200)
        self.assertIn("Лежневский район", body)
        self.assertNotIn('<h2>Другой район</h2>', body)


if __name__ == "__main__":
    unittest.main()
