import unittest
from datetime import datetime, timedelta, timezone

from alertsrv.adapters.test_adapter import make_event
from alertsrv.models import AlertState, Severity
from alertsrv.service import AlertService

T0 = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


class AdapterAndServiceTests(unittest.TestCase):
    def test_adapter_produces_normalized_event(self):
        event = make_event(
            event_id="a1",
            occurred_at=T0,
            severity=Severity.CRITICAL,
            payload={"area": "Ivanovo"},
        )
        self.assertEqual(event.event_type, "test.alert")
        self.assertEqual(event.severity, Severity.CRITICAL)
        self.assertEqual(event.payload["area"], "Ivanovo")

    def test_service_hides_engine_storage_details(self):
        service = AlertService()
        alert = service.accept(make_event(event_id="a1", occurred_at=T0))
        self.assertEqual(service.active(), [alert])
        self.assertEqual(service.all(), [alert])
        service.resolve(alert.alert_id)
        self.assertEqual(alert.state, AlertState.RESOLVED)
        self.assertEqual(service.active(), [])

    def test_resolve_event_through_service(self):
        service = AlertService()
        alert = service.accept(make_event(event_id="a1", occurred_at=T0))
        service.accept(
            make_event(
                event_id="a2",
                occurred_at=T0 + timedelta(minutes=5),
                resolved=True,
            )
        )
        self.assertEqual(alert.state, AlertState.RESOLVED)


if __name__ == "__main__":
    unittest.main()
