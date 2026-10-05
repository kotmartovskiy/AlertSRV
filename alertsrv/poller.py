from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .engine import AlertEngine
from .models import Alert, NormalizedEvent, SourceHealth


class PollStatus(str, Enum):
    SUCCESS = "success"
    EMPTY = "empty"
    STALE = "stale"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SourceFetchResult:
    """Optional adapter metadata that distinguishes successful absence from degraded data."""
    events: tuple[NormalizedEvent, ...] = ()
    stale: bool = False
    parser_degraded: bool = False
    detail: str | None = None


class EventSource(Protocol):
    source_id: str

    def fetch(self) -> list[NormalizedEvent] | SourceFetchResult: ...


@dataclass(frozen=True, slots=True)
class PollResult:
    """Outcome of one source poll with transport and data-quality semantics separated."""
    source_id: str
    health: SourceHealth
    status: PollStatus
    events: tuple[NormalizedEvent, ...] = ()
    error: str | None = None

    @property
    def event_count(self) -> int:
        return len(self.events)


class SourcePoller:
    """Execute one adapter and translate transport/data-quality failures to health."""

    def __init__(self, engine: AlertEngine) -> None:
        self.engine = engine

    def poll(self, source: EventSource) -> PollResult:
        source_id = source.source_id
        try:
            fetched = source.fetch()
            if isinstance(fetched, SourceFetchResult):
                result = fetched
            else:
                result = SourceFetchResult(events=tuple(fetched))
        except Exception as exc:
            self.engine.set_source_health(source_id, SourceHealth.UNAVAILABLE)
            return PollResult(
                source_id=source_id,
                health=SourceHealth.UNAVAILABLE,
                status=PollStatus.UNAVAILABLE,
                error=f"{type(exc).__name__}: {exc}",
            )

        events = tuple(result.events)
        try:
            for event in events:
                if event.source_id != source_id:
                    raise ValueError(
                        f"source {source_id!r} returned event for {event.source_id!r}"
                    )
            self.engine.ingest_batch(events)
        except Exception as exc:
            self.engine.set_source_health(source_id, SourceHealth.DEGRADED)
            return PollResult(
                source_id=source_id,
                health=SourceHealth.DEGRADED,
                status=PollStatus.DEGRADED,
                events=events,
                error=f"{type(exc).__name__}: {exc}",
            )

        if result.parser_degraded:
            health = SourceHealth.DEGRADED
            status = PollStatus.DEGRADED
        elif result.stale:
            health = SourceHealth.DEGRADED
            status = PollStatus.STALE
        elif not events:
            health = SourceHealth.HEALTHY
            status = PollStatus.EMPTY
        else:
            health = SourceHealth.HEALTHY
            status = PollStatus.SUCCESS

        self.engine.set_source_health(source_id, health)
        return PollResult(
            source_id=source_id,
            health=health,
            status=status,
            events=events,
            error=result.detail,
        )

    def poll_many(self, sources: list[EventSource] | tuple[EventSource, ...]) -> list[PollResult]:
        return [self.poll(source) for source in sources]
