from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class IncidentCandidate:
    category: str
    track_ids: tuple[int, ...]
    peak_seconds: float
    confidence: float


def suppress_duplicates(
    candidates: Iterable[IncidentCandidate], window_seconds: float = 8.0
) -> list[IncidentCandidate]:
    accepted: list[IncidentCandidate] = []
    for candidate in sorted(candidates, key=lambda value: value.peak_seconds):
        duplicate_index = next((
            index for index, existing in enumerate(accepted)
            if existing.category == candidate.category
            and set(existing.track_ids) == set(candidate.track_ids)
            and abs(existing.peak_seconds - candidate.peak_seconds) <= window_seconds
        ), None)
        if duplicate_index is None:
            accepted.append(candidate)
        elif candidate.confidence > accepted[duplicate_index].confidence:
            accepted[duplicate_index] = candidate
    return accepted

