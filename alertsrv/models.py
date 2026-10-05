from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    @property
    def rank(self) -> int:
        return {Severity.INFO: 10, Severity.WARNING: 20, Severity.CRITICAL: 30}[self]

class AlertState(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    RESOLVED = "resolved"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"

class EventCategory(str, Enum):
    WEATHER = "weather"
    HYDROLOGY = "hydrology"
    AIR_THREAT = "air_threat"
    EMERGENCY_MODE = "emergency_mode"
    QUARANTINE = "quarantine"
    PUBLIC_SAFETY = "public_safety"
    INFRASTRUCTURE = "infrastructure"
    EPIDEMIOLOGY = "epidemiology"
    OTHER = "other"


class ResolutionType(str, Enum):
    ALL_CLEAR = "all_clear"
    CANCEL = "cancel"
    SUPERSEDED = "superseded"


class SourceHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"

@dataclass(frozen=True, slots=True)
class NormalizedEvent:
    event_id: str
    source_id: str
    event_type: str
    title: str
    severity: Severity
    confidence: float
    occurred_at: datetime
    received_at: datetime
    correlation_key: str
    payload: dict[str, Any] = field(default_factory=dict)
    expires_at: datetime | None = None
    resolved: bool = False
    category: EventCategory | None = None
    subtype: str | None = None
    resolution_type: ResolutionType | None = None
    replacement_event_id: str | None = None
    replacement_source_id: str | None = None
    source_authority: str = "unknown"
    source_authority_score: float = 0.0
    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not self.event_id or not self.source_id or not self.correlation_key:
            raise ValueError("event_id, source_id and correlation_key are required")
        if not 0.0 <= self.source_authority_score <= 1.0:
            raise ValueError("source_authority_score must be between 0.0 and 1.0")
        if self.expires_at is not None and self.expires_at < self.occurred_at:
            raise ValueError("expires_at cannot precede occurred_at")
        # Typed lifecycle semantics are validated when supplied. Legacy events
        # that only carry payload metadata remain accepted for compatibility.
        safety_categories = {
            EventCategory.AIR_THREAT,
            EventCategory.EMERGENCY_MODE,
            EventCategory.QUARANTINE,
            EventCategory.PUBLIC_SAFETY,
        }
        if self.category in safety_categories and self.resolved and self.resolution_type is None:
            raise ValueError("safety-critical resolved events require resolution_type")
        if self.replacement_event_id is not None and self.resolution_type is not ResolutionType.SUPERSEDED:
            raise ValueError("replacement_event_id requires resolution_type=superseded")
        if self.replacement_source_id is not None and self.replacement_event_id is None:
            raise ValueError("replacement_source_id requires replacement_event_id")
        if self.resolution_type is ResolutionType.SUPERSEDED and self.replacement_event_id is None:
            raise ValueError("superseded events require replacement_event_id")
        if self.resolution_type is ResolutionType.ALL_CLEAR and (
            self.replacement_event_id is not None or self.replacement_source_id is not None
        ):
            raise ValueError("all_clear events cannot carry replacement references")

@dataclass(frozen=True, slots=True)
class Evidence:
    event_id: str
    source_id: str
    severity: Severity
    confidence: float
    occurred_at: datetime
    received_at: datetime
    title: str
    payload: dict[str, Any] = field(default_factory=dict)
    source_authority: str = "unknown"
    source_authority_score: float = 0.0

@dataclass(slots=True)
class Alert:
    alert_id: str
    correlation_key: str
    state: AlertState
    severity: Severity
    confidence: float
    title: str
    started_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
    source_authority: str = "unknown"
    source_authority_score: float = 0.0
    superseded_by: str | None = None
    supersedes_alert_id: str | None = None
    evidence: list[Evidence] = field(default_factory=list)
    transition_history: list[tuple[AlertState, AlertState, datetime, str]] = field(default_factory=list)
