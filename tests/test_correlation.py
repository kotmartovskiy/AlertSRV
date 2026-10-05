import unittest
from datetime import datetime, timedelta, timezone

from alertsrv.engine import AlertEngine
from alertsrv.models import NormalizedEvent, Severity

UTC = timezone.utc
T0 = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)


def event(event_id, source_id, *, region="37", hazard="wind", category="weather", subtype="wind", scope="region", minutes=0):
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
        payload={"region_code": region, "scope": scope, "hazard_class": hazard, "category": category, "subtype": subtype},
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

    def test_different_semantic_categories_do_not_correlate(self):
        engine = AlertEngine()
        first = engine.ingest(event("1", "mchs-37", hazard="other", category="weather", subtype="other"))
        second = engine.ingest(event("2", "ros-37", hazard="other", category="air_threat", subtype="drone_warning", minutes=30))
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

    def test_same_source_does_not_cross_correlate_without_exact_key(self):
        engine = AlertEngine()
        first = engine.ingest(event("1", "mchs-37"))
        second = engine.ingest(event("2", "mchs-37", minutes=30))
        self.assertIsNot(first, second)

    def test_missing_category_does_not_cross_correlate(self):
        engine = AlertEngine()
        first = engine.ingest(event("1", "mchs-37", category="weather"))
        second = event("2", "ros-37", minutes=30)
        second.payload.pop("category")
        second.payload.pop("subtype")
        self.assertIsNot(first, engine.ingest(second))

    def test_correlation_time_window_is_conservative(self):
        engine = AlertEngine()
        first = engine.ingest(event("1", "mchs-37"))
        second = engine.ingest(event("2", "ros-37", minutes=361))
        self.assertIsNot(first, second)

    def test_region_wide_event_does_not_merge_with_local_area(self):
        engine = AlertEngine()
        first = engine.ingest(event("1", "mchs-37"))
        second = event("2", "ros-37", minutes=30)
        second.payload["geography_precision"] = "municipality"
        second.payload["affected_areas"] = [{"level": "municipality", "name": "Лежневский район"}]
        self.assertIsNot(first, engine.ingest(second))

    def test_same_municipality_correlates(self):
        engine = AlertEngine()
        first = event("1", "mchs-37", minutes=0)
        first.payload["geography_precision"] = "municipality"
        first.payload["affected_areas"] = [{"level": "municipality", "name": "Лежневский район"}]
        second = event("2", "ros-37", minutes=30)
        second.payload["geography_precision"] = "municipality"
        second.payload["affected_areas"] = [{"level": "municipality", "name": "Лежневский район"}]
        self.assertIs(engine.ingest(first), engine.ingest(second))

    def test_different_municipalities_do_not_correlate(self):
        engine = AlertEngine()
        first = event("1", "mchs-37")
        second = event("2", "ros-37", minutes=30)
        for e, name in ((first, "Лежневский район"), (second, "Шуйский район")):
            e.payload["geography_precision"] = "municipality"
            e.payload["affected_areas"] = [{"level": "municipality", "name": name}]
        self.assertIsNot(engine.ingest(first), engine.ingest(second))

    def test_different_settlements_in_same_municipality_do_not_correlate(self):
        engine = AlertEngine()
        first = event("1", "mchs-37")
        second = event("2", "ros-37", minutes=30)
        for e, name in ((first, "д. Кунятиха"), (second, "с. Новое")):
            e.payload["geography_precision"] = "settlement"
            e.payload["affected_areas"] = [{"level": "settlement", "name": name, "municipality": "Лежневский район"}]
        self.assertIsNot(engine.ingest(first), engine.ingest(second))

    def test_settlement_and_parent_municipality_do_not_correlate(self):
        engine = AlertEngine()
        first = event("1", "mchs-37")
        first.payload["geography_precision"] = "settlement"
        first.payload["affected_areas"] = [{"level": "settlement", "name": "д. Кунятиха", "municipality": "Лежневский район"}]
        second = event("2", "ros-37", minutes=30)
        second.payload["geography_precision"] = "municipality"
        second.payload["affected_areas"] = [{"level": "municipality", "name": "Лежневский район"}]
        self.assertIsNot(engine.ingest(first), engine.ingest(second))

    def test_different_farms_do_not_correlate_even_with_same_region(self):
        engine = AlertEngine()
        first = event("1", "mchs-37")
        second = event("2", "ros-37", minutes=30)
        for e, cadastral in ((first, "37:09:010338:245"), (second, "37:09:010338:246")):
            e.payload["geography_precision"] = "farm"
            e.payload["affected_areas"] = [{"level": "farm", "name": "Хозяйство", "cadastral_number": cadastral}]
        self.assertIsNot(engine.ingest(first), engine.ingest(second))

    def test_same_farm_correlates_by_cadastral_number(self):
        engine = AlertEngine()
        first = event("1", "mchs-37")
        second = event("2", "ros-37", minutes=30)
        for e in (first, second):
            e.payload["geography_precision"] = "farm"
            e.payload["affected_areas"] = [{"level": "farm", "name": "Хозяйство", "cadastral_number": "37:09:010338:245"}]
        self.assertIs(engine.ingest(first), engine.ingest(second))


if __name__ == "__main__":
    unittest.main()
