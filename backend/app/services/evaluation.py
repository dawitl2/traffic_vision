from __future__ import annotations

import math
import itertools
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..entities import (
    AnalysisJob, Calibration, CameraConfiguration, Incident, PlateRead, Track, TrackPoint,
)
from .geometry import direction_similarity, movement_direction, point_in_polygon, segments_cross
from .incidents import IncidentCandidate, suppress_duplicates
from .speed import estimate_segment_speeds, reference_scale, robust_speed_kph
from .analysis_modules import CongestionModule


VEHICLES = {"car", "motorcycle", "bus", "truck", "bicycle"}
VULNERABLE = {"person", "bicycle", "dog", "cat", "horse", "sheep", "cow", "bird"}


def _points(db: Session, track_id: str) -> list[TrackPoint]:
    return list(db.scalars(
        select(TrackPoint).where(TrackPoint.track_id == track_id).order_by(TrackPoint.timestamp_seconds)
    ).all())


def _shape_points(shape: dict[str, Any]) -> list[tuple[float, float]]:
    return [(float(point["x"]), float(point["y"])) if isinstance(point, dict) else (float(point[0]), float(point[1])) for point in shape.get("points", [])]


def _inside_ratio(points: list[TrackPoint], polygon: list[tuple[float, float]]) -> float:
    if not points or len(polygon) < 3:
        return 0.0
    return sum(point_in_polygon((point.x, point.y), polygon) for point in points) / len(points)


def _duration_inside(points: list[TrackPoint], polygon: list[tuple[float, float]]) -> float:
    inside = [point.timestamp_seconds for point in points if point_in_polygon((point.x, point.y), polygon)]
    return max(inside) - min(inside) if len(inside) > 1 else 0.0


def _bbox_iou(a: list[float], b: list[float]) -> float:
    left, top = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    if not intersection:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return intersection / max(area_a + area_b - intersection, 1e-9)


def _crosses(points: list[TrackPoint], line: list[tuple[float, float]]) -> bool:
    if len(line) < 2:
        return False
    return any(
        segments_cross((a.x, a.y), (b.x, b.y), line[0], line[1]) for a, b in zip(points, points[1:])
    )


def _number(db: Session) -> str:
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    count = len(db.scalars(select(Incident).where(Incident.incident_number.like(f"TV-{date}-%"))).all()) + 1
    return f"TV-{date}-{count:05d}"


def _plate_for_track(db: Session, track_id: str) -> PlateRead | None:
    return db.scalars(
        select(PlateRead).where(PlateRead.track_id == track_id).order_by(PlateRead.confidence.desc())
    ).first()


def _add(
    db: Session, job: AnalysisJob, track: Track | None, category: str, confidence: float,
    start: float, peak: float, end: float, measurements: dict[str, Any], severity: str = "medium",
) -> Incident:
    plate = _plate_for_track(db, track.id) if track else None
    row = Incident(
        incident_number=_number(db), job_id=job.id, category=category, severity=severity,
        confidence=max(0.0, min(float(confidence), 1.0)),
        track_ids_json=[track.id] if track else [], vehicle_class=track.object_class if track else None,
        plate_text=plate.text if plate else "Unreadable", plate_confidence=plate.confidence if plate else 0.0,
        start_seconds=max(0, start), peak_seconds=max(0, peak), end_seconds=max(peak, end),
        measurements_json=measurements,
    )
    db.add(row); db.flush()
    return row


