from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from .base import Finding, Observation


@dataclass
class RuleModule:
    key: str
    title: str
    threshold: float = 0.65
    enabled: bool = True
    model_status: str = "Heuristic available; camera geometry required"
    state: dict[str, Any] = field(default_factory=dict)

    def process(self, observation: Observation) -> list[Finding]:
        if not self.enabled:
            return []
        return []


class VehicleCountingModule(RuleModule):
    def __init__(self):
        super().__init__("vehicle_counting", "Vehicle counting & classification", 0.5)
        self.state["counted"] = set()

    def process(self, observation: Observation) -> list[Finding]:
        # Crossing totals are stored as analytics rather than incidents.
        return []


class CongestionModule(RuleModule):
    def __init__(self, threshold: float = 0.65):
        super().__init__("congestion", "Congestion & queue detection", threshold)

    @staticmethod
    def score(vehicle_count: int, stationary_count: int, region_capacity: int) -> tuple[float, str]:
        if region_capacity <= 0:
            return 0.0, "Unknown"
        density = min(vehicle_count / region_capacity, 1.0)
        stationary_ratio = stationary_count / max(vehicle_count, 1)
        score = round(0.6 * density + 0.4 * stationary_ratio, 3)
        label = "Free flowing"
        if score >= 0.85:
            label = "Gridlocked"
        elif score >= 0.65:
            label = "Heavy"
        elif score >= 0.4:
            label = "Moderate"
        elif score >= 0.2:
            label = "Light"
        return score, label


def build_modules(settings: dict[str, Any] | None = None) -> dict[str, RuleModule]:
    values = settings or {}
    definitions = [
        ("collision", "Possible collision", "Heuristic available; configured road region recommended"),
        ("speed", "Speeding & abnormal speed", "Requires measured-distance or perspective calibration"),
        ("parking", "Illegal parking & duration", "Requires parking/no-parking zones"),
        ("wrong_way", "Wrong-way & illegal U-turn", "Requires lane polygons and direction vectors"),
        ("red_light", "Red-light & stop-line", "Requires signal region, stop line, and reliable signal state"),
        ("lane", "Lane violation & dangerous overtaking", "Requires configured lane geometry"),
        ("intrusion", "Pedestrian, cyclist & animal intrusion", "General detector support varies by class"),
        ("hazard", "Road hazards", "Limited: stalled vehicles only; custom model required for debris/fire/flood/potholes"),
    ]
    modules: dict[str, RuleModule] = {
        "vehicle_counting": VehicleCountingModule(),
        "congestion": CongestionModule(),
    }
    for key, title, status in definitions:
        modules[key] = RuleModule(
            key,
            title,
            float(values.get(key, {}).get("threshold", 0.65)),
            bool(values.get(key, {}).get("enabled", True)),
            status,
        )
    return modules

