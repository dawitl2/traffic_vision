"""End-to-end local upload smoke test using generated non-traffic footage."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.entities import AnalysisJob, Incident, VideoSource  # noqa: E402
from app.services.evidence import create_incident_evidence  # noqa: E402


def make_video(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (320, 240))
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not create the synthetic smoke-test video")
    try:
        for index in range(30):
            frame = np.full((240, 320, 3), (12, 18, 20), dtype=np.uint8)
            cv2.rectangle(frame, (index * 5, 90), (index * 5 + 60, 135), (45, 150, 130), -1)
            cv2.putText(frame, "SYNTHETIC SMOKE TEST", (40, 35), cv2.FONT_HERSHEY_SIMPLEX, .55, (220, 230, 232), 1)
            writer.write(frame)
    finally:
        writer.release()


def main() -> int:
    source = ROOT / "data" / "temp" / "SMOKE_TEST_SYNTHETIC.mp4"
    make_video(source)
    with TestClient(app) as client, source.open("rb") as stream:
        upload = client.post("/api/videos/upload", files={"file": (source.name, stream, "video/mp4")})
        upload.raise_for_status()
        video = upload.json()
        start = client.post(
            f"/api/videos/{video['id']}/analysis",
            json={
                "modules": ["vehicle_counting"], "performance_profile": "CPU Light",
                "frame_skip": 3, "inference_size": 320, "detection_confidence": .35,
                "enable_plate_ocr": False, "privacy_acknowledged": False,
            },
        )
        start.raise_for_status()
        job_id = start.json()["id"]
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            result = client.get(f"/api/jobs/{job_id}").json()
            print(f"{result['status']:>10} {result['progress']:.0%} {result['active_module']}")
            if result["status"] in {"completed", "failed", "cancelled"}:
                if result["status"] != "completed":
                    raise RuntimeError(result.get("error_message") or result["status"])
                output = client.get(f"/api/jobs/{job_id}/output")
                if output.status_code != 200 or not output.content:
                    raise RuntimeError("Annotated output was not streamable")
                with SessionLocal() as db:
                    job = db.get(AnalysisJob, job_id)
                    video_row = db.get(VideoSource, video["id"])
                    incident = Incident(
                        incident_number=f"SMOKE-{job_id[:8]}", job_id=job_id,
                        category="Synthetic evidence-system smoke test", severity="low",
                        confidence=1.0, is_simulation=True, plate_text="Unreadable",
                        start_seconds=.5, peak_seconds=1.0, end_seconds=1.5,
                        measurements_json={"synthetic": True},
                    )
                    db.add(incident); db.commit(); db.refresh(incident)
                    evidence = create_incident_evidence(db, incident, video_row.file_path, job.output_video_path)
                    if not evidence:
                        raise RuntimeError("Synthetic incident evidence was not generated")
                    incident_id, evidence_id = incident.id, evidence[0].id
                evidence_response = client.get(f"/api/evidence/{evidence_id}/file")
                report_response = client.get(f"/api/incidents/{incident_id}/report")
                if evidence_response.status_code != 200 or report_response.status_code != 200:
                    raise RuntimeError("Evidence or draft report was not streamable")
                print(f"PASS job={job_id} frames={result['processed_frames']} output_bytes={len(output.content)}")
                return 0
            time.sleep(.5)
    raise TimeoutError("Smoke-test analysis did not finish within 240 seconds")


if __name__ == "__main__":
    raise SystemExit(main())
