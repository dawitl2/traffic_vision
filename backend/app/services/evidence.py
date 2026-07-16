from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
from sqlalchemy.orm import Session

from ..config import get_settings
from ..entities import Incident, IncidentEvidence, PlateRead, TrackPoint


def _clock(seconds: float) -> str:
    minutes = int(max(0, seconds) // 60)
    remaining = max(0, seconds) - minutes * 60
    return f"{minutes:02d}:{remaining:05.2f}"


def overlay_incident_alerts(db: Session, annotated_path: str, incidents: list[Incident]) -> None:
    """Burn collision alerts, involved boxes, analysis date, and video time into output."""
    collisions = [incident for incident in incidents if "collision" in incident.category.lower()]
    path = Path(annotated_path)
    if not collisions or not path.is_file():
        return
    histories = {
        track_id: list(db.query(TrackPoint).filter(TrackPoint.track_id == track_id).order_by(TrackPoint.timestamp_seconds).all())
        for incident in collisions for track_id in incident.track_ids_json
    }
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return
    fps = float(capture.get(cv2.CAP_PROP_FPS)) or 25.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    temporary = path.with_name(f"{path.stem}-alerts{path.suffix}")
    writer = cv2.VideoWriter(str(temporary), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        capture.release()
        return
    frame_index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            timestamp = frame_index / fps
            frame_index += 1
            for incident in collisions:
                if not (incident.start_seconds <= timestamp <= incident.end_seconds):
                    continue
                event_date = incident.created_at.strftime("%Y-%m-%d") if incident.created_at else "Unknown"
                cv2.rectangle(frame, (10, 10), (min(width - 10, 535), 94), (0, 0, 0), -1)
                cv2.rectangle(frame, (10, 10), (min(width - 10, 535), 94), (0, 0, 255), 3)
                cv2.putText(frame, "COLLISION DETECTED", (24, 39), cv2.FONT_HERSHEY_SIMPLEX, .78, (0, 0, 255), 2)
                cv2.putText(frame, f"Analysis date (UTC): {event_date}", (24, 63), cv2.FONT_HERSHEY_SIMPLEX, .48, (255, 255, 255), 1)
                cv2.putText(frame, f"Event: {_clock(incident.peak_seconds)}   Video: {_clock(timestamp)}", (24, 84), cv2.FONT_HERSHEY_SIMPLEX, .48, (255, 255, 255), 1)
                for track_id in incident.track_ids_json:
                    points = histories.get(track_id, [])
                    if not points:
                        continue
                    point = min(points, key=lambda item: abs(item.timestamp_seconds - timestamp))
                    if abs(point.timestamp_seconds - timestamp) > .35:
                        continue
                    x1, y1, x2, y2 = point.bbox_json
                    left, top = int(x1 * width), int(y1 * height)
                    right, bottom = int(x2 * width), int(y2 * height)
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 4)
                    cv2.putText(frame, "COLLISION DETECTED", (left, max(112, top - 8)), cv2.FONT_HERSHEY_SIMPLEX, .55, (0, 0, 255), 2)
            writer.write(frame)
    finally:
        capture.release()
        writer.release()
    if temporary.is_file() and temporary.stat().st_size > 0:
        temporary.replace(path)


def _frame_at(video_path: str, seconds: float, output: Path) -> bool:
    capture = cv2.VideoCapture(video_path)
    try:
        capture.set(cv2.CAP_PROP_POS_MSEC, max(0, seconds) * 1000)
        ok, frame = capture.read()
        if not ok:
            return False
        output.parent.mkdir(parents=True, exist_ok=True)
        return bool(cv2.imwrite(str(output), frame))
    finally:
        capture.release()


def create_incident_evidence(
    db: Session, incident: Incident, source_path: str, annotated_path: str | None
) -> list[IncidentEvidence]:
    settings = get_settings()
    directory = settings.data_dir / "evidence" / incident.id
    directory.mkdir(parents=True, exist_ok=True)
    created: list[IncidentEvidence] = []
    for evidence_type, timestamp in (
        ("before_frame", max(0, incident.start_seconds - 1)),
        ("event_frame", incident.peak_seconds),
        ("after_frame", incident.end_seconds + 1),
    ):
        path = directory / f"{evidence_type}.jpg"
        if _frame_at(source_path, timestamp, path):
            row = IncidentEvidence(incident_id=incident.id, evidence_type=evidence_type, file_path=str(path), metadata_json={"timestamp_seconds": timestamp})
            db.add(row); created.append(row)
    if settings.ffmpeg_path:
        clip = directory / "evidence.mp4"
        start = max(0, incident.start_seconds - settings.evidence_seconds_before)
        duration = max(1, incident.end_seconds - start + settings.evidence_seconds_after)
        command = [settings.ffmpeg_path, "-y", "-ss", f"{start:.3f}", "-i", source_path, "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-an", str(clip)]
        completed = subprocess.run(command, capture_output=True, timeout=180)
        if completed.returncode == 0 and clip.exists():
            row = IncidentEvidence(incident_id=incident.id, evidence_type="evidence_clip", file_path=str(clip), metadata_json={"start_seconds": start, "duration_seconds": duration})
            db.add(row); created.append(row)
    if annotated_path and Path(annotated_path).is_file():
        row = IncidentEvidence(incident_id=incident.id, evidence_type="annotated_trajectory_video", file_path=annotated_path, metadata_json={"shared_job_output": True})
        db.add(row); created.append(row)
    if incident.track_ids_json:
        plate = db.query(PlateRead).filter(PlateRead.track_id == incident.track_ids_json[0]).order_by(PlateRead.confidence.desc()).first()
        if plate and plate.crop_path and Path(plate.crop_path).is_file():
            row = IncidentEvidence(incident_id=incident.id, evidence_type="plate_crop", file_path=plate.crop_path, metadata_json={"ocr_text": plate.text, "confidence": plate.confidence, "shared_plate_crop": True})
            db.add(row); created.append(row)
    db.commit()
    return created
