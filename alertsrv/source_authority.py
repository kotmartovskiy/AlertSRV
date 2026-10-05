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
    resolution_categories: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("authority score must be between 0.0 and 1.0")

    def can_resolve(self, category: str | None) -> bool:
        if self.authority != SourceAuthority.OFFICIAL_PRIMARY:
            return False
        if self.resolution_categories is None:
            return True
        return category in self.resolution_categories


_POLICIES = {
    SourceAuthority.OFFICIAL_PRIMARY: SourceAuthorityPolicy(SourceAuthority.OFFICIAL_PRIMARY, 1.0),
    SourceAuthority.OFFICIAL_CORROBORATING: SourceAuthorityPolicy(SourceAuthority.OFFICIAL_CORROBORATING, 0.85),
    SourceAuthority.UNOFFICIAL_CORROBORATING: SourceAuthorityPolicy(SourceAuthority.UNOFFICIAL_CORROBORATING, 0.35),
    SourceAuthority.UNKNOWN: SourceAuthorityPolicy(SourceAuthority.UNKNOWN, 0.0),
}

_SOURCE_KIND_POLICIES = {
    "official_regional_operational_hq": SourceAuthority.OFFICIAL_PRIMARY,
    "official_rosgidromet_hydrology": SourceAuthority.OFFICIAL_PRIMARY,
    "official_rosgidromet_emergency": SourceAuthority.OFFICIAL_PRIMARY,
    "veterinary_service_npa": SourceAuthority.OFFICIAL_PRIMARY,
    "official_mchs": SourceAuthority.OFFICIAL_PRIMARY,
    "official_regional_government": SourceAuthority.OFFICIAL_PRIMARY,
    "official_civil_defense": SourceAuthority.OFFICIAL_CORROBORATING,
}


_SOURCE_KIND_RESOLUTION_CATEGORIES = {
    "official_mchs": frozenset({"weather", "emergency_mode", "quarantine", "public_safety"}),
}

def source_authority(source_kind: str | None) -> SourceAuthorityPolicy:
    source_kind = source_kind or ""
    authority = _SOURCE_KIND_POLICIES.get(source_kind, SourceAuthority.UNKNOWN)
    policy = _POLICIES[authority]
    categories = _SOURCE_KIND_RESOLUTION_CATEGORIES.get(source_kind)
    if categories is None:
        return policy
    return SourceAuthorityPolicy(policy.authority, policy.score, categories)
