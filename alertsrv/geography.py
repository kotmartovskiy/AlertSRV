"""Typed affected-area hierarchy for AlertSRV.

The hierarchy is intentionally conservative: equal-level identity is compatible;
parent/child containment is not treated as correlation by itself.
"""

from dataclasses import dataclass
from enum import Enum


class GeographyLevel(str, Enum):
    FEDERAL = "federal"
    REGION = "region"
    MUNICIPALITY = "municipality"
    SETTLEMENT = "settlement"
    LOCAL_AREA = "local_area"


@dataclass(frozen=True)
class AffectedArea:
    level: GeographyLevel
    name: str | None = None
    code: str | None = None
    parent_code: str | None = None
    parent_name: str | None = None
    cadastral_number: str | None = None

    def __post_init__(self) -> None:
        if self.level is GeographyLevel.FEDERAL:
            if any((self.code, self.parent_code, self.parent_name, self.cadastral_number)):
                raise ValueError("federal area cannot carry subordinate identity")
            if not self.name:
                raise ValueError("federal area requires a name")
            return

        if not (self.name or self.code or self.cadastral_number):
            raise ValueError(f"{self.level.value} area requires an identity")

        if self.level is GeographyLevel.SETTLEMENT and not (self.parent_code or self.parent_name):
            raise ValueError("settlement requires municipality parent identity")

        if self.level is GeographyLevel.LOCAL_AREA and not (self.parent_code or self.parent_name or self.cadastral_number):
            raise ValueError("local_area requires parent identity or cadastral identity")

    @property
    def rank(self) -> int:
        return list(GeographyLevel).index(self.level)

    def identity(self) -> tuple[str, ...]:
        if self.cadastral_number:
            return (self.level.value, self.cadastral_number.strip().casefold())
        if self.code:
            return (self.level.value, self.code.strip().casefold())
        return (self.level.value, (self.name or "").strip().casefold())


def area_from_dict(value: dict) -> AffectedArea:
    level = value.get("level")
    if isinstance(level, GeographyLevel):
        parsed_level = level
    else:
        raw_level = str(level)
        # Backward-compatible alias used by the first veterinary adapter.
        parsed_level = GeographyLevel.LOCAL_AREA if raw_level == "farm" else GeographyLevel(raw_level)
    parent_name = value.get("parent_name") or value.get("municipality") or value.get("district")
    return AffectedArea(
        level=parsed_level,
        name=value.get("name"),
        code=value.get("code"),
        parent_code=value.get("parent_code"),
        parent_name=parent_name,
        cadastral_number=value.get("cadastral_number"),
    )


def area_to_dict(area: AffectedArea) -> dict:
    result = {"level": area.level.value}
    for key in ("name", "code", "parent_code", "parent_name", "cadastral_number"):
        value = getattr(area, key)
        if value is not None:
            result[key] = value
    return result


def areas_compatible(left: AffectedArea, right: AffectedArea) -> bool:
    """Return True only for the same geographic level and identity."""
    return left.level is right.level and left.identity() == right.identity()
