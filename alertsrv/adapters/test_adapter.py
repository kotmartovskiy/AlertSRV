from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models import NormalizedEvent, Severity


def make_event(
    *,
    event_id: str,
    source_id: str = "test",
    title: str = "Test alert",
    correlation_key: str = "test:alert",
    severity: Severity = Severity.WARNING,
    confidence: float = 0.8,
    occurred_at: datetime,
    received_at: datetime | None = None,
    expires_at: datetime | None = None,
    resolved: bool = False,
    payload: dict[str, Any] | None = None,
) -> NormalizedEvent:
    return NormalizedEvent(
        event_id=event_id,
        source_id=source_id,
        event_type="test.alert",
        title=title,
        severity=severity,
        confidence=confidence,
        occurred_at=occurred_at,
        received_at=received_at or occurred_at,
        correlation_key=correlation_key,
        expires_at=expires_at,
        resolved=resolved,
        payload=payload or {},
    )
