# AlertSRV roadmap

## Current milestone: real warning service

Completed:

- deterministic core lifecycle and persistence;
- strict normalized-event HTTP contract;
- official Ivanovo MChS warning adapter;
- official regional MChS catalog discovery;
- national MChS polling mode;
- general operational RSS fallback when a dedicated warning RSS endpoint is unavailable;
- warning validity-date expiration extraction;
- source-health reporting;
- runnable local runtime and Linux/systemd deployment unit.

Current verified state on the Lenovo test host:

- 37 automated tests pass;
- official MChS catalog resolves 89 regional sites including Moscow;
- a full national poll was executed with 8 concurrent workers;
- 727 RSS observations were ingested during the full poll test;
- historical observations were transitioned to EXPIRED according to parsed validity dates;
- the API remained localhost-only during runtime tests;
- no project data outside temporary test databases was modified.

## Next work

1. Improve regional source semantics and coverage for the regions whose feeds expose warnings only through non-standard mechanisms.
2. Add independent weather/meteorological sources so MChS warnings are corroborated rather than treated as the only weather evidence.
3. Add regional civil-defense / public warning sources where officially available.
4. Implement cross-source geographic/temporal correlation and contradiction policy.
5. Add notification delivery state and a notification adapter (Telegram/local webhook first).
6. Add a small local UI for active warnings and source health.
7. Add operational retention, backup/repair and schema migration procedures.

The national MChS adapter is deliberately not the final aggregation layer: it is one evidence source. The target service should combine independent sources before assigning high confidence to a logical alert.
