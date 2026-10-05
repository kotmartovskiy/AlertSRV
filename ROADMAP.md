# AlertSRV roadmap

## Current milestone: reliable multi-source warning service

Completed:

- deterministic core lifecycle and SQLite persistence;
- strict normalized-event HTTP contract;
- official Ivanovo MChS warning adapter;
- official regional MChS catalog discovery;
- national MChS polling mode;
- general operational RSS fallback;
- warning validity-date expiration extraction;
- source-health reporting and durable source-health state;
- generic Source Poller lifecycle:
  - successful poll with zero events => HEALTHY;
  - transport/fetch failure => UNAVAILABLE;
  - successful fetch with invalid/uningestable data => DEGRADED;
  - source recovery => HEALTHY;
  - source failure never resolves an alert;
- runnable local runtime and Linux/systemd deployment unit;
- official Rosgidromet national emergency-information adapter;
- regional scope and hazard classification;
- conservative cross-source regional correlation;
- region filtering in the HTTP API;
- public-safety taxonomy for air threats, emergency regimes and quarantine;
- dedicated Ivanovo operational-headquarters adapter for drone/missile danger and explicit all-clear events;
- regional-government source catalog;
- Ivanovo veterinary/quarantine registry adapter with affected-area extraction;
- structured Rosgidromet hydrology adapter with current-bulletin discovery and explicit forecast expiry where available;
- typed event lifecycle semantics with validation for safety-critical resolution and supersession metadata;
- conservative contradiction semantics: a clear from one contributing source cannot resolve an aggregate while another contributing source remains uncleared;
- explicit source-event supersession references with active replacement validation;
- typed lifecycle metadata takes precedence over legacy payload metadata;
- poll-batch validation prevents adapter source-identity/freshness errors from partially mutating alert state;
- explicit source-authority mapping is attached by the current MChS, Rosgidromet emergency, hydrology, operational-headquarters and veterinary adapters;
- structured affected-area hierarchy is implemented and used conservatively for correlation;
- notification delivery state and an adapter contract/dispatcher are implemented; delivery failure is isolated from alert lifecycle;
- local JSONL notification adapter is implemented as the first deterministic transport;
- local web UI is implemented for active warnings with region and municipality filters.

Current verified state:

- 177 automated tests pass;
- regional modules are introduced as lazy, independently selectable source bundles; Ivanovo (`37`) is the first module;
- deterministic confidence/reliability aggregation combines parser confidence with source reliability and independent corroboration without double-counting same-source reposts;
- a single low-overhead scheduler polls only enabled regional modules using each source's declared interval and isolates source failures;
- official Ivanovo air-threat source is parsed for warning and all-clear messages;
- official veterinary/quarantine publications preserve municipality/settlement/farm details when present;
- Rosgidromet hydrology discovery selects the newest non-future bulletin and rejects stale bulletins;
- the latest verified hydrology fetch produced 39 events, including 5 with explicit expiry;
- source outage and source recovery are independent from alert resolution;
- tests use temporary/local state and do not modify user data.

## Public safety scope

AlertSRV is intended to expose more than meteorological warnings:

1. weather and hydrology;
2. drone danger;
3. missile danger;
4. civil-defense/public-warning signals;
5. high-readiness and emergency-situation regimes;
6. extraordinary/emergency legal regimes where an authoritative source explicitly reports them;
7. quarantine:
   - human/public health;
   - animal/veterinary;
   - plant/phytosanitary;
8. epidemiological situations;
9. evacuation and movement restrictions;
10. major infrastructure disruptions.

The semantic taxonomy is documented in docs/PUBLIC_SAFETY_TAXONOMY.md.

## Next work

1. Add operational retention policy automation and scheduled backup rotation; backup/repair helpers and schema migration versioning are implemented.
2. Add broader national source coverage only after each source family has deterministic tests.
3. Add source-specific freshness/degradation metadata where an adapter can distinguish:
   successful empty result, stale upstream data, parser degradation, and transport failure.
4. Add concrete external notification adapters only with deterministic tests and isolated delivery failures.

## Safety-critical source policy

Air-threat alerts must preserve original wording, publication time, source URL/channel, geographic scope, and explicit cancellation/all-clear. Source silence never resolves an air-threat alert.

Unofficial reports may be useful as corroborating evidence in the future, but cannot automatically become high-confidence alerts.

The national service must distinguish raw observations from logical threats: one event can have multiple independent pieces of evidence, and one source can report many observations about the same underlying threat.

Source lifecycle is separate from alert lifecycle. A source being unavailable, degraded, or recovered is operational evidence about the source, not evidence that an underlying threat ended.

### Lifecycle authority policy

Resolution authority is category-specific rather than inferred from parser confidence:

- `air_threat`: the regional operational headquarters is lifecycle-authoritative; MChS and civil-defense feeds are corroborating evidence unless a future source-specific policy explicitly promotes them.
- `weather`: official MChS/Rosgidromet sources may resolve according to their source policy.
- `emergency_mode` and `quarantine`: resolution must come from a source explicitly authorized for that category.
- unofficial/corroborating sources may strengthen or contradict an alert, but cannot independently clear a safety-critical alert.
- when several lifecycle-authoritative sources exist for the same logical alert, all current authoritative source states must clear before automatic resolution.
- stale, missing, unavailable, or recovered sources do not count as a clear.

The implementation represents this through source-authority policy plus category-scoped resolution permissions; the policy is deliberately testable and can later be expanded to subtype/geography-specific rules.
