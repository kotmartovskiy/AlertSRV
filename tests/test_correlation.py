import unittest
from datetime import datetime, timedelta, timezone

from alertsrv.engine import AlertEngine
from alertsrv.models import NormalizedEvent, Severity

UTC = timezone.utc
T0 = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)


def event(event_id, source_id, *, region="37", hazard="wind", scope="region", minutes=0):
    at = T0 + timedelta(minutes=minutes)
    return NormalizedEvent(
        event_id=event_id,
        source_id=source_id,
        event_type="weather.warning",
        title="Сильный ветер",
        severity=Severity.WARNING,
        confidence=0.9,
        occurred_at=at,
        received_at=at,
        correlation_key=f"{source_id}:{event_id}",
        payload={"region_code": region, "scope": scope, "hazard_class": hazard},
    )


class CorrelationTests(unittest.TestCase):
    def test_regional_different_sources_same_hazard_correlate(self):
        engine = AlertEngine()
        first = engine.ingest(event("1", "mchs-37"))
        second = engine.ingest(event("2", "ros-37", minutes=30))
        self.assertIs(first, second)
        self.assertEqual(len(first.evidence), 2)

    def test_different_hazards_do_not_correlate(self):
        engine = AlertEngine()
        first = engine.ingest(event("1", "mchs-37", hazard="wind"))
        second = engine.ingest(event("2", "ros-37", hazard="heavy_rain", minutes=30))
        self.assertIsNot(first, second)

    def test_different_regions_do_not_correlate(self):
        engine = AlertEngine()
        first = engine.ingest(event("1", "mchs-37", region="37"))
        second = engine.ingest(event("2", "ros-76", region="76", minutes=30))
        self.assertIsNot(first, second)

    def test_national_event_does_not_attach_to_region(self):
        engine = AlertEngine()
        first = engine.ingest(event("1", "mchs-37"))
        second = engine.ingest(event("2", "ros-national", scope="russia", minutes=30))
        self.assertIsNot(first, second)

    def test_correlation_time_window_is_conservative(self):
        engine = AlertEngine()
        first = engine.ingest(event("1", "mchs-37"))
        second = engine.ingest(event("2", "ros-37", minutes=361))
        self.assertIsNot(first, second)


if __name__ == "__main__":
    unittest.main()
