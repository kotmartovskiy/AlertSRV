import unittest
from datetime import datetime, timezone, timedelta

from alertsrv.confidence import ConfidencePolicy, aggregate_confidence, source_reliability
from alertsrv.models import Evidence, Severity


def evidence(source, confidence, kind="official_regional_operational_hq", minutes=0, resolved=False):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minutes)
    return Evidence(
        event_id=f"{source}-{minutes}",
        source_id=source,
        severity=Severity.WARNING,
        confidence=confidence,
        occurred_at=now,
        received_at=now,
        title="test warning",
        payload={"source_kind": kind, "resolved": resolved},
        source_authority="unknown",
        source_authority_score=0.0,
    )


class ConfidenceTests(unittest.TestCase):
    def test_primary_source_preserves_high_parser_confidence(self):
        value = aggregate_confidence([evidence("hq", 0.98)])
        self.assertAlmostEqual(value, 0.9604, places=4)

    def test_same_source_repost_does_not_double_count(self):
        one = aggregate_confidence([evidence("hq", 0.90)])
        two = aggregate_confidence([evidence("hq", 0.50), evidence("hq", 0.90, minutes=1)])
        self.assertAlmostEqual(one, two, places=9)

    def test_independent_corroboration_raises_confidence(self):
        one = aggregate_confidence([evidence("hq", 0.90)])
        two = aggregate_confidence([
            evidence("hq", 0.90),
            evidence("mchs", 0.90, kind="official_civil_defense"),
        ])
        self.assertGreater(two, one)
        self.assertLess(two, 1.0)

    def test_same_publisher_mirrors_do_not_double_count(self):
        one = aggregate_confidence([evidence("site", 0.90)])
        mirror = evidence("telegram", 0.90, kind="official_regional_operational_hq", minutes=1)
        mirror.payload["publisher_id"] = "ivanovo-hq"
        site = evidence("site", 0.90)
        site.payload["publisher_id"] = "ivanovo-hq"
        two = aggregate_confidence([site, mirror])
        self.assertAlmostEqual(one, two, places=9)

    def test_latest_observation_wins_within_publisher_group(self):
        old = evidence("site", 0.40)
        old.payload["publisher_id"] = "ivanovo-hq"
        new = evidence("telegram", 0.90, kind="official_civil_defense", minutes=1)
        new.payload["publisher_id"] = "ivanovo-hq"
        value = aggregate_confidence([old, new])
        expected = aggregate_confidence([new])
        self.assertAlmostEqual(value, expected, places=9)

    def test_unofficial_source_cannot_outrank_primary(self):
        primary = aggregate_confidence([evidence("hq", 0.90)])
        unofficial = aggregate_confidence([evidence("telegram", 0.99, kind="unofficial_feed")])
        self.assertGreater(primary, unofficial)

    def test_resolved_evidence_does_not_boost_active_confidence(self):
        active = aggregate_confidence([evidence("hq", 0.80)])
        with_clear = aggregate_confidence([
            evidence("hq", 0.80),
            evidence("hq", 1.0, minutes=1, resolved=True),
        ])
        self.assertAlmostEqual(active, with_clear, places=9)

    def test_latest_observation_from_source_wins(self):
        low = aggregate_confidence([evidence("hq", 0.40)])
        latest = aggregate_confidence([
            evidence("hq", 0.40),
            evidence("hq", 0.90, minutes=1),
        ])
        self.assertGreater(latest, low)

    def test_unknown_source_is_strongly_discounted(self):
        self.assertEqual(source_reliability("unknown"), 0.10)
        self.assertLess(
            aggregate_confidence([evidence("x", 0.99, kind="unknown")]),
            0.2,
        )

    def test_policy_is_bounded(self):
        with self.assertRaises(ValueError):
            ConfidencePolicy(corroboration_weight=1.1)


if __name__ == "__main__":
    unittest.main()
