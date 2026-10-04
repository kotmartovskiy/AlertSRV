# AlertSRV

AlertSRV is a standalone, local-first alert aggregation service intended to become the alert subsystem for LAN Discovery.

The central design principle is:

> **A source is not an alert.**

Several independent sources may report the same real-world condition. AlertSRV turns those observations into normalized events, deduplicates them, correlates related observations, and maintains the lifecycle of a logical alert.

## Architecture

```
External source
      |
      v
Source adapter
      |
      v
NormalizedEvent
      |
      v
AlertService
      |
      v
AlertEngine
   |       |
   |       +--> source health
   |
   +--> Alert
          +--> state
          +--> severity
          +--> confidence
          +--> evidence[]
          +--> transition_history[]
          |
          v
       AlertStore
          |
          +--> SQLite
```

The HTTP API is an input/output boundary around the service. It does not contain aggregation policy.

## Current implementation

The current vertical slice includes:

- immutable `NormalizedEvent` model;
- `Alert` model with evidence and transition history;
- deterministic event deduplication;
- correlation by adapter-provided `correlation_key`;
- independent severity and confidence;
- explicit alert resolution and expiration;
- separate source-health state;
- `AlertService` application boundary;
- SQLite persistence behind `AlertStore`;
- restart recovery of alerts, evidence, event deduplication and source health;
- standard-library HTTP API;
- HTTP event ingestion;
- deterministic test adapter;
- automated tests.

The project currently has no external production source adapter and no notification channel.

## Alert lifecycle

Current states:

```
NEW -> ACTIVE -> RESOLVED
             \
              -> EXPIRED

ACTIVE -> CANCELLED / SUPERSEDED
```

A newly accepted event normally creates `NEW` and immediately transitions it to `ACTIVE`. The transition is retained in history.

An explicit resolved event or service operation can resolve an active alert. An expiration rule can move an active alert to `EXPIRED`.

**Source outage does not resolve an alert.**

This distinction is fundamental: inability to obtain new evidence is not evidence that the underlying condition ended.

## Event ingestion

Events can be submitted through:

```
POST /api/v1/events
Content-Type: application/json
```

Example:

```json
{
  "event_id": "weather-001",
  "source_id": "weather-test",
  "event_type": "weather_warning",
  "title": "Heavy rain warning",
  "severity": "WARNING",
  "confidence": 0.9,
  "occurred_at": "2026-10-04T20:00:00+00:00",
  "received_at": "2026-10-04T20:01:00+00:00",
  "correlation_key": "weather:ivanovo:heavy-rain",
  "payload": {}
}
```

The endpoint validates and converts the payload into `NormalizedEvent`, then passes it through the normal service and engine path.

Repeated submission of the same `source_id + event_id` is deduplicated.

The API is currently intended for local integration and binds to `127.0.0.1` by default. It should not be exposed to an untrusted network without an explicit authentication/access-control design.

## HTTP API

Current endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service health check |
| GET | `/api/v1/alerts` | List alerts |
| GET | `/api/v1/alerts/<id>` | Get one alert |
| POST | `/api/v1/events` | Ingest a normalized event |
| POST | `/api/v1/alerts/expire` | Apply expiration rules |

Malformed or invalid event payloads return HTTP `400`. Unknown routes return `404`.

A dedicated API contract document will be added when the endpoint set and semantics stabilize.

## Persistence

SQLite persistence is deliberately simple at this stage.

The store currently persists:

- alert JSON;
- alert correlation/state metadata;
- event-to-alert deduplication mappings;
- source health.

The engine can also run without a store for deterministic unit tests.

Persistence is not yet considered production-hardened. In particular, multi-step ingest persistence and retention/cleanup policies still need explicit transactional and lifecycle design.

## Design policies

### Correlation

The adapter currently supplies `correlation_key`.

Automatic geographic, temporal, textual or semantic correlation is intentionally outside the core until its rules can be specified and tested.

### Confidence

The engine currently keeps the maximum observed confidence.

This is a deterministic placeholder, **not a statistically calibrated probability model**. Future aggregation should account for source reliability and evidence quality.

### Severity

The current alert severity is the maximum observed severity.

This is conservative and may later become a policy layer for contradictory, stale or low-confidence observations.

### Freshness

Event timing is now classified by an explicit `FreshnessPolicy`. The policy is configurable because different sources can have different acceptable ages.

The current classifications are:

- `FRESH` — usable by the aggregation engine;
- `STALE` — older than the configured maximum age;
- `FUTURE` — received later than the configured future-skew allowance.

By default no age limits are imposed. When limits are configured, stale and excessively future-dated events are rejected before they can create or modify alerts. This prevents an old observation from resurrecting an alert and prevents clock/source errors from becoming active evidence.

Freshness is deliberately separate from source health and alert state. Source silence still does not resolve an alert, and recovery still requires a new usable observation.

### Source health

Source health is tracked independently from alert state.

A source can be unavailable while an alert remains active. Recovery of a source likewise does not automatically create or resolve an alert without evidence.

## Development

Requires Python 3.11+.

Run the complete test suite:

```bash
python -m pytest -q
```

The project intentionally uses the Python standard library for the service core and persistence/API implementation.

## Project status

The project is still in the architecture-validation stage.

The current goal is not to add many integrations quickly. The goal is to establish a deterministic, testable event-to-alert lifecycle before connecting real external sources.

See [ROADMAP.md](ROADMAP.md) for the current development sequence.
