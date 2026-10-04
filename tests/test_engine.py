import unittest
from datetime import datetime, timedelta, timezone
from alertsrv.engine import AlertEngine
from alertsrv.models import AlertState, NormalizedEvent, Severity, SourceHealth
UTC = timezone.utc
T0 = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
def event(event_id, source_id, *, correlation_key="region:ivanovo:weather:storm",
          severity=Severity.WARNING, confidence=0.8, received_offset=0,
          expires_offset=None, resolved=False):
    received = T0 + timedelta(minutes=received_offset)
    return NormalizedEvent(event_id=event_id, source_id=source_id, event_type="weather.warning",
        title="Storm warning", severity=severity, confidence=confidence, occurred_at=received,
        received_at=received, correlation_key=correlation_key,
        expires_at=(received + timedelta(minutes=expires_offset) if expires_offset is not None else None),
        resolved=resolved)
class AlertEngineTests(unittest.TestCase):
    def test_first_event_becomes_active_and_records_transition(self):
        engine = AlertEngine(); alert = engine.ingest(event("1", "weather-a"))
        self.assertEqual(alert.state, AlertState.ACTIVE); self.assertEqual(len(alert.evidence), 1)
        self.assertEqual(alert.transition_history[0][:2], (AlertState.NEW, AlertState.ACTIVE))
    def test_duplicate_event_is_ignored(self):
        engine = AlertEngine(); first = engine.ingest(event("1", "weather-a"))
        second = engine.ingest(event("1", "weather-a", confidence=0.99))
        self.assertIs(first, second); self.assertEqual(len(first.evidence), 1); self.assertEqual(first.confidence, 0.8)
    def test_different_sources_correlate_to_one_alert(self):
        engine = AlertEngine(); first = engine.ingest(event("1", "weather-a", confidence=0.7))
        second = engine.ingest(event("abc", "emergency-b", severity=Severity.CRITICAL, confidence=0.95))
        self.assertIs(first, second); self.assertEqual(len(first.evidence), 2)
        self.assertEqual(first.severity, Severity.CRITICAL); self.assertEqual(first.confidence, 0.95)
    def test_source_outage_does_not_resolve_alert(self):
        engine = AlertEngine(); alert = engine.ingest(event("1", "weather-a"))
        engine.set_source_health("weather-a", SourceHealth.UNAVAILABLE)
        self.assertEqual(engine.source_health("weather-a"), SourceHealth.UNAVAILABLE); self.assertEqual(alert.state, AlertState.ACTIVE)

    def test_source_recovery_is_independent_from_alert_state(self):
        engine = AlertEngine(); alert = engine.ingest(event("1", "weather-a"))
        engine.set_source_health("weather-a", SourceHealth.UNAVAILABLE)
        engine.set_source_health("weather-a", SourceHealth.HEALTHY)
        self.assertEqual(engine.source_health("weather-a"), SourceHealth.HEALTHY)
        self.assertEqual(alert.state, AlertState.ACTIVE)
        recovered = engine.ingest(event("2", "weather-a", received_offset=5))
        self.assertIs(recovered, alert)
        self.assertEqual(len(alert.evidence), 2)

    def test_repeated_resolution_is_idempotent(self):
        engine = AlertEngine(); alert = engine.ingest(event("1", "weather-a"))
        first = engine.resolve(alert.alert_id, reason="operator")
        second = engine.resolve(alert.alert_id, reason="operator again")
        self.assertIs(first, second)
        self.assertEqual(alert.state, AlertState.RESOLVED)
        self.assertEqual(len(alert.transition_history), 2)
    def test_expiration_is_explicit(self):
        engine = AlertEngine(); alert = engine.ingest(event("1", "weather-a", expires_offset=10))
        self.assertEqual(engine.expire(now=T0 + timedelta(minutes=9)), [])
        expired = engine.expire(now=T0 + timedelta(minutes=10))
        self.assertEqual(expired, [alert]); self.assertEqual(alert.state, AlertState.EXPIRED)
    def test_resolve_event_changes_state(self):
        engine = AlertEngine(); alert = engine.ingest(event("1", "weather-a"))
        engine.ingest(event("2", "weather-a", resolved=True, received_offset=5))
        self.assertEqual(alert.state, AlertState.RESOLVED)
        self.assertEqual(alert.transition_history[-1][:2], (AlertState.ACTIVE, AlertState.RESOLVED))
    def test_resolved_alert_does_not_reactivate_from_late_evidence(self):
        engine = AlertEngine(); alert = engine.ingest(event("1", "weather-a")); engine.resolve(alert.alert_id)
        late = engine.ingest(event("2", "weather-b", received_offset=30))
        self.assertIsNot(alert, late); self.assertEqual(alert.state, AlertState.RESOLVED)
    def test_older_event_cannot_move_updated_at_backwards(self):
        engine = AlertEngine(); alert = engine.ingest(event("1", "weather-a", received_offset=10))
        engine.ingest(event("2", "weather-b", received_offset=5))
        self.assertEqual(alert.updated_at, T0 + timedelta(minutes=10))
if __name__ == "__main__":
    unittest.main()
