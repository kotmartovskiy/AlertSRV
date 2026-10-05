from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..poller import EventSource

SourceFactory = Callable[[], EventSource]


@dataclass(frozen=True, slots=True)
class RegionSourceSpec:
    """Lazy regional source definition.

    The factory is called only when the region is enabled, so merely importing
    the catalog never creates adapters or performs network requests.
    """

    source_id: str
    interval_seconds: int
    categories: frozenset[str]
    factory: SourceFactory

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id is required")
        if self.interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")


@dataclass(frozen=True, slots=True)
class RegionModule:
    """Static configuration for one independently selectable region."""

    region_code: str
    region_name: str
    timezone: str
    sources: tuple[RegionSourceSpec, ...]

    def __post_init__(self) -> None:
        if not self.region_code or not self.region_name:
            raise ValueError("region_code and region_name are required")
        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("region source IDs must be unique")

    def source_ids(self) -> tuple[str, ...]:
        return tuple(source.source_id for source in self.sources)

    def create_sources(self) -> tuple[EventSource, ...]:
        """Instantiate only this region's adapters; no other region is touched."""
        return tuple(spec.factory() for spec in self.sources)
