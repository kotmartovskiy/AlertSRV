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
- runnable local runtime and Linux/systemd deployment unit;
- official Rosgidromet national emergency-information adapter;
- regional scope and hazard classification;
- conservative cross-source regional correlation;
- region filtering in the HTTP API;
- initial public-safety taxonomy for air threats, emergency regimes and quarantine.

Current verified state:

- 46 automated tests pass before the current taxonomy test expansion;
- official MChS catalog resolves 89 regional sites including Moscow;
- national MChS polling and Rosgidromet live fetches were previously verified;
- official Ivanovo sources were verified for drone-danger warnings and all-clear messages;
- official Ivanovo civil-defense material was verified for missile-danger signaling;
- official Ivanovo government/veterinary publications were verified for quarantine and emergency-regime information;
- API remains localhost-only during runtime tests;
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

1. Add a dedicated Ivanovo official operational-headquarters adapter for drone/missile danger and explicit all-clear events.
2. Add a regional-government source catalog so the same adapter pattern can be extended beyond Ivanovo.
3. Add official veterinary/quarantine source adapters and preserve the exact affected municipality/settlement.
4. Add a dedicated Rosgidromet hydrology adapter with structured water-body/observation-point data.
5. Extend geographic representation from region_code to a structured affected_area hierarchy:
   federal -> region -> municipality -> settlement -> local_area.
6. Add contradiction and cancellation semantics for safety-critical warnings.
7. Add notification delivery state and adapters.
8. Add a small local UI showing active warnings by selected region and municipality.
9. Add operational retention, backup/repair and schema migration procedures.
10. Add broader national source coverage only after each source family has deterministic tests.

## Safety-critical source policy

Air-threat alerts must preserve original wording, publication time, source URL/channel, geographic scope, and explicit cancellation/all-clear. Source silence never resolves an air-threat alert.

Unofficial reports may be useful as corroborating evidence in the future, but cannot automatically become high-confidence alerts.

The national service must distinguish raw observations from logical threats: one event can have multiple independent pieces of evidence, and one source can report many observations about the same underlying threat.
