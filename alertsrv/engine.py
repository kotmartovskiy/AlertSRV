from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock
from uuid import uuid4

from .freshness import Freshness, FreshnessPolicy
from .hazards import classify_hazard
from .keys import dedup_key
from .models import Alert, AlertState, Evidence, NormalizedEvent, SourceHealth
from .storage import AlertStore


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AlertEngine:
    """Deterministic alert aggregator with serialized state changes."""

    def __init__(
        self,
        *,
        clock=_utcnow,
        store: AlertStore | None = None,
        freshness: FreshnessPolicy | None = None,
    ) -> None:
        self._clock = clock
        self._store = store
        self._freshness = freshness or FreshnessPolicy()
        self._alerts: dict[str, Alert] = {}
        self._event_to_alert: dict[str, str] = {}
        self._source_health: dict[str, SourceHealth] = {}
        self._lock = RLock()
        if store is not None:
            self._alerts = {alert.alert_id: alert for alert in store.load_alerts()}
            self._source_health = store.load_source_health()

    def ingest(self, event: NormalizedEvent) -> Alert:
        with self._lock:
            return self._ingest_locked(event)

    def _ingest_locked(self, event: NormalizedEvent) -> Alert:
        event_key = dedup_key(event.event_id, event.source_id)
        existing_id = self._event_to_alert.get(event_key)
        if existing_id is None and self._store is not None:
            existing_id = self._store.event_alert_id(event_key)
            if existing_id is not None:
                self._event_to_alert[event_key] = existing_id
        if existing_id is not None:
            return self._alerts[existing_id]

        freshness = self._freshness.classify(event, now=self._clock())
        if freshness == Freshness.FUTURE:
            raise ValueError("event received_at is too far in the future")
        if freshness == Freshness.STALE:
            raise ValueError("event received_at is too old")

        alert = self._find_correlated(event)
        evidence = Evidence(
            event_id=event.event_id,
            source_id=event.source_id,
            severity=event.severity,
            confidence=event.confidence,
            occurred_at=event.occurred_at,
            received_at=event.received_at,
            title=event.title,
            payload=dict(event.payload),
        )

        if alert is None:
            alert = Alert(
                alert_id=str(uuid4()),
                correlation_key=event.correlation_key,
                state=AlertState.NEW,
                severity=event.severity,
                confidence=event.confidence,
                title=event.title,
                started_at=event.occurred_at,
                updated_at=event.received_at,
                expires_at=event.expires_at,
            )
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
        if (
            event.resolved
            and alert.state == AlertState.ACTIVE
            and self._all_sources_resolved(alert, resolved_event_id=event.event_id)
        ):
            self._transition(alert, AlertState.RESOLVED, event.received_at, "all contributing sources resolved")

        self._event_to_alert[event_key] = alert.alert_id
        if self._store is not None:
            self._store.save_ingest(alert, event_key, event.received_at)
        return alert

    def resolve(self, alert_id: str, *, reason: str = "manual resolution") -> Alert:
        with self._lock:
            alert = self._require(alert_id)
            if alert.state == AlertState.ACTIVE:
                self._transition(alert, AlertState.RESOLVED, self._clock(), reason)
                if self._store is not None:
                    self._store.save_alert(alert)
            return alert

    def expire(self, *, now: datetime | None = None) -> list[Alert]:
        with self._lock:
            now = now or self._clock()
            expired = []
            for alert in self._alerts.values():
                if alert.state == AlertState.ACTIVE and alert.expires_at is not None and alert.expires_at <= now:
                    self._transition(alert, AlertState.EXPIRED, now, "expiration time reached")
                    if self._store is not None:
                        self._store.save_alert(alert)
                    expired.append(alert)
            return expired

    def prune_event_index(self, *, retention: timedelta) -> int:
        """Prune old dedup mappings for terminal alerts in memory and storage."""
        cutoff = self._clock() - retention
        with self._lock:
            removed_keys = {
                key
                for key, alert_id in self._event_to_alert.items()
                if alert_id in self._alerts
                and self._alerts[alert_id].state
                in {
                    AlertState.RESOLVED,
                    AlertState.EXPIRED,
                    AlertState.CANCELLED,
                    AlertState.SUPERSEDED,
                }
                and any(
                    dedup_key(e.event_id, e.source_id) == key and e.received_at < cutoff
                    for e in self._alerts[alert_id].evidence
                )
            }
            for key in removed_keys:
                self._event_to_alert.pop(key, None)
            if self._store is not None:
                return self._store.prune_event_index(cutoff)
            return len(removed_keys)

    def set_source_health(self, source_id: str, health: SourceHealth) -> None:
        with self._lock:
            self._source_health[source_id] = health
            if self._store is not None:
                self._store.save_source_health(source_id, health)

    def source_health(self, source_id: str) -> SourceHealth:
        with self._lock:
            return self._source_health.get(source_id, SourceHealth.UNKNOWN)

    def source_health_all(self) -> dict[str, SourceHealth]:
        with self._lock:
            return dict(self._source_health)

    def get(self, alert_id: str) -> Alert:
        with self._lock:
            return self._require(alert_id)

    def list_alerts(self, *, state: AlertState | None = None) -> list[Alert]:
        with self._lock:
            alerts = list(self._alerts.values())
            if state is not None:
                alerts = [a for a in alerts if a.state == state]
            return sorted(alerts, key=lambda a: a.started_at)

    @staticmethod
    def _all_sources_resolved(alert: Alert, *, resolved_event_id: str) -> bool:
        """Resolve only after every contributing source has explicitly cleared."""
        latest_by_source: dict[str, Evidence] = {}
        for evidence in alert.evidence:
            previous = latest_by_source.get(evidence.source_id)
            if previous is None or evidence.received_at >= previous.received_at:
                latest_by_source[evidence.source_id] = evidence
        return bool(latest_by_source) and all(
            evidence.event_id == resolved_event_id or evidence.payload.get("resolved") is True
            for evidence in latest_by_source.values()
        )

    def _find_correlated(self, event: NormalizedEvent) -> Alert | None:
        candidates = [
            a
            for a in self._alerts.values()
            if a.correlation_key == event.correlation_key and a.state == AlertState.ACTIVE
        ]
        if candidates:
            return max(candidates, key=lambda a: a.updated_at)

        # Cross-source correlation is deliberately conservative. It requires
        # explicit regional scope, the same normalized hazard class, a short
        # temporal distance, and different source identities. National events
        # therefore cannot be silently attached to a particular region.
        event_region = event.payload.get("region_code")
        event_scope = event.payload.get("scope")
        event_hazard = event.payload.get("hazard_class") or classify_hazard(event.title, event_type=event.event_type)
        event_category = event.payload.get("category")
        event_subtype = event.payload.get("subtype")
        if event_scope != "region" or not event_region:
            return None

        matches: list[Alert] = []
        for alert in self._alerts.values():
            if alert.state != AlertState.ACTIVE:
                continue
            for evidence in reversed(alert.evidence):
                if evidence.source_id == event.source_id:
                    continue
                payload = evidence.payload
                if payload.get("scope") != "region" or payload.get("region_code") != event_region:
                    continue
                hazard = payload.get("hazard_class") or classify_hazard(evidence.title)
                category = payload.get("category")
                subtype = payload.get("subtype")
                if event_category != category:
                    continue
                if event_subtype != subtype:
                    continue
                if hazard != event_hazard:
                    continue
                delta = abs((evidence.occurred_at - event.occurred_at).total_seconds())
                if delta <= 6 * 3600:
                    matches.append(alert)
                    break
        return max(matches, key=lambda a: a.updated_at) if matches else None

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
