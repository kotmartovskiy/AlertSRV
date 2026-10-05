from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock, Thread, current_thread
from time import monotonic
from .base import RegionModule
from ..poller import EventSource, PollResult, SourcePoller


@dataclass(frozen=True, slots=True)
class ScheduledSource:
    region_code: str
    source_id: str
    interval_seconds: int


class RegionalScheduler:
    """One low-overhead worker for explicitly enabled regional modules."""

    def __init__(
        self,
        poller: SourcePoller,
        regions: tuple[RegionModule, ...] | list[RegionModule] = (),
        *,
        clock=monotonic,
    ) -> None:
        self.poller = poller
        self.regions = tuple(regions)
        self.clock = clock
        self._stop = Event()
        self._lock = Lock()
        self._sources: dict[tuple[str, str], EventSource] = {}
        self._specs: dict[tuple[str, str], ScheduledSource] = {}
        self._next_due: dict[tuple[str, str], float] = {}
        self._last_results: dict[tuple[str, str], PollResult] = {}
        self._thread: Thread | None = None

    def _prepare(self, now: float) -> None:
        if self._sources:
            return
        for region in self.regions:
            for spec, source in zip(region.sources, region.create_sources()):
                key = (region.region_code, spec.source_id)
                if key in self._sources:
                    raise ValueError(f"duplicate scheduled source {key!r}")
                self._sources[key] = source
                self._specs[key] = ScheduledSource(
                    region.region_code, spec.source_id, spec.interval_seconds
                )
                self._next_due[key] = now

    def enabled_sources(self) -> tuple[ScheduledSource, ...]:
        return tuple(
            ScheduledSource(region.region_code, spec.source_id, spec.interval_seconds)
            for region in self.regions
            for spec in region.sources
        )

    def last_results(self) -> dict[tuple[str, str], PollResult]:
        with self._lock:
            return dict(self._last_results)

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._prepare(self.clock())
            self._stop.clear()
            self._thread = Thread(
                target=self._run,
                name="alertsrv-regional-poller",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not current_thread():
            thread.join(timeout=timeout)
        with self._lock:
            self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            now = self.clock()
            due = [key for key, deadline in self._next_due.items() if deadline <= now]
            if due:
                for key in due:
                    if self._stop.is_set():
                        break
                    result = self.poller.poll(self._sources[key])
                    with self._lock:
                        self._last_results[key] = result
                        interval = self._specs[key].interval_seconds
                        self._next_due[key] = self.clock() + interval
                continue
            deadlines = tuple(self._next_due.values())
            delay = max(0.01, min(deadlines) - now) if deadlines else 60.0
            self._stop.wait(delay)

