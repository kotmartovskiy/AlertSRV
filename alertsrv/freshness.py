from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from .models import NormalizedEvent


class Freshness(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    FUTURE = "future"


@dataclass(frozen=True, slots=True)
class FreshnessPolicy:
    """Classifies event timing without deciding alert severity or resolution."""

    max_age: timedelta | None = None
    max_future_skew: timedelta | None = None

    def classify(self, event: NormalizedEvent, *, now: datetime) -> Freshness:
        if self.max_future_skew is not None and event.received_at > now + self.max_future_skew:
            return Freshness.FUTURE
        if self.max_age is not None and event.received_at < now - self.max_age:
            return Freshness.STALE
        return Freshness.FRESH
