from .base import RegionModule, RegionSourceSpec
from .ivanovo import IVANOVO_REGION
from .scheduler import RegionalScheduler, ScheduledSource

_REGIONS: dict[str, RegionModule] = {
    IVANOVO_REGION.region_code: IVANOVO_REGION,
}


def get_region(region_code: str) -> RegionModule:
    try:
        return _REGIONS[region_code]
    except KeyError:
        raise KeyError(f"no region module configured for {region_code}") from None


def list_regions() -> tuple[RegionModule, ...]:
    return tuple(_REGIONS.values())


__all__ = [
    "RegionModule",
    "RegionSourceSpec",
    "IVANOVO_REGION",
    "get_region",
    "list_regions",
]
