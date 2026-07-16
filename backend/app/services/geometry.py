from __future__ import annotations

import math
from collections.abc import Sequence

import cv2
import numpy as np
from shapely.geometry import LineString, Point, Polygon


Point2D = tuple[float, float]


def point_in_polygon(point: Point2D, polygon: Sequence[Point2D]) -> bool:
    if len(polygon) < 3:
        return False
    return Polygon(polygon).covers(Point(point))


def segments_cross(a: Point2D, b: Point2D, c: Point2D, d: Point2D) -> bool:
    movement = LineString([a, b])
    boundary = LineString([c, d])
    return movement.crosses(boundary) or movement.touches(boundary)


def movement_direction(points: Sequence[Point2D]) -> Point2D:
    if len(points) < 2:
        return (0.0, 0.0)
    dx = points[-1][0] - points[0][0]
    dy = points[-1][1] - points[0][1]
    length = math.hypot(dx, dy)
    return (dx / length, dy / length) if length else (0.0, 0.0)


def direction_similarity(actual: Point2D, allowed: Point2D) -> float:
    a_norm = math.hypot(*actual)
    b_norm = math.hypot(*allowed)
    if not a_norm or not b_norm:
        return 0.0
    return (actual[0] * allowed[0] + actual[1] * allowed[1]) / (a_norm * b_norm)


def dwell_time(timestamps: Sequence[float], stationary_flags: Sequence[bool]) -> float:
    if len(timestamps) < 2 or len(timestamps) != len(stationary_flags):
        return 0.0
    longest = current_start = 0.0
    start: float | None = None
    for timestamp, stationary in zip(timestamps, stationary_flags, strict=True):
        if stationary and start is None:
            start = timestamp
        elif not stationary and start is not None:
            longest = max(longest, timestamp - start)
            start = None
    if start is not None:
        longest = max(longest, timestamps[-1] - start)
    return max(0.0, longest)


def homography(image_points: Sequence[Point2D], world_points: Sequence[Point2D]) -> np.ndarray:
    if len(image_points) != 4 or len(world_points) != 4:
        raise ValueError("Perspective calibration requires exactly four image and world points")
    matrix = cv2.getPerspectiveTransform(
        np.asarray(image_points, dtype=np.float32), np.asarray(world_points, dtype=np.float32)
    )
    if not np.isfinite(matrix).all() or abs(np.linalg.det(matrix)) < 1e-10:
        raise ValueError("Calibration points are degenerate")
    return matrix


def transform_point(point: Point2D, matrix: np.ndarray) -> Point2D:
    value = cv2.perspectiveTransform(np.asarray([[point]], dtype=np.float32), matrix)[0, 0]
    return float(value[0]), float(value[1])

