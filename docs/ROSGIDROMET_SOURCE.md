# Rosgidromet source

AlertSRV now consumes the official Rosgidromet emergency-information page:

https://www.meteorf.gov.ru/product/emergency/

The source is intentionally modeled as independent evidence, not as a replacement for regional MChS warnings.

The current adapter parses the published date and text of the emergency-information entries and creates normalized weather.emergency_national events with scope=russia.

The official Rosgidromet product catalog also exposes dangerous/adverse hydrometeorological forecasts, weather products, environmental monitoring, radiation information and other products. Those are separate source families and should be added as separate adapters rather than mixed into this parser.

The current national emergency page is useful as corroborating meteorological evidence, but it does not by itself provide a reliable region code for every message. Therefore AlertSRV must not infer a regional alert from this source solely from textual similarity.

## Live verification

A live poll on the Lenovo test host successfully fetched 10 current Rosgidromet emergency entries. A combined national MChS + Rosgidromet run produced 742 normalized observations before lifecycle filtering.

The API was bound to 127.0.0.1 during testing and the temporary database was removed afterward.
