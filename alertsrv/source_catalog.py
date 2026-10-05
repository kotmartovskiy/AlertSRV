from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class RegionalGovernmentSource:
    """Authoritative regional-government source metadata.

    The catalog is metadata-only. Adapters remain responsible for parsing
    pages and applying alert policy.
    """

    region_code: str
    region_name: str
    base_url: str
    operational_sitemap_url: str
    source_id: str

    def __post_init__(self) -> None:
        if not self.region_code or not self.region_name or not self.source_id:
            raise ValueError("region_code, region_name and source_id are required")
        for field_name in ("base_url", "operational_sitemap_url"):
            value = getattr(self, field_name)
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError(f"{field_name} must be an HTTPS URL")


IVANOVO = RegionalGovernmentSource(
    region_code="37",
    region_name="Ивановская область",
    base_url="https://ivanovoobl.ru/",
    operational_sitemap_url="https://ivanovoobl.ru/sitemap.xml",
    source_id="ivanovo-operational-hq",
)


_REGIONAL_GOVERNMENT_SOURCES: dict[str, RegionalGovernmentSource] = {
    IVANOVO.region_code: IVANOVO,
}


def get_regional_government_source(region_code: str) -> RegionalGovernmentSource:
    try:
        return _REGIONAL_GOVERNMENT_SOURCES[region_code]
    except KeyError:
        raise KeyError(f"no regional government source configured for {region_code}") from None


def list_regional_government_sources() -> tuple[RegionalGovernmentSource, ...]:
    return tuple(_REGIONAL_GOVERNMENT_SOURCES.values())
