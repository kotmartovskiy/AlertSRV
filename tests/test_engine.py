import unittest
from concurrent.futures import ThreadPoolExecutor
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
        payload={"resolved": resolved}, resolved=resolved)
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

    def test_one_source_clear_does_not_resolve_multi_source_alert(self):
        engine = AlertEngine()
        alert = engine.ingest(event("1", "weather-a", confidence=0.7))
        engine.ingest(event("2", "emergency-b", confidence=0.9, received_offset=1))
        engine.ingest(event("3", "weather-a", resolved=True, received_offset=2))
        self.assertEqual(alert.state, AlertState.ACTIVE)
        engine.ingest(event("4", "emergency-b", resolved=True, received_offset=3))
        self.assertEqual(alert.state, AlertState.RESOLVED)
    def test_clear_then_new_warning_from_same_source_creates_new_alert(self):
        engine = AlertEngine()
        alert = engine.ingest(event("1", "weather-a"))
        engine.ingest(event("2", "weather-a", resolved=True, received_offset=5))
        fresh = engine.ingest(event("3", "weather-a", received_offset=10))
        self.assertEqual(alert.state, AlertState.RESOLVED)
        self.assertIsNot(alert, fresh)
        self.assertEqual(fresh.state, AlertState.ACTIVE)

    def test_one_source_clear_followed_by_new_warning_keeps_aggregate_active(self):
        engine = AlertEngine()
        alert = engine.ingest(event("1", "weather-a"))
        engine.ingest(event("2", "emergency-b", received_offset=1))
        engine.ingest(event("3", "weather-a", resolved=True, received_offset=2))
        fresh = engine.ingest(event("4", "weather-a", received_offset=3))
        self.assertIs(alert, fresh)
        self.assertEqual(alert.state, AlertState.ACTIVE)

    def test_resolved_alert_does_not_reactivate_from_late_evidence(self):
        engine = AlertEngine(); alert = engine.ingest(event("1", "weather-a")); engine.resolve(alert.alert_id)
        late = engine.ingest(event("2", "weather-b", received_offset=30))
        self.assertIsNot(alert, late); self.assertEqual(alert.state, AlertState.RESOLVED)

    def test_authoritative_cancel_maps_to_cancelled(self):
        engine = AlertEngine()
        alert = engine.ingest(event("1", "official-hq"))
        cleared = event("2", "official-hq", resolved=True, received_offset=5)
        cleared.payload.update({
            "category": "public_safety",
            "source_kind": "official_mchs",
            "resolution_type": "cancel",
        })
        engine.ingest(cleared)
        self.assertEqual(alert.state, AlertState.CANCELLED)
        self.assertEqual(alert.transition_history[-1][:2], (AlertState.ACTIVE, AlertState.CANCELLED))

    def test_authoritative_superseded_maps_to_superseded(self):
        engine = AlertEngine()
        alert = engine.ingest(event("1", "official-hq"))
        replaced = event("2", "official-hq", resolved=True, received_offset=5)
        replaced.payload.update({
            "category": "public_safety",
            "source_kind": "official_mchs",
            "resolution_type": "superseded",
        })
        engine.ingest(replaced)
        self.assertEqual(alert.state, AlertState.SUPERSEDED)

    def test_weak_source_cannot_cancel_safety_alert(self):
        engine = AlertEngine()
        alert = engine.ingest(event("1", "official-hq"))
        cleared = event("2", "unofficial", resolved=True, received_offset=5)
        cleared.payload.update({
            "category": "public_safety",
            "source_kind": "unknown",
            "resolution_type": "cancel",
        })
        engine.ingest(cleared)
        self.assertEqual(alert.state, AlertState.ACTIVE)

    def test_terminal_state_cannot_transition_again(self):
        engine = AlertEngine()
        alert = engine.ingest(event("1", "weather-a"))
        engine.resolve(alert.alert_id)
        with self.assertRaises(ValueError):
            engine._transition(alert, AlertState.ACTIVE, T0, "invalid reactivation")

    def test_new_state_cannot_skip_active(self):
        candidate = AlertEngine().ingest(event("transition-skip", "weather-a"))
        candidate.state = AlertState.NEW
        with self.assertRaises(ValueError):
            AlertEngine._transition(candidate, AlertState.RESOLVED, T0, "invalid skip")

    def test_active_state_all_terminal_transitions_are_allowed(self):
        for terminal in (
            AlertState.RESOLVED,
            AlertState.EXPIRED,
            AlertState.CANCELLED,
            AlertState.SUPERSEDED,
        ):
            alert = AlertEngine().ingest(event(f"transition-{terminal.value}", "weather-a"))
            AlertEngine._transition(alert, terminal, T0, "valid terminal transition")
            self.assertEqual(alert.state, terminal)

    def test_older_event_cannot_move_updated_at_backwards(self):
        engine = AlertEngine(); alert = engine.ingest(event("1", "weather-a", received_offset=10))
        engine.ingest(event("2", "weather-b", received_offset=5))
        self.assertEqual(alert.updated_at, T0 + timedelta(minutes=10))

    def test_concurrent_duplicate_ingest_is_idempotent(self):
        engine = AlertEngine()
        incoming = event("parallel-1", "weather-a")
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(engine.ingest, [incoming] * 32))
        self.assertEqual(len({alert.alert_id for alert in results}), 1)
        self.assertEqual(len(results[0].evidence), 1)
if __name__ == "__main__":
    unittest.main()
