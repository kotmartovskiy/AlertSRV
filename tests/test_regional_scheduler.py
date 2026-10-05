import unittest

from alertsrv.engine import AlertEngine
from alertsrv.poller import SourcePoller
from alertsrv.regions.base import RegionModule, RegionSourceSpec
from alertsrv.regions.scheduler import RegionalScheduler


class FakeSource:
    def __init__(self, source_id, calls):
        self.source_id = source_id
        self.calls = calls

    def fetch(self):
        self.calls.append(self.source_id)
        return []


def make_region(code, calls, source_id="test-source", interval=60):
    return RegionModule(
        region_code=code,
        region_name=f"Region {code}",
        timezone="UTC",
        sources=(
            RegionSourceSpec(
                source_id=source_id,
                interval_seconds=interval,
                categories=frozenset({"test"}),
                factory=lambda: FakeSource(source_id, calls),
            ),
        ),
    )


class RegionalSchedulerTests(unittest.TestCase):
    def test_selected_region_is_lazy_until_scheduler_start(self):
        calls = []
        scheduler = RegionalScheduler(SourcePoller(AlertEngine()), (make_region("37", calls),))
        self.assertEqual(
            [(x.region_code, x.source_id, x.interval_seconds) for x in scheduler.enabled_sources()],
            [("37", "test-source", 60)],
        )
        self.assertEqual(calls, [])
        scheduler.start()
        scheduler.stop()
        self.assertEqual(calls, ["test-source"])

    def test_enabled_source_uses_declared_interval(self):
        calls = []
        scheduler = RegionalScheduler(
            SourcePoller(AlertEngine()),
            (make_region("37", calls, interval=120),),
        )
        scheduler.start()
        scheduler.stop()
        self.assertEqual(scheduler.enabled_sources()[0].interval_seconds, 120)

    def test_empty_region_creates_no_sources(self):
        scheduler = RegionalScheduler(SourcePoller(AlertEngine()), ())
        scheduler.start()
        scheduler.stop()
        self.assertEqual(scheduler.enabled_sources(), ())

    def test_history_records_latest_poll(self):
        calls = []
        scheduler = RegionalScheduler(
            SourcePoller(AlertEngine()), (make_region("37", calls),), history_limit=2
        )
        scheduler.start()
        scheduler.stop()
        history = scheduler.history("37", "test-source")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].result.status.value, "empty")
        self.assertEqual(history[0].result.event_count, 0)
        self.assertGreaterEqual(history[0].duration_seconds, 0.0)
        self.assertIsNotNone(history[0].completed_at.tzinfo)

    def test_history_limit_and_unknown_source(self):
        calls = []
        scheduler = RegionalScheduler(
            SourcePoller(AlertEngine()), (make_region("37", calls),), history_limit=1
        )
        scheduler.start()
        scheduler.stop()
        self.assertEqual(len(scheduler.history("37", "test-source", limit=1)), 1)
        with self.assertRaises(KeyError):
            scheduler.history("37", "missing")

    def test_poll_failure_history_contains_error(self):
        class Broken:
            source_id = "broken"
            def fetch(self):
                raise TimeoutError("offline")

        region = RegionModule(
            region_code="37",
            region_name="Ivanovo",
            timezone="UTC",
            sources=(RegionSourceSpec(
                "broken", 60, frozenset({"test"}), lambda: Broken()
            ),),
        )
        scheduler = RegionalScheduler(SourcePoller(AlertEngine()), (region,))
        scheduler.start()
        scheduler.stop()
        history = scheduler.history("37", "broken")
        self.assertEqual(history[0].result.status.value, "unavailable")
        self.assertIn("offline", history[0].result.error)

    def test_poll_failure_does_not_stop_scheduler(self):
        class Broken:
            source_id = "broken"
            def fetch(self):
                raise TimeoutError("offline")

        region = RegionModule(
            region_code="37",
            region_name="Ivanovo",
            timezone="UTC",
            sources=(RegionSourceSpec(
                "broken", 60, frozenset({"test"}), lambda: Broken()
            ),),
        )
        scheduler = RegionalScheduler(SourcePoller(AlertEngine()), (region,))
        scheduler.start()
        scheduler.stop()
        self.assertEqual(scheduler.last_results()[("37", "broken")].status.value, "unavailable")


if __name__ == "__main__":
    unittest.main()
