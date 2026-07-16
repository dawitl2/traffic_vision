from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import median

import numpy as np

from .geometry import Point2D, transform_point


def estimate_segment_speeds(
    points: Sequence[Point2D], timestamps: Sequence[float], matrix: np.ndarray | None = None
) -> list[float]:
    """Return robust segment speeds in km/h; coordinates must be metres or mapped to metres."""
    if len(points) != len(timestamps) or len(points) < 2:
        return []
    world = [transform_point(point, matrix) for point in points] if matrix is not None else list(points)
    speeds: list[float] = []
    for previous, current, start, end in zip(world, world[1:], timestamps, timestamps[1:]):
        elapsed = end - start
        if elapsed <= 0:
            continue
        speed = math.dist(previous, current) / elapsed * 3.6
        if 0 <= speed <= 300:
            speeds.append(speed)
    return speeds


def robust_speed_kph(speeds: Sequence[float]) -> float | None:
    if not speeds:
        return None
    med = median(speeds)
    deviations = [abs(value - med) for value in speeds]
    mad = median(deviations) or 1.0
    filtered = [value for value in speeds if abs(value - med) <= 3.5 * mad]
    if not filtered:
        return None
    weights = np.linspace(1.0, 2.0, len(filtered))
    return round(float(np.average(filtered, weights=weights)), 1)


def reference_scale(meters: float, pixel_distance: float) -> float:
    if meters <= 0 or pixel_distance <= 0:
        raise ValueError("Reference distance and pixel distance must be positive")
    return meters / pixel_distance
