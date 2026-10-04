## First real source: regional MChS emergency warnings

AlertSRV now has an official-source adapter for the regional MChS emergency-warning RSS feed. The Ivanovo regional feed is the first production-oriented source because it is official, structured RSS, and contains explicit warning publications rather than requiring arbitrary scraping.

The official MChS portal lists regional Main Directorates for the federal districts and subjects of the Russian Federation.

For Ivanovo, the regional MChS site exposes an RSS feed specifically for "Штормовые и экстренные предупреждения". The feed contains publication date, stable article URL/ID and full text. The site currently publishes warnings such as wind-related emergency warnings with explicit validity periods.

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


## National coverage

The regional catalog is built from the federal MChS directory of territorial bodies rather than from a hand-maintained list. The current directory exposes 89 official regional sites, including the Moscow site. The catalog deduplicates regional codes and maps the Moscow host to code 77.

The runtime polls the warning RSS feed for each region. If the dedicated warning RSS endpoint returns HTTP 404, it falls back to the regional general operational RSS and keeps only items whose titles indicate a warning/storm. A region with a reachable feed but no current warning items remains `HEALTHY`; an unreachable source becomes `UNAVAILABLE`.

This is deliberately a source-coverage mechanism, not a claim that every regional feed has identical semantics. Some regional sites publish warnings only through their general operational feed, and some may currently have no warning items.

Historical RSS entries are not treated as indefinitely active alerts: when a warning title contains a validity date/range, the adapter derives an expiration at the end of the stated final date.
