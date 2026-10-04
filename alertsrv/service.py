from __future__ import annotations

from .engine import AlertEngine
from .models import Alert, AlertState, NormalizedEvent


class AlertService:
    """Application-facing facade around the AlertEngine."""

    def __init__(self, engine: AlertEngine | None = None) -> None:
        self.engine = engine or AlertEngine()

    def accept(self, event: NormalizedEvent) -> Alert:
        return self.engine.ingest(event)

    def resolve(self, alert_id: str, reason: str = "manual resolution") -> Alert:
        return self.engine.resolve(alert_id, reason=reason)

    def expire(self) -> list[Alert]:
        return self.engine.expire()

    def get(self, alert_id: str) -> Alert:
        return self.engine.get(alert_id)

    def active(self) -> list[Alert]:
        return self.engine.list_alerts(state=AlertState.ACTIVE)

    def all(self) -> list[Alert]:
        return self.engine.list_alerts()
