# AlertSRV

AlertSRV is a standalone, local-first alert aggregation service intended to become the alert subsystem for LAN Discovery.

## Design goals

- Separate external **sources** from logical **alerts**.
- Normalize heterogeneous source events into one internal model.
- Deduplicate repeated observations from the same source.
- Correlate observations from different sources into one logical alert.
- Keep **severity** and **confidence** independent.
- Treat source failure or stale data as source-health information, not as evidence that an alert has ended.
- Keep the core dependency-free and portable to small Linux/ARM appliances.
- Make state transitions deterministic and testable.

## Current scope

This first vertical slice contains normalized event and alert models, deterministic deduplication/correlation keys, an in-memory alert engine, explicit resolve/expire operations, evidence history, source health tracking, and standard-library tests.

HTTP API, persistent storage, real source adapters and notification outputs are intentionally not included yet. They should be added after the core state model is proven.

## State model

`NEW -> ACTIVE -> RESOLVED`
`ACTIVE -> EXPIRED`

A newly accepted event is activated immediately, while the transition history records the `NEW -> ACTIVE` lifecycle.

Source outage does **not** resolve an alert.

## Development

Requires Python 3.11+.

```bash
python -m unittest discover -s tests -v
```
