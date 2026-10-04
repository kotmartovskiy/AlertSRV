# AlertSRV roadmap

## Phase 1 — core — done

- NormalizedEvent
- Alert model
- evidence history
- source health
- deduplication
- correlation
- state transitions
- deterministic tests

## Phase 2 — service boundary — done

- AlertService facade
- deterministic test adapter
- adapter/service integration tests

## Phase 3 — persistence and API — mostly done

Completed:

1. Stable JSON representation for alerts, including evidence and transition history.
2. Persistence interface and SQLite implementation.
3. Restart recovery for alerts, evidence, deduplication index and source health.
4. Persistence tests covering restart, duplicate events and expiration.
5. Minimal HTTP API using only the Python standard library.
6. API tests for health, listing, detail and 404 behavior.
7. HTTP event ingestion through `POST /api/v1/events`.
8. API tests for event creation, idempotent duplicate ingestion and invalid payloads.
9. Documentation updated to reflect the implemented architecture and API.

Remaining in this phase:

10. Define source lifecycle and freshness semantics.
11. Add tests for stale events, future events, conflicting sources, source recovery and repeated resolution.
12. Harden persistence transaction boundaries and define retention/cleanup policy.
13. Add a stable API contract document once the semantics stop changing.

## Phase 4 — first real source

Only after lifecycle/freshness semantics are stable:

1. Select one real source.
2. Implement a dedicated source adapter.
3. Keep raw-source parsing isolated from the core.
4. Map source observations into NormalizedEvent.
5. Define source-specific reliability and freshness policy.
6. Add fixture-based tests for real source responses.
7. Test source failure, malformed data, empty data and schema changes.

## Phase 5 — aggregation policy

After real-source behavior is understood:

- source reliability model;
- evidence weighting;
- confidence aggregation;
- contradictory-source handling;
- temporal/geographic correlation;
- supersession;
- alert expiration policy;
- event/alert retention.

## Phase 6 — outputs

Only after the aggregation core is stable:

- LAN Discovery API integration;
- local UI;
- notification adapters;
- optional Telegram/push/etc.;
- notification deduplication and delivery state.

## Important architectural rules

### Source failure is not alert resolution

A source becoming unavailable must not silently transition an alert to RESOLVED.

### Severity and confidence are independent

A critical event with low confidence and a warning with high confidence are different situations and must remain distinguishable.

### Source is not alert

Multiple source observations can contribute evidence to one logical alert.

### Core remains deterministic

External I/O belongs in adapters. Aggregation rules should be testable without network access.

### Do not add real sources too early

The first real adapter should validate an already-defined lifecycle rather than define the lifecycle accidentally.

## Open design questions

### Correlation

How should geographic, temporal and textual similarity contribute to correlation without causing unrelated alerts to merge?

### Confidence

How should source reliability and evidence quality affect confidence without pretending that the result is a calibrated probability?

### Severity

How should contradictory severity reports be resolved when a weak source reports CRITICAL and a highly reliable source reports INFO?

### Freshness

When does an observation become stale? Does staleness affect evidence, source health, alert state, or all three?

### Persistence

The current SQLite store is sufficient for the vertical slice but needs transactional ingest semantics and retention policy before production use.

### Source health

What exact state transitions and timestamps define HEALTHY, DEGRADED and UNAVAILABLE?

## Current non-goals

Do not add:

- notification channels;
- Telegram/push;
- arbitrary website scraping;
- complex UI;
- automatic semantic correlation;

until the event lifecycle and persistence semantics are sufficiently specified and tested.
