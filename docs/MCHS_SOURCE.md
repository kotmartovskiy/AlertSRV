## First real source: regional MChS emergency warnings

AlertSRV now has an official-source adapter for the regional MChS emergency-warning RSS feed. The Ivanovo regional feed is the first production-oriented source because it is official, structured RSS, and contains explicit warning publications rather than requiring arbitrary scraping.

The official MChS portal lists regional Main Directorates for the federal districts and subjects of the Russian Federation. citeturn2search0

For Ivanovo, the regional MChS site exposes an RSS feed specifically for "Штормовые и экстренные предупреждения". The feed contains publication date, stable article URL/ID and full text. The site currently publishes warnings such as wind-related emergency warnings with explicit validity periods. citeturn0search0turn0search8

### Adapter policy

- Only the official warning RSS feed is ingested.
- Raw source parsing stays in `alertsrv/adapters/mchs_rss.py`.
- Source observations become `NormalizedEvent`.
- The adapter does not resolve alerts merely because a newer RSS snapshot no longer contains an item.
- The article URL and raw text are preserved as evidence payload.
- Live network tests are opt-in; the normal test suite remains deterministic and offline.

### Expansion path

The next source layer should become a regional MChS source registry. It should discover/cache the official regional GU domains from the MChS territorial-org directory, then probe the standardized warning RSS path. A failed regional feed must produce source-health degradation, not silently disappear from the alert set.

This gives a practical route from one region to broad Russian coverage without duplicating one adapter per region.
