import unittest
from datetime import timedelta

from alertsrv.engine import AlertEngine
from alertsrv.freshness import Freshness, FreshnessPolicy
from tests.test_engine import T0, event


class FreshnessTests(unittest.TestCase):
    def test_classification(self):
        policy = FreshnessPolicy(max_age=timedelta(minutes=30), max_future_skew=timedelta(minutes=5))
        engine = AlertEngine(clock=lambda: T0, freshness=policy)

        self.assertEqual(policy.classify(event("1", "s", received_offset=0), now=T0), Freshness.FRESH)
        self.assertEqual(policy.classify(event("2", "s", received_offset=-31), now=T0), Freshness.STALE)
        self.assertEqual(policy.classify(event("3", "s", received_offset=6), now=T0), Freshness.FUTURE)

    def test_stale_event_does_not_create_alert(self):
        policy = FreshnessPolicy(max_age=timedelta(minutes=30))
        engine = AlertEngine(clock=lambda: T0, freshness=policy)
        with self.assertRaisesRegex(ValueError, "too old"):
            engine.ingest(event("1", "s", received_offset=-31))
        self.assertEqual(engine.list_alerts(), [])

    def test_future_event_does_not_create_alert(self):
        policy = FreshnessPolicy(max_future_skew=timedelta(minutes=5))
        engine = AlertEngine(clock=lambda: T0, freshness=policy)
        with self.assertRaisesRegex(ValueError, "too far in the future"):
            engine.ingest(event("1", "s", received_offset=6))
        self.assertEqual(engine.list_alerts(), [])


if __name__ == "__main__":
    unittest.main()
