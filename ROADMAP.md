# AlertSRV roadmap

## Phase 1 — core (done)

- NormalizedEvent
- Alert model
- evidence history
- source health
- deduplication
- correlation
- state transitions
- deterministic tests

## Phase 2 — service boundary (done)

- AlertService facade
- deterministic test adapter
- adapter/service integration tests

## Phase 3 — in progress

Completed in this phase:

1. Stable JSON representation for alerts, including evidence and transition history.
2. Persistence interface and SQLite implementation.
3. Restart recovery for alerts, evidence, deduplication index and source health.
4. Persistence tests covering restart, duplicate events and expiration.

Next, before adding real external sources:

5. Add a minimal HTTP API using only the Python standard library.
6. Add an API-level test adapter.
7. Define source lifecycle and freshness semantics.
8. Add tests for stale events, conflicting sources, source recovery and repeated resolution.
9. Only then implement the first real source adapter.

## Important unresolved design questions

### Correlation

The current `correlation_key` is supplied by an adapter. This is intentional: automatic geographic/text correlation is a later subsystem and must not be hidden inside the core.

### Confidence

The current engine retains the maximum observed confidence. This is a temporary deterministic policy, not a statistical confidence model. A future aggregator should be able to use source reliability and evidence weighting.

### Severity

The current alert severity is the maximum observed severity. This is conservative but may need a policy layer for contradictory or stale observations.

### Persistence

SQLite persistence now exists behind an AlertStore interface. The engine can still run in-memory for tests, while a SQLite-backed instance restores alerts, evidence, deduplication mappings and source health after restart.

### Source outage

A source becoming unavailable never resolves an alert. Resolution must come from an explicit source event, an expiration rule, or an operator/system policy.

## Non-goals for the current stage

Do not add notification channels, Telegram, push, scraping of arbitrary websites, or a complex UI before the state model and persistence semantics are stable.
