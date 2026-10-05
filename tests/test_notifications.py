import unittest
from datetime import datetime, timezone

from alertsrv.engine import AlertEngine
from alertsrv.models import Severity
from alertsrv.notifications import DeliveryState, NotificationDispatcher

UTC = timezone.utc
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


class _Adapter:
    def __init__(self, channel, error=None):
        self.channel = channel
        self.error = error
        self.sent = []

    def send(self, notification):
        if self.error:
            raise RuntimeError(self.error)
        self.sent.append(notification)


class NotificationTests(unittest.TestCase):
    def _alert(self):
        engine = AlertEngine()
        return engine.ingest(
            __import__("alertsrv.models", fromlist=["NormalizedEvent"]).NormalizedEvent(
                event_id="warning",
                source_id="source",
                event_type="weather.warning",
                title="Storm warning",
                severity=Severity.WARNING,
                confidence=0.9,
                occurred_at=NOW,
                received_at=NOW,
                correlation_key="weather:storm",
            )
        )

    def test_successful_delivery_is_recorded_per_channel(self):
        alert = self._alert()
        adapter = _Adapter("local")
        dispatcher = NotificationDispatcher()

        result = dispatcher.dispatch(alert, adapters=[adapter], body="Warning", now=NOW)

        self.assertEqual(result[0].state, DeliveryState.SENT)
        self.assertEqual(result[0].attempts, 1)
        self.assertEqual(result[0].notification.channel, "local")
        self.assertEqual(adapter.sent[0].body, "Warning")
        self.assertIs(dispatcher.get(result[0].notification.notification_id), result[0])

    def test_failed_channel_does_not_change_alert_state(self):
        alert = self._alert()
        adapter = _Adapter("broken", error="transport down")
        dispatcher = NotificationDispatcher()

        result = dispatcher.dispatch(alert, adapters=[adapter], now=NOW)

        self.assertEqual(result[0].state, DeliveryState.FAILED)
        self.assertEqual(result[0].attempts, 1)
        self.assertEqual(result[0].error, "transport down")
        self.assertEqual(alert.state.value, "active")

    def test_channels_are_independent(self):
        alert = self._alert()
        good = _Adapter("local")
        bad = _Adapter("broken", error="down")
        dispatcher = NotificationDispatcher()

        result = dispatcher.dispatch(alert, adapters=[good, bad], now=NOW)

        self.assertEqual([item.state for item in result], [DeliveryState.SENT, DeliveryState.FAILED])
        self.assertEqual(len(dispatcher.all()), 2)


if __name__ == "__main__":
    unittest.main()
