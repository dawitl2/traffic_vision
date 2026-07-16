from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
from sqlalchemy.orm import Session

from ..config import get_settings
from ..entities import Incident, IncidentEvidence, PlateRead


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
