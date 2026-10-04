from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from .keys import dedup_key
from .models import Alert, AlertState, Evidence, NormalizedEvent, SourceHealth
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
class AlertEngine:
    """Deterministic in-memory alert aggregator."""
    def __init__(self, *, clock=_utcnow) -> None:
        self._clock = clock
        self._alerts: dict[str, Alert] = {}
        self._event_to_alert: dict[str, str] = {}
        self._source_health: dict[str, SourceHealth] = {}
    def ingest(self, event: NormalizedEvent) -> Alert:
        event_key = dedup_key(event.event_id, event.source_id)
        existing_id = self._event_to_alert.get(event_key)
        if existing_id is not None:
            return self._alerts[existing_id]
        alert = self._find_correlated(event)
        evidence = Evidence(event_id=event.event_id, source_id=event.source_id,
            severity=event.severity, confidence=event.confidence, occurred_at=event.occurred_at,
            received_at=event.received_at, title=event.title, payload=dict(event.payload))
        if alert is None:
            alert = Alert(alert_id=str(uuid4()), correlation_key=event.correlation_key,
                state=AlertState.NEW, severity=event.severity, confidence=event.confidence,
                title=event.title, started_at=event.occurred_at, updated_at=event.received_at,
                expires_at=event.expires_at)
            self._alerts[alert.alert_id] = alert
            self._transition(alert, AlertState.ACTIVE, event.received_at, "first observation")
        else:
            if alert.state != AlertState.ACTIVE:
                return alert
            if event.occurred_at < alert.started_at:
                alert.started_at = event.occurred_at
            if event.received_at >= alert.updated_at:
                alert.updated_at = event.received_at
                if event.title:
                    alert.title = event.title
            if event.severity.rank > alert.severity.rank:
                alert.severity = event.severity
            if event.confidence > alert.confidence:
                alert.confidence = event.confidence
            if event.expires_at is not None:
                if alert.expires_at is None or event.expires_at > alert.expires_at:
                    alert.expires_at = event.expires_at
        alert.evidence.append(evidence)
        self._event_to_alert[event_key] = alert.alert_id
        if event.resolved and alert.state == AlertState.ACTIVE:
            self._transition(alert, AlertState.RESOLVED, event.received_at, "source resolved event")
        return alert
    def resolve(self, alert_id: str, *, reason: str = "manual resolution") -> Alert:
        alert = self._require(alert_id)
        if alert.state == AlertState.ACTIVE:
            self._transition(alert, AlertState.RESOLVED, self._clock(), reason)
        return alert
    def expire(self, *, now: datetime | None = None) -> list[Alert]:
        now = now or self._clock()
        expired = []
        for alert in self._alerts.values():
            if alert.state == AlertState.ACTIVE and alert.expires_at is not None and alert.expires_at <= now:
                self._transition(alert, AlertState.EXPIRED, now, "expiration time reached")
                expired.append(alert)
        return expired
    def set_source_health(self, source_id: str, health: SourceHealth) -> None:
        self._source_health[source_id] = health
    def source_health(self, source_id: str) -> SourceHealth:
        return self._source_health.get(source_id, SourceHealth.UNKNOWN)
    def get(self, alert_id: str) -> Alert:
        return self._require(alert_id)
    def list_alerts(self, *, state: AlertState | None = None) -> list[Alert]:
        alerts = list(self._alerts.values())
        if state is not None:
            alerts = [a for a in alerts if a.state == state]
        return sorted(alerts, key=lambda a: a.started_at)
    def _find_correlated(self, event: NormalizedEvent) -> Alert | None:
        candidates = [a for a in self._alerts.values()
                      if a.correlation_key == event.correlation_key and a.state == AlertState.ACTIVE]
        return max(candidates, key=lambda a: a.updated_at) if candidates else None
    @staticmethod
    def _transition(alert: Alert, new_state: AlertState, at: datetime, reason: str) -> None:
        old_state = alert.state
        if old_state == new_state:
            return
        alert.state = new_state
        alert.updated_at = max(alert.updated_at, at)
        alert.transition_history.append((old_state, new_state, at, reason))
    def _require(self, alert_id: str) -> Alert:
        try:
            return self._alerts[alert_id]
        except KeyError:
            raise KeyError(f"unknown alert: {alert_id}") from None
