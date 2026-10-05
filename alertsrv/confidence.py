from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import Evidence
from .source_authority import SourceAuthority, source_authority


@dataclass(frozen=True, slots=True)
class ConfidencePolicy:
    """Interpretable confidence aggregation, not a calibrated probability model."""

    official_primary_reliability: float = 0.98
    official_corroborating_reliability: float = 0.85
    unofficial_corroborating_reliability: float = 0.35
    unknown_reliability: float = 0.10
    corroboration_weight: float = 0.35

    def __post_init__(self) -> None:
        values = (
            self.official_primary_reliability,
            self.official_corroborating_reliability,
            self.unofficial_corroborating_reliability,
            self.unknown_reliability,
            self.corroboration_weight,
        )
        if any(not 0.0 <= value <= 1.0 for value in values):
            raise ValueError("confidence policy values must be between 0.0 and 1.0")


def source_reliability(source_kind: str | None, policy: ConfidencePolicy | None = None) -> float:
    policy = policy or ConfidencePolicy()
    authority = source_authority(source_kind)
    return {
        SourceAuthority.OFFICIAL_PRIMARY: policy.official_primary_reliability,
        SourceAuthority.OFFICIAL_CORROBORATING: policy.official_corroborating_reliability,
        SourceAuthority.UNOFFICIAL_CORROBORATING: policy.unofficial_corroborating_reliability,
        SourceAuthority.UNKNOWN: policy.unknown_reliability,
    }[authority.authority]


def aggregate_confidence(
    evidence: Iterable[Evidence],
    *,
    policy: ConfidencePolicy | None = None,
) -> float:
    """Combine independent current observations conservatively.

    Only the newest non-resolution observation from each publisher group
    contributes. Additional independent publishers raise confidence with
    diminishing returns; reposts or mirrors from one publisher do not. The
    result is intentionally a bounded evidence score rather than a statistical
    probability.
    """
    policy = policy or ConfidencePolicy()
    # A publisher group represents one underlying publisher. Different
    # adapters (for example a site and a mirror/channel) must not count as
    # independent confirmation when they carry the same publisher_id.
    latest: dict[str, Evidence] = {}
    for item in evidence:
        if item.payload.get("resolved") is True:
            continue
        publisher_id = item.payload.get("publisher_id") or item.source_id
        previous = latest.get(publisher_id)
        if previous is None or item.received_at >= previous.received_at:
            latest[publisher_id] = item

    if not latest:
        return 0.0

    scores: list[float] = []
    for item in latest.values():
        source_kind = item.payload.get("source_kind")
        # Legacy events without source metadata retain their parser confidence.
        # Explicitly unknown source kinds remain strongly discounted.
        reliability = 1.0 if not source_kind else source_reliability(source_kind, policy)
        scores.append(max(0.0, min(1.0, item.confidence * reliability)))

    scores.sort(reverse=True)
    confidence = scores[0]
    for score in scores[1:]:
        confidence += (1.0 - confidence) * score * policy.corroboration_weight
    return max(0.0, min(1.0, confidence))
