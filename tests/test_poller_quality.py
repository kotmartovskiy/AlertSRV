import unittest

from alertsrv.engine import AlertEngine
from alertsrv.models import SourceHealth
from alertsrv.poller import PollStatus, SourceFetchResult, SourcePoller
from tests.test_poller import FakeSource, make_event


class SourceQualityTests(unittest.TestCase):
    def test_empty_success_is_explicitly_empty(self):
        result = SourcePoller(AlertEngine()).poll(FakeSource("source-a"))
        self.assertEqual(result.status, PollStatus.EMPTY)
        self.assertEqual(result.health, SourceHealth.HEALTHY)

    def test_stale_result_is_degraded_without_being_unavailable(self):
        class StaleSource:
            source_id = "source-a"

            def fetch(self):
                return SourceFetchResult(
                    events=(make_event("1", "source-a"),),
                    stale=True,
                    detail="upstream publication timestamp is stale",
                )

        result = SourcePoller(AlertEngine()).poll(StaleSource())
        self.assertEqual(result.status, PollStatus.STALE)
        self.assertEqual(result.health, SourceHealth.DEGRADED)
        self.assertIn("stale", result.error or "")

    def test_parser_degradation_is_distinct_from_transport_failure(self):
        class DegradedSource:
            source_id = "source-a"

            def fetch(self):
                return SourceFetchResult(
                    events=(make_event("1", "source-a"),),
                    parser_degraded=True,
                    detail="one malformed item skipped",
                )

        result = SourcePoller(AlertEngine()).poll(DegradedSource())
        self.assertEqual(result.status, PollStatus.DEGRADED)
        self.assertEqual(result.health, SourceHealth.DEGRADED)
        self.assertIn("malformed", result.error or "")

    def test_transport_failure_is_unavailable(self):
        result = SourcePoller(AlertEngine()).poll(
            FakeSource("source-a", error=TimeoutError("timeout"))
        )
        self.assertEqual(result.status, PollStatus.UNAVAILABLE)
        self.assertEqual(result.health, SourceHealth.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
