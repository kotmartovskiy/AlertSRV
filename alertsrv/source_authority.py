from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SourceAuthority(str, Enum):
    OFFICIAL_PRIMARY = "official_primary"
    OFFICIAL_CORROBORATING = "official_corroborating"
    UNOFFICIAL_CORROBORATING = "unofficial_corroborating"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SourceAuthorityPolicy:
    authority: SourceAuthority
    score: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("authority score must be between 0.0 and 1.0")


_POLICIES = {
    SourceAuthority.OFFICIAL_PRIMARY: SourceAuthorityPolicy(SourceAuthority.OFFICIAL_PRIMARY, 1.0),
    SourceAuthority.OFFICIAL_CORROBORATING: SourceAuthorityPolicy(SourceAuthority.OFFICIAL_CORROBORATING, 0.85),
    SourceAuthority.UNOFFICIAL_CORROBORATING: SourceAuthorityPolicy(SourceAuthority.UNOFFICIAL_CORROBORATING, 0.35),
    SourceAuthority.UNKNOWN: SourceAuthorityPolicy(SourceAuthority.UNKNOWN, 0.0),
}

_SOURCE_KIND_POLICIES = {
    "official_regional_operational_hq": SourceAuthority.OFFICIAL_PRIMARY,
    "official_rosgidromet_hydrology": SourceAuthority.OFFICIAL_PRIMARY,
    "veterinary_service_npa": SourceAuthority.OFFICIAL_PRIMARY,
    "official_mchs": SourceAuthority.OFFICIAL_PRIMARY,
    "official_regional_government": SourceAuthority.OFFICIAL_PRIMARY,
    "official_civil_defense": SourceAuthority.OFFICIAL_CORROBORATING,
}


def source_authority(source_kind: str | None) -> SourceAuthorityPolicy:
    authority = _SOURCE_KIND_POLICIES.get(source_kind or "", SourceAuthority.UNKNOWN)
    return _POLICIES[authority]