def evaluate_configured_rules(db: Session, job: AnalysisJob) -> list[Incident]:
    """Evaluate only rules whose camera geometry/calibration is explicitly available."""
    configuration_id = job.config_json.get("configuration_id")
    if not configuration_id:
        return []
    configuration = db.get(CameraConfiguration, configuration_id)
    if configuration is None:
        return []
    config = configuration.config_json or {}
    shapes = config.get("shapes", [])
    tracks = list(db.scalars(select(Track).where(Track.job_id == job.id)).all())
    histories = {track.id: _points(db, track.id) for track in tracks}
    created: list[Incident] = []
    candidates: list[IncidentCandidate] = []

    no_parking = [shape for shape in shapes if str(shape.get("type", "")).lower() in {"no-parking zone", "no_parking"}]
    restricted = [shape for shape in shapes if str(shape.get("type", "")).lower() in {"bus-only lane", "emergency lane", "shoulder"}]
    danger_regions = [shape for shape in shapes if str(shape.get("type", "")).lower() in {"road region", "pedestrian restriction", "hazard region"}]
    road_regions = [shape for shape in shapes if str(shape.get("type", "")).lower() == "road region"]
    hazard_regions = [shape for shape in shapes if str(shape.get("type", "")).lower() == "hazard region"]
    lanes = [shape for shape in shapes if str(shape.get("type", "")).lower() == "lane"]
    counting_lines = [shape for shape in shapes if str(shape.get("type", "")).lower() == "counting line"]
    stop_lines = [shape for shape in shapes if str(shape.get("type", "")).lower() == "stop line"]

    for track in tracks:
        points = histories[track.id]
        if len(points) < 2:
            continue
        times = [point.timestamp_seconds for point in points]
        trajectory = [(point.x, point.y) for point in points]
        for shape in no_parking:
            polygon = _shape_points(shape)
            dwell = _duration_inside(points, polygon)
            grace = float(shape.get("grace_seconds", 30))
            displacement = math.dist(trajectory[0], trajectory[-1])
            if track.object_class in VEHICLES and dwell >= grace and displacement < float(shape.get("stationary_threshold", .03)):
                created.append(_add(db, job, track, "Possible illegal parking", min(.95, .6 + dwell / 600), times[0], times[-1], times[-1], {"dwell_seconds": round(dwell, 1), "grace_seconds": grace, "zone": shape.get("name", "No-parking zone")}))
        for shape in lanes:
            polygon = _shape_points(shape)
            allowed = shape.get("direction")
            if allowed and _inside_ratio(points, polygon) >= .5:
                actual = movement_direction(trajectory)
                similarity = direction_similarity(actual, (float(allowed[0]), float(allowed[1])))
                if similarity < float(shape.get("wrong_way_similarity", -.25)):
                    created.append(_add(db, job, track, "Possible wrong-way movement", min(.95, abs(similarity)), times[0], times[len(times)//2], times[-1], {"direction_similarity": round(similarity, 3), "lane": shape.get("name", "Lane")}))
                if len(trajectory) >= 6:
                    first = movement_direction(trajectory[:len(trajectory)//2])
                    second = movement_direction(trajectory[len(trajectory)//2:])
                    turn_similarity = direction_similarity(first, second)
                    if turn_similarity < -.65 and not shape.get("u_turn_allowed", False):
                        created.append(_add(db, job, track, "Possible illegal U-turn", min(.9, abs(turn_similarity)), times[0], times[len(times)//2], times[-1], {"turn_similarity": round(turn_similarity, 3), "lane": shape.get("name", "Lane")}))
        for shape in restricted:
            if track.object_class != "bus" and _duration_inside(points, _shape_points(shape)) >= float(shape.get("minimum_seconds", 2)):
                created.append(_add(db, job, track, "Possible lane violation", .72, times[0], times[len(times)//2], times[-1], {"restricted_region": shape.get("type"), "rule": "Geometry entry"}))
        if track.object_class in VULNERABLE:
            for shape in danger_regions:
                if _inside_ratio(points, _shape_points(shape)) >= .2:
                    created.append(_add(db, job, track, "Vulnerable road-user intrusion", .7, times[0], times[len(times)//2], times[-1], {"object_class": track.object_class, "region": shape.get("name", shape.get("type"))}))
                    break
        for shape in hazard_regions:
            polygon = _shape_points(shape)
            duration = _duration_inside(points, polygon)
            if track.object_class in VEHICLES and duration >= float(shape.get("stalled_seconds", 20)) and math.dist(trajectory[0], trajectory[-1]) < .025:
                created.append(_add(db, job, track, "Possible stalled vehicle / road hazard", .74, times[0], times[-1], times[-1], {"stationary_seconds": round(duration, 1), "supported_hazard_class": "stalled vehicle"}, "high"))

    # Congestion needs an explicit road region and sustained track density; a single busy frame is insufficient.
    for shape in road_regions:
        polygon = _shape_points(shape)
        capacity = int(shape.get("capacity", 20))
        buckets: dict[int, set[str]] = defaultdict(set)
        stationary: set[str] = set()
        for track in tracks:
            if track.object_class not in VEHICLES:
                continue
            history = [point for point in histories[track.id] if point_in_polygon((point.x, point.y), polygon)]
            for point in history:
                buckets[int(point.timestamp_seconds)].add(track.id)
            if len(history) >= 2 and math.dist((history[0].x, history[0].y), (history[-1].x, history[-1].y)) < .025:
                stationary.add(track.id)
        congested = []
        for second, ids in sorted(buckets.items()):
            score, label = CongestionModule.score(len(ids), len(ids & stationary), capacity)
            if score >= float(shape.get("congestion_threshold", .65)):
                congested.append((second, score, label, len(ids)))
        if congested and congested[-1][0] - congested[0][0] >= float(shape.get("minimum_congestion_seconds", 10)):
            peak = max(congested, key=lambda item: item[1])
            created.append(_add(db, job, None, f"{peak[2]} congestion", peak[1], congested[0][0], peak[0], congested[-1][0], {"vehicle_count": peak[3], "region_capacity": capacity, "queue_duration_seconds": congested[-1][0] - congested[0][0], "classification": peak[2]}))

    # Collision heuristic: strong overlap followed by both tracks becoming nearly stationary inside a road region.
    if road_regions:
        road_polygon = _shape_points(road_regions[0])
        vehicle_tracks = [track for track in tracks if track.object_class in VEHICLES]
        for first, second in itertools.combinations(vehicle_tracks, 2):
            a = {round(point.timestamp_seconds, 1): point for point in histories[first.id]}
            b = {round(point.timestamp_seconds, 1): point for point in histories[second.id]}
            overlaps = [(timestamp, _bbox_iou(a[timestamp].bbox_json, b[timestamp].bbox_json)) for timestamp in a.keys() & b.keys() if point_in_polygon((a[timestamp].x, a[timestamp].y), road_polygon)]
            if not overlaps:
                continue
            timestamp, overlap = max(overlaps, key=lambda item: item[1])
            if overlap < float(road_regions[0].get("collision_iou", .3)):
                continue
            after_a = [point for point in histories[first.id] if point.timestamp_seconds >= timestamp]
            after_b = [point for point in histories[second.id] if point.timestamp_seconds >= timestamp]
            stopped_a = len(after_a) > 2 and math.dist((after_a[0].x, after_a[0].y), (after_a[-1].x, after_a[-1].y)) < .02
            stopped_b = len(after_b) > 2 and math.dist((after_b[0].x, after_b[0].y), (after_b[-1].x, after_b[-1].y)) < .02
            if stopped_a and stopped_b:
                row = _add(db, job, first, "Possible collision", min(.9, .6 + overlap / 2), max(0, timestamp - 2), timestamp, timestamp + 4, {"bounding_box_iou": round(overlap, 3), "both_stationary_after": True}, "critical")
                row.track_ids_json = [first.id, second.id]
                created.append(row)

    calibration = db.scalars(
        select(Calibration).where(Calibration.configuration_id == configuration.id).order_by(Calibration.calibrated_at.desc())
    ).first()
    if calibration and calibration.confidence >= .5:
        reference = calibration.reference_json or {}
        for track in tracks:
            if track.object_class not in VEHICLES:
                continue
            points = histories[track.id]
            if len(points) < 3:
                continue
            region = [(float(x), float(y)) for x, y in calibration.speed_region_json]
            selected = [point for point in points if not region or point_in_polygon((point.x, point.y), region)]
            if len(selected) < 3:
                continue
            values = [(point.x, point.y) for point in selected]
            timestamps = [point.timestamp_seconds for point in selected]
            speed: float | None = None
            segment_speeds: list[float] = []
            if calibration.method == "measured_reference":
                image_points = reference.get("image_points", [])
                distance_m = float(reference.get("distance_m", 0))
                if len(image_points) == 2 and distance_m > 0:
                    ax, ay = image_points[0]; bx, by = image_points[1]
                    pixel_ref = math.dist((ax * configuration.original_width, ay * configuration.original_height), (bx * configuration.original_width, by * configuration.original_height))
                    scale = reference_scale(distance_m, pixel_ref)
                    world = [(x * configuration.original_width * scale, y * configuration.original_height * scale) for x, y in values]
                    segment_speeds = estimate_segment_speeds(world, timestamps)
                    speed = robust_speed_kph(segment_speeds)
            elif calibration.method == "perspective":
                from .geometry import homography
                image = [(float(x) * configuration.original_width, float(y) * configuration.original_height) for x, y in reference.get("image_points", [])]
                world = [(float(x), float(y)) for x, y in reference.get("world_points", [])]
                if len(image) == len(world) == 4:
                    matrix = homography(image, world)
                    pixels = [(x * configuration.original_width, y * configuration.original_height) for x, y in values]
                    segment_speeds = estimate_segment_speeds(pixels, timestamps, matrix)
                    speed = robust_speed_kph(segment_speeds)
            if speed is not None:
                track.best_speed_kph = speed
                if speed > calibration.speed_limit_kph:
                    created.append(_add(db, job, track, "Possible speeding", min(.95, calibration.confidence * .9), timestamps[0], timestamps[len(timestamps)//2], timestamps[-1], {"speed_kph": speed, "speed_limit_kph": calibration.speed_limit_kph, "amount_over_kph": round(speed - calibration.speed_limit_kph, 1), "calibration_method": calibration.method, "calibration_confidence": calibration.confidence}, "high"))
                minimum = config.get("minimum_speed_kph")
                if minimum is not None and speed < float(minimum) and timestamps[-1] - timestamps[0] >= float(config.get("slow_vehicle_seconds", 5)):
                    created.append(_add(db, job, track, "Unusually slow vehicle", min(.9, calibration.confidence * .85), timestamps[0], timestamps[len(timestamps)//2], timestamps[-1], {"speed_kph": speed, "minimum_expected_kph": minimum, "calibration_method": calibration.method}))
                if len(segment_speeds) >= 3:
                    changes = [current - previous for previous, current in zip(segment_speeds, segment_speeds[1:])]
                    threshold = float(config.get("sudden_speed_change_kph", 30))
                    strongest = max(changes, key=abs)
                    if abs(strongest) >= threshold:
                        category = "Sudden acceleration" if strongest > 0 else "Sudden braking"
                        created.append(_add(db, job, track, category, min(.88, calibration.confidence * .82), timestamps[0], timestamps[len(timestamps)//2], timestamps[-1], {"speed_change_kph": round(strongest, 1), "calibration_method": calibration.method}))

    # Counting lines are evaluated without generating a violation. Values are stored in the job config snapshot.
    counts: dict[str, int] = {}
    for shape in counting_lines:
        line = _shape_points(shape)
        counts[shape.get("name", "Counting line")] = sum(_crosses(histories[track.id], line) for track in tracks)
    if counts:
        job.config_json = {**job.config_json, "directional_counts": counts}

    # A red-light finding is deliberately withheld unless an independently reliable signal timeline exists.
    signal_timeline = job.config_json.get("signal_timeline", []) or config.get("signal_timeline", [])
    if stop_lines and signal_timeline:
        for track in tracks:
            points = histories[track.id]
            if not _crosses(points, _shape_points(stop_lines[0])):
                continue
            crossing = next((point.timestamp_seconds for a, point in zip(points, points[1:]) if segments_cross((a.x, a.y), (point.x, point.y), *_shape_points(stop_lines[0])[:2])), None)
            red = next((item for item in signal_timeline if item.get("state") == "red" and item.get("start", 0) <= (crossing or -1) <= item.get("end", -1) and item.get("confidence", 0) >= .75), None)
            if red:
                created.append(_add(db, job, track, "Possible red-light violation", min(.95, float(red["confidence"])), crossing or 0, crossing or 0, (crossing or 0)+2, {"signal_state": "red", "signal_confidence": red["confidence"]}))

    # Deduplicate rows created by overlapping geometry using category/track/time, retaining the stronger record.
    unique = suppress_duplicates([
        IncidentCandidate(row.category, tuple(hash(value) for value in row.track_ids_json), row.peak_seconds, row.confidence)
        for row in created
    ])
    keep = {(item.category, item.track_ids, item.peak_seconds, item.confidence) for item in unique}
    final: list[Incident] = []
    for row in created:
        key = (row.category, tuple(hash(value) for value in row.track_ids_json), row.peak_seconds, row.confidence)
        if key in keep:
            final.append(row)
        else:
            db.delete(row)
    db.commit()
    return final
