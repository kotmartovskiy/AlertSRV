from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .engine import AlertEngine
from .models import Alert, NormalizedEvent, SourceHealth


class EventSource(Protocol):
    source_id: str

    def fetch(self) -> list[NormalizedEvent]: ...


@dataclass(frozen=True, slots=True)
class PollResult:
    """Outcome of one source poll.

    An empty successful result is deliberately healthy: absence of new events is
    not evidence that a source failed or that an existing alert was cleared.
    """

    source_id: str
    health: SourceHealth
    events: tuple[NormalizedEvent, ...] = ()
    error: str | None = None

    @property
    def event_count(self) -> int:
        return len(self.events)


class SourcePoller:
    """Execute one adapter and translate transport/runtime failures to health."""

    def __init__(self, engine: AlertEngine) -> None:
        self.engine = engine

    def poll(self, source: EventSource) -> PollResult:
        source_id = source.source_id
        try:
            events = tuple(source.fetch())
        except Exception as exc:
            self.engine.set_source_health(source_id, SourceHealth.UNAVAILABLE)
            return PollResult(
                source_id=source_id,
                health=SourceHealth.UNAVAILABLE,
                error=f"{type(exc).__name__}: {exc}",
            )

        try:
            for event in events:
                if event.source_id != source_id:
                    raise ValueError(
                        f"source {source_id!r} returned event for {event.source_id!r}"
                    )
            self.engine.ingest_batch(events)
        except Exception as exc:
            # Fetch succeeded, but the source response could not be trusted or
            # ingested. Keep this distinct from transport unavailability.
            self.engine.set_source_health(source_id, SourceHealth.DEGRADED)
            return PollResult(
                source_id=source_id,
                health=SourceHealth.DEGRADED,
                events=events,
                error=f"{type(exc).__name__}: {exc}",
            )

        self.engine.set_source_health(source_id, SourceHealth.HEALTHY)
        return PollResult(
            source_id=source_id,
            health=SourceHealth.HEALTHY,
            events=events,
        )

    def poll_many(self, sources: list[EventSource] | tuple[EventSource, ...]) -> list[PollResult]:
        return [self.poll(source) for source in sources]
