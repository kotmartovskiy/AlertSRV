# Public safety and administrative alert taxonomy

AlertSRV must treat a public warning as an observation of a condition, not as a source-specific alert.

## Categories
- weather — dangerous/adverse meteorological phenomena.
- hydrology — flood, high water, dangerous water levels and related phenomena.
- air_threat — drone activity/warning and missile danger.
- emergency_mode — high-readiness, emergency situation, emergency regime.
- quarantine — public-health, animal or plant quarantine.
- epidemiology — infectious-disease or poisoning situation without a formal quarantine event.
- public_safety — evacuation, movement restrictions and similar measures.
- infrastructure — major utility/infrastructure disruption.
- other — unclassified observation.

## Air threat
The service must distinguish at least:
- missile_warning
- drone_warning
- drone_activity

A regional government's official warning that says 'Угроза атаки БПЛА' is materially different from a generic report that a drone was observed somewhere. They must not receive the same semantic subtype.

## Emergency regimes
Do not collapse these into one generic emergency flag:
- high_readiness — режим повышенной готовности;
- emergency_situation — режим чрезвычайной ситуации;
- emergency_regime — чрезвычайное положение.

The first two are explicitly part of the Russian emergency-management regime described by MChS. The federal/local authority and territorial scope must remain attached to the event.

## Quarantine
Quarantine requires both scope and object:
- human/public health;
- animal/veterinary;
- plant/phytosanitary.

A quarantine in one settlement must never be displayed as a region-wide quarantine merely because its source belongs to a regional authority.

## Geographic scope
Future normalized events should carry a structured affected-area object where the source provides it:
federal -> region -> municipality -> settlement -> local_area

The hierarchy is additive: a municipality-level event is not automatically a region-wide event.

## Correlation rules
Cross-source correlation should require compatible:
1. category/subtype;
2. geographic scope;
3. affected area;
4. time interval;
5. source independence.

National-scope evidence cannot silently create a region-specific air-threat or quarantine alert.

## Source strategy
For weather and hydrology, official MChS/Rosgidromet sources are primary candidates.

For missile/drone danger and administrative regimes, the preferred source order is:
1. official regional/federal government or emergency authority;
2. official MChS regional publication;
3. official civil-defense/public-warning channel;
4. corroborating independent official source.

Unofficial social-media reports should be retained, if ever supported, as low-confidence evidence and never promoted automatically to a high-confidence alert.

## Safety requirement
Air-threat events are safety-critical. The adapter must preserve the original wording, publication timestamp, source URL/channel, scope, and explicit all-clear/cancellation when present. Silence from the source is never an implicit cancellation.