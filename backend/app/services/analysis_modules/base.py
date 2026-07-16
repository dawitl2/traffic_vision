from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Observation:
    frame_index: int
    timestamp: float
    tracks: list[dict[str, Any]]
    zones: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Finding:
    category: str
    confidence: float
    track_ids: list[int]
    start_seconds: float
    peak_seconds: float
    end_seconds: float
    measurements: dict[str, Any] = field(default_factory=dict)


class AnalysisModule(Protocol):
    key: str
    title: str
    model_status: str

    def process(self, observation: Observation) -> list[Finding]: ...

