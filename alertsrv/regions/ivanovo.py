from __future__ import annotations

from ..adapters.ivanovo_operational_hq import IvanovoOperationalHQAdapter
from ..adapters.ivanovo_operational_telegram import IvanovoOperationalTelegramAdapter
from ..adapters.ivanovo_veterinary import IvanovoVeterinaryRegistryAdapter
from ..adapters.mchs_rss import MchsRssAdapter
from .base import RegionModule, RegionSourceSpec

IVANOVO_REGION = RegionModule(
    region_code="37",
    region_name="Ивановская область",
    timezone="Europe/Moscow",
    sources=(
        RegionSourceSpec(
            source_id="ivanovo-operational-hq",
            interval_seconds=60,
            categories=frozenset({"air_threat"}),
            factory=IvanovoOperationalHQAdapter,
        ),
        RegionSourceSpec(
            source_id="ivanovo-operational-telegram",
            interval_seconds=120,
            categories=frozenset({"air_threat"}),
            factory=IvanovoOperationalTelegramAdapter,
        ),
        RegionSourceSpec(
            source_id="mchs-ivanovo",
            interval_seconds=300,
            categories=frozenset({"weather", "public_safety"}),
            factory=MchsRssAdapter,
        ),
        RegionSourceSpec(
            source_id="ivanovo-veterinary-registry",
            interval_seconds=900,
            categories=frozenset({"quarantine"}),
            factory=IvanovoVeterinaryRegistryAdapter,
        ),
    ),
)
