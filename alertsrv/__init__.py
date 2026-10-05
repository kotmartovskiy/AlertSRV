"""AlertSRV — local-first alert aggregation service."""

from .freshness import Freshness, FreshnessPolicy
from .models import Alert, AlertState, NormalizedEvent, Severity, SourceHealth
from .poller import EventSource, PollResult, SourcePoller
from .service import AlertService
from .source_authority import SourceAuthority, SourceAuthorityPolicy, source_authority

__all__ = [
    "Alert",
    "AlertState",
    "AlertService",
    "EventSource",
    "NormalizedEvent",
    "PollResult",
    "Severity",
    "SourceHealth",
    "SourcePoller",
    "SourceAuthority",
    "SourceAuthorityPolicy",
    "source_authority",
]
