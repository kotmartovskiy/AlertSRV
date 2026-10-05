import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from alertsrv.engine import AlertEngine
from alertsrv.freshness import FreshnessPolicy
from alertsrv.models import AlertState, NormalizedEvent, Severity, SourceHealth
from alertsrv.poller import SourcePoller


T0 = datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc)


def make_event(event_id: str, source_id: str, *, resolved: bool = False) -> NormalizedEvent:
    return NormalizedEvent(
        event_id=event_id,
        source_id=source_id,
        event_type="test.warning",
        title="Test warning",
        severity=Severity.WARNING,
        confidence=0.9,
        occurred_at=T0,
        received_at=T0,
        correlation_key=f"test:{source_id}",
        payload={"resolved": resolved},
        resolved=resolved,
    )


@dataclass
class FakeSource:
    source_id: str
    events: list[NormalizedEvent] | None = None
    error: Exception | None = None

    def fetch(self) -> list[NormalizedEvent]:
        if self.error is not None:
            raise self.error
        return list(self.events or [])


class SourcePollerTests(unittest.TestCase):
    def test_successful_empty_poll_is_healthy(self):
        engine = AlertEngine()
        result = SourcePoller(engine).poll(FakeSource("source-a"))
        self.assertEqual(result.health, SourceHealth.HEALTHY)
        self.assertEqual(result.event_count, 0)
        self.assertIsNone(result.error)
        self.assertEqual(engine.source_health("source-a"), SourceHealth.HEALTHY)

    def test_successful_poll_ingests_events(self):
        engine = AlertEngine()
        source = FakeSource("source-a", [make_event("1", "source-a")])
        result = SourcePoller(engine).poll(source)
        self.assertEqual(result.event_count, 1)
        self.assertEqual(engine.source_health("source-a"), SourceHealth.HEALTHY)
        self.assertEqual(len(engine.list_alerts(state=AlertState.ACTIVE)), 1)

    def test_failure_marks_source_unavailable(self):
        engine = AlertEngine()
        result = SourcePoller(engine).poll(FakeSource("source-a", error=TimeoutError("timed out")))
        self.assertEqual(result.health, SourceHealth.UNAVAILABLE)
        self.assertIn("TimeoutError", result.error or "")
        self.assertEqual(engine.source_health("source-a"), SourceHealth.UNAVAILABLE)

    def test_failure_does_not_resolve_existing_alert(self):
        engine = AlertEngine()
        engine.ingest(make_event("1", "source-a"))
        result = SourcePoller(engine).poll(FakeSource("source-a", error=ConnectionError("offline")))
        self.assertEqual(result.health, SourceHealth.UNAVAILABLE)
        alerts = engine.list_alerts(state=AlertState.ACTIVE)
        self.assertEqual(len(alerts), 1)

    def test_recovery_is_healthy_but_does_not_change_alert_lifecycle(self):
        engine = AlertEngine()
        alert = engine.ingest(make_event("1", "source-a"))
        poller = SourcePoller(engine)
        poller.poll(FakeSource("source-a", error=OSError("offline")))
        result = poller.poll(FakeSource("source-a"))
        self.assertEqual(result.health, SourceHealth.HEALTHY)
        self.assertEqual(alert.state, AlertState.ACTIVE)

    def test_source_mismatch_degrades_source_without_raising_to_scheduler(self):
        engine = AlertEngine()
        source = FakeSource("source-a", [make_event("1", "source-b")])
        result = SourcePoller(engine).poll(source)
        self.assertEqual(result.health, SourceHealth.DEGRADED)
        self.assertIn("ValueError", result.error or "")
        self.assertEqual(engine.source_health("source-a"), SourceHealth.DEGRADED)

    def test_invalid_event_does_not_partially_apply_poll_batch(self):
        engine = AlertEngine(clock=lambda: T0, freshness=FreshnessPolicy(max_age=timedelta(minutes=30)))
        valid = make_event("valid", "source-a")
        stale = NormalizedEvent(
            event_id="stale", source_id="source-a", event_type="test.warning", title="Stale warning",
            severity=Severity.WARNING, confidence=0.9, occurred_at=T0, received_at=T0.replace(hour=5),
            correlation_key="test:stale",
        )
        result = SourcePoller(engine).poll(FakeSource("source-a", [valid, stale]))
        self.assertEqual(result.health, SourceHealth.DEGRADED)
        self.assertEqual(engine.list_alerts(), [])

    def test_poll_many_isolated(self):
        engine = AlertEngine()
        results = SourcePoller(engine).poll_many([
            FakeSource("source-a"),
            FakeSource("source-b", error=RuntimeError("broken")),
        ])
        self.assertEqual([r.health for r in results], [SourceHealth.HEALTHY, SourceHealth.UNAVAILABLE])


if __name__ == "__main__":
    unittest.main()
