from __future__ import annotations

import csv
import io
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import PROJECT_ROOT, get_settings
from ..database import get_db
from ..entities import (
    AnalysisJob, ApplicationSetting, Calibration, Camera, CameraConfiguration, Incident,
    IncidentEvidence, JobStatus, PlateRead, ProcessingLog, Track, VideoSource,
)
from ..schemas import AnalysisRequest, CalibrationInput, CameraConfigurationInput, CameraInput, IncidentUpdate, SettingsUpdate
from ..services.analysis_modules import build_modules
from ..services.pipeline import pipeline_runtime
from ..services.report import generate_draft_report
from ..services.video import probe_video


router = APIRouter()
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024 * 1024


def _safe_display_name(name: str | None) -> str:
    if not name:
        raise HTTPException(400, "A filename is required")
    value = Path(name).name
    if value != name or value in {".", ".."} or "\x00" in value:
        raise HTTPException(400, "Unsafe filename")
    return re.sub(r"[^A-Za-z0-9._ ()-]", "_", value)[:255]


def _delete_local_file(value: str | None) -> None:
    if not value:
        return
    root = get_settings().data_dir.resolve()
    path = Path(value).resolve()
    if path.is_relative_to(root) and path.is_file():
        path.unlink()


def _job(job: AnalysisJob) -> dict[str, Any]:
    return {
        "id": job.id, "video_id": job.video_id, "status": job.status, "progress": job.progress,
        "processed_frames": job.processed_frames, "total_frames": job.total_frames,
        "processing_fps": job.processing_fps, "active_module": job.active_module,
        "modules": job.modules_json, "error_message": job.error_message,
        "output_available": bool(job.output_video_path and Path(job.output_video_path).exists()),
        "created_at": job.created_at.isoformat(),
    }


def _incident(incident: Incident) -> dict[str, Any]:
    return {
        "id": incident.id, "incident_number": incident.incident_number, "job_id": incident.job_id,
        "category": incident.category, "severity": incident.severity, "confidence": incident.confidence,
        "review_status": incident.review_status, "is_simulation": incident.is_simulation,
        "track_ids": incident.track_ids_json, "vehicle_class": incident.vehicle_class,
        "plate_text": incident.plate_text, "plate_confidence": incident.plate_confidence,
        "start_seconds": incident.start_seconds, "peak_seconds": incident.peak_seconds,
        "end_seconds": incident.end_seconds, "measurements": incident.measurements_json,
        "operator_notes": incident.operator_notes, "created_at": incident.created_at.isoformat(),
    }


@router.get("/health")
def health(db: Session = Depends(get_db)):
    settings = get_settings()
    db.execute(select(func.count()).select_from(AnalysisJob)).scalar_one()
    disk = shutil.disk_usage(settings.data_dir)
    evidence_bytes = sum(path.stat().st_size for path in (settings.data_dir / "evidence").rglob("*") if path.is_file())
    camera_count = db.scalar(select(func.count()).select_from(Camera).where(Camera.enabled.is_(True))) or 0
    return {
        "status": "healthy", "app": settings.app_name, "version": "0.1.0",
        "database": "connected", "ffmpeg": bool(settings.ffmpeg_path), "ffprobe": bool(settings.ffprobe_path),
        "cpu_percent": psutil.cpu_percent(), "memory_percent": psutil.virtual_memory().percent,
        "disk_free_gb": round(disk.free / 1024**3, 1), "data_directory": str(settings.data_dir),
        "evidence_storage_mb": round(evidence_bytes / 1024**2, 2), "configured_cameras": camera_count,
        "bound_to": f"{settings.host}:{settings.port}", "local_only": settings.host in {"127.0.0.1", "localhost"},
    }


@router.get("/models/status")
def model_status():
    settings = get_settings()
    detector_file = settings.model_dir / Path(settings.yolo_model).name
    cuda = False
    device_name = "CPU"
    try:
        import torch
        cuda = torch.cuda.is_available()
        if cuda:
            device_name = torch.cuda.get_device_name(0)
    except Exception:
        pass
    try:
        import onnxruntime as ort
        onnx_providers = ort.get_available_providers()
    except Exception:
        onnx_providers = []
    modules = build_modules()
    return {
        "compute_device": device_name, "cuda_available": cuda,
        "onnx_providers": onnx_providers,
        "plate_execution_provider": "CPUExecutionProvider",
        "detector": {"name": settings.yolo_model, "status": "ready" if detector_file.is_file() else "downloads on first real analysis if absent", "tracker": "ByteTrack"},
        "plate": {
            "detector": "yolo-v9-t-384-license-plate-end2end", "ocr": "cct-xs-v2-global-model",
            "status": "ready when privacy acknowledgement and plate OCR are enabled",
            "profile": "Generic Latin / digits",
            "execution": "CPU (main vehicle detector/tracker still uses the selected CPU or CUDA profile)",
        },
        "modules": [{"key": item.key, "title": item.title, "status": item.model_status} for item in modules.values()],
    }


@router.get("/cameras")
def list_cameras(db: Session = Depends(get_db)):
    rows = db.scalars(select(Camera).order_by(Camera.created_at.desc())).all()
    return [{"id": row.id, "name": row.name, "location": row.location, "source_type": row.source_type, "enabled": row.enabled, "configured": bool(row.source_uri)} for row in rows]


@router.post("/cameras", status_code=201)
def create_camera(request: CameraInput, db: Session = Depends(get_db)):
    if request.source_uri and request.source_type in {"rtsp", "http"} and not request.source_uri.lower().startswith(("rtsp://", "http://", "https://")):
        raise HTTPException(422, "Stream URI must use RTSP, HTTP, or HTTPS")
    row = Camera(**request.model_dump())
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "location": row.location, "source_type": row.source_type, "enabled": row.enabled}


@router.post("/videos/upload", status_code=201)
async def upload_video(file: UploadFile = File(...), db: Session = Depends(get_db)):
    settings = get_settings()
    display_name = _safe_display_name(file.filename)
    extension = Path(display_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, f"Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    storage_name = f"{uuid.uuid4()}{extension}"
    destination = settings.data_dir / "input" / storage_name
    size = 0
    try:
        with destination.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Video exceeds the 8 GB local upload limit")
                output.write(chunk)
        metadata = probe_video(destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    video = VideoSource(
        display_name=display_name, storage_name=storage_name, file_path=str(destination),
        mime_type=file.content_type, size_bytes=size, duration_seconds=metadata.get("duration_seconds"),
        fps=metadata.get("fps"), width=metadata.get("width"), height=metadata.get("height"),
        frame_count=metadata.get("frame_count"), codec=metadata.get("codec"), metadata_json=metadata,
    )
    db.add(video); db.commit(); db.refresh(video)
    return {"id": video.id, "display_name": video.display_name, "size_bytes": size, "metadata": metadata}


@router.get("/videos")
def list_videos(db: Session = Depends(get_db)):
    rows = db.scalars(select(VideoSource).order_by(VideoSource.created_at.desc())).all()
    return [{
        "id": row.id, "display_name": row.display_name, "size_bytes": row.size_bytes,
        "duration_seconds": row.duration_seconds, "fps": row.fps, "width": row.width,
        "height": row.height, "frame_count": row.frame_count, "codec": row.codec,
        "created_at": row.created_at.isoformat(),
    } for row in rows]


@router.get("/videos/{video_id}")
def video_metadata(video_id: str, db: Session = Depends(get_db)):
    row = db.get(VideoSource, video_id)
    if row is None:
        raise HTTPException(404, "Video not found")
    return {"id": row.id, "display_name": row.display_name, "metadata": row.metadata_json, "size_bytes": row.size_bytes}


@router.get("/videos/{video_id}/frame")
def video_reference_frame(video_id: str, seconds: float = Query(default=0, ge=0), db: Session = Depends(get_db)):
    import cv2

    row = db.get(VideoSource, video_id)
    if row is None:
        raise HTTPException(404, "Video not found")
    if row.duration_seconds is not None and seconds > row.duration_seconds:
        raise HTTPException(422, "Frame timestamp is outside the video")
    capture = cv2.VideoCapture(row.file_path)
    try:
        if not capture.isOpened():
            raise HTTPException(422, "Video can no longer be decoded")
        capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ok, frame = capture.read()
        if not ok:
            raise HTTPException(422, "Could not decode the requested frame")
        encoded, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not encoded:
            raise HTTPException(500, "Could not encode the reference frame")
        return Response(content=buffer.tobytes(), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=60"})
    finally:
        capture.release()


@router.post("/videos/{video_id}/analysis", status_code=202)
def start_analysis(video_id: str, request: AnalysisRequest, db: Session = Depends(get_db)):
    if db.get(VideoSource, video_id) is None:
        raise HTTPException(404, "Video not found")
    if request.enable_plate_ocr and not request.privacy_acknowledged:
        raise HTTPException(422, "Acknowledge the local privacy warning before enabling plate OCR")
    config = request.model_dump()
    runtime_keys = {
        "detection_confidence", "ocr_confidence", "plate_detector_confidence", "retention_days",
        "plate_allowed_characters", "plate_minimum_length", "plate_maximum_length", "plate_regex",
    }
    for setting in db.scalars(select(ApplicationSetting).where(ApplicationSetting.key.in_(runtime_keys))).all():
        config[setting.key] = setting.value_json
    job = AnalysisJob(
        video_id=video_id, status=JobStatus.queued.value, modules_json=request.modules,
        config_json=config, active_module="Queued",
    )
    db.add(job); db.commit(); db.refresh(job)
    pipeline_runtime.start(job.id)
    return _job(job)


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    return [_job(row) for row in db.scalars(select(AnalysisJob).order_by(AnalysisJob.created_at.desc()).limit(100)).all()]


@router.get("/jobs/{job_id}")
def job_progress(job_id: str, db: Session = Depends(get_db)):
    row = db.get(AnalysisJob, job_id)
    if row is None:
        raise HTTPException(404, "Analysis job not found")
    logs = db.scalars(select(ProcessingLog).where(ProcessingLog.job_id == job_id).order_by(ProcessingLog.id.desc()).limit(30)).all()
    data = _job(row)
    data["logs"] = [{"level": log.level, "message": log.message, "created_at": log.created_at.isoformat()} for log in reversed(logs)]
    data["track_count"] = db.scalar(select(func.count()).select_from(Track).where(Track.job_id == job_id)) or 0
    data["plate_reads"] = db.scalar(select(func.count()).select_from(PlateRead).where(PlateRead.job_id == job_id)) or 0
    return data


@router.post("/jobs/{job_id}/cancel", status_code=202)
def cancel_analysis(job_id: str, db: Session = Depends(get_db)):
    row = db.get(AnalysisJob, job_id)
    if row is None:
        raise HTTPException(404, "Analysis job not found")
    if row.status not in {JobStatus.queued.value, JobStatus.processing.value}:
        raise HTTPException(409, "Only queued or processing jobs can be cancelled")
    row.cancel_requested = True; db.commit()
    return {"status": "cancellation_requested"}


@router.websocket("/ws/jobs/{job_id}")
async def job_updates(websocket: WebSocket, job_id: str):
    await websocket.accept()
    try:
        while True:
            with next(get_db()) as db:
                row = db.get(AnalysisJob, job_id)
                if row is None:
                    await websocket.send_json({"error": "Job not found"}); return
                await websocket.send_json(_job(row))
                if row.status in {JobStatus.completed.value, JobStatus.failed.value, JobStatus.cancelled.value}:
                    return
            import asyncio
            await asyncio.sleep(0.75)
    except WebSocketDisconnect:
        return


@router.get("/jobs/{job_id}/output")
def stream_output(job_id: str, db: Session = Depends(get_db)):
    row = db.get(AnalysisJob, job_id)
    if row is None or not row.output_video_path or not Path(row.output_video_path).is_file():
        raise HTTPException(404, "Annotated output is not available")
    return FileResponse(row.output_video_path, media_type="video/mp4", filename=f"trafficvision-{job_id}.mp4")


@router.get("/incidents")
def list_incidents(
    include_simulation: bool = False, review_status: str | None = None, db: Session = Depends(get_db)
):
    query = select(Incident)
    if not include_simulation:
        query = query.where(Incident.is_simulation.is_(False))
    if review_status:
        query = query.where(Incident.review_status == review_status)
    return [_incident(row) for row in db.scalars(query.order_by(Incident.created_at.desc())).all()]


@router.patch("/incidents/{incident_id}")
def update_incident(incident_id: str, request: IncidentUpdate, db: Session = Depends(get_db)):
    row = db.get(Incident, incident_id)
    if row is None:
        raise HTTPException(404, "Incident not found")
    row.review_status = request.review_status; row.operator_notes = request.operator_notes
    db.commit(); db.refresh(row)
    return _incident(row)


@router.get("/incidents/{incident_id}/evidence")
def incident_evidence(incident_id: str, db: Session = Depends(get_db)):
    if db.get(Incident, incident_id) is None:
        raise HTTPException(404, "Incident not found")
    rows = db.scalars(select(IncidentEvidence).where(IncidentEvidence.incident_id == incident_id)).all()
    return [{
        "id": row.id, "type": row.evidence_type, "metadata": row.metadata_json,
        "available": Path(row.file_path).is_file(), "url": f"/api/evidence/{row.id}/file",
    } for row in rows]


@router.get("/evidence/{evidence_id}/file")
def evidence_file(evidence_id: str, db: Session = Depends(get_db)):
    row = db.get(IncidentEvidence, evidence_id)
    if row is None or not Path(row.file_path).is_file():
        raise HTTPException(404, "Evidence file not found")
    suffix = Path(row.file_path).suffix.lower()
    media = {".jpg": "image/jpeg", ".png": "image/png", ".mp4": "video/mp4", ".pdf": "application/pdf"}.get(suffix, "application/octet-stream")
    return FileResponse(row.file_path, media_type=media)


@router.delete("/incidents/{incident_id}", status_code=204)
def delete_incident(incident_id: str, db: Session = Depends(get_db)):
    row = db.get(Incident, incident_id)
    if row is None:
        raise HTTPException(404, "Incident not found")
    evidence = db.scalars(select(IncidentEvidence).where(IncidentEvidence.incident_id == incident_id)).all()
    for item in evidence:
        if not any((item.metadata_json or {}).get(key) for key in ("shared_job_output", "shared_plate_crop")):
            _delete_local_file(item.file_path)
        db.delete(item)
    db.delete(row); db.commit()


@router.get("/incidents/{incident_id}/report")
def incident_report(incident_id: str, db: Session = Depends(get_db)):
    row = db.get(Incident, incident_id)
    if row is None:
        raise HTTPException(404, "Incident not found")
    path = get_settings().data_dir / "evidence" / f"draft-report-{row.incident_number}.pdf"
    images = [Path(item.file_path) for item in db.scalars(
        select(IncidentEvidence).where(
            IncidentEvidence.incident_id == incident_id,
            IncidentEvidence.evidence_type.in_(["before_frame", "event_frame", "after_frame"]),
        )
    ).all()]
    generate_draft_report(row, path, images)
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.post("/simulation/reset")
def reset_simulation(db: Session = Depends(get_db)):
    for row in db.scalars(select(Incident).where(Incident.is_simulation.is_(True))).all():
        db.delete(row)
    examples = [
        ("Possible speeding", "high", .91, "Car", "DEMO42", {"speed_kph": 78, "speed_limit_kph": 50, "calibration": "simulated"}),
        ("Possible collision", "critical", .76, "Truck", "Unreadable", {"relative_speed_change": 0.63}),
        ("Wrong-way movement", "medium", .84, "Motorcycle", "Insufficient confidence", {"direction_similarity": -0.88}),
        ("Heavy congestion", "medium", .88, None, "Unreadable", {"queue_length": 19, "waiting_seconds": 143}),
    ]
    now = datetime.now(timezone.utc)
    for index, (category, severity, confidence, vehicle, plate, measurements) in enumerate(examples, 1):
        db.add(Incident(
            incident_number=f"SIM-{now:%Y%m%d}-{index:03d}", category=category, severity=severity,
            confidence=confidence, is_simulation=True, vehicle_class=vehicle, plate_text=plate,
            plate_confidence=.86 if plate == "DEMO42" else 0, start_seconds=index * 12,
            peak_seconds=index * 12 + 2, end_seconds=index * 12 + 6, measurements_json=measurements,
        ))
    db.commit()
    return {"created": len(examples), "mode": "Simulation/Demo Mode", "warning": "These are synthetic examples, not AI analysis"}


@router.get("/plates")
def search_plates(q: str = Query(default="", max_length=40), db: Session = Depends(get_db)):
    query = select(PlateRead)
    if q:
        query = query.where(PlateRead.text.ilike(f"%{q.upper()}%"))
    rows = db.scalars(query.order_by(PlateRead.created_at.desc()).limit(200)).all()
    return [{
        "id": row.id, "job_id": row.job_id, "track_id": row.track_id, "text": row.text,
        "confidence": row.confidence, "status": row.status, "alternatives": row.alternatives_json,
        "observed_at_seconds": row.observed_at_seconds, "crop_available": bool(row.crop_path),
        "created_at": row.created_at.isoformat(),
    } for row in rows]


@router.get("/plates/{plate_id}/crop")
def plate_crop(plate_id: str, db: Session = Depends(get_db)):
    row = db.get(PlateRead, plate_id)
    if row is None or not row.crop_path or not Path(row.crop_path).is_file():
        raise HTTPException(404, "Plate crop not available")
    return FileResponse(row.crop_path, media_type="image/jpeg")


@router.delete("/plates/{plate_id}", status_code=204)
def delete_plate_read(plate_id: str, db: Session = Depends(get_db)):
    row = db.get(PlateRead, plate_id)
    if row is None:
        raise HTTPException(404, "Plate read not found")
    _delete_local_file(row.crop_path)
    db.delete(row); db.commit()


@router.delete("/evidence/{evidence_id}", status_code=204)
def delete_evidence(evidence_id: str, db: Session = Depends(get_db)):
    row = db.get(IncidentEvidence, evidence_id)
    if row is None:
        raise HTTPException(404, "Evidence not found")
    if not any((row.metadata_json or {}).get(key) for key in ("shared_job_output", "shared_plate_crop")):
        _delete_local_file(row.file_path)
    db.delete(row); db.commit()


@router.get("/analytics")
def analytics(db: Session = Depends(get_db)):
    jobs = db.scalar(select(func.count()).select_from(AnalysisJob)) or 0
    completed = db.scalar(select(func.count()).select_from(AnalysisJob).where(AnalysisJob.status == "completed")) or 0
    tracks = db.scalar(select(func.count()).select_from(Track)) or 0
    incidents = db.scalar(select(func.count()).select_from(Incident).where(Incident.is_simulation.is_(False))) or 0
    plates = db.scalar(select(func.count()).select_from(PlateRead)) or 0
    readable = db.scalar(select(func.count()).select_from(PlateRead).where(~PlateRead.text.in_(["Unreadable", "Insufficient confidence"]))) or 0
    classes = db.execute(select(Track.object_class, func.count()).group_by(Track.object_class)).all()
    speeds = [float(value) for value in db.scalars(select(Track.best_speed_kph).where(Track.best_speed_kph.is_not(None))).all()]
    bins = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 120), (120, 300)]
    directional: dict[str, int] = {}
    camera_jobs: dict[str, int] = {}
    for job in db.scalars(select(AnalysisJob)).all():
        for name, value in (job.config_json or {}).get("directional_counts", {}).items():
            directional[name] = directional.get(name, 0) + int(value)
        config_id = (job.config_json or {}).get("configuration_id")
        if config_id:
            camera_jobs[config_id] = camera_jobs.get(config_id, 0) + 1
    frequencies = db.execute(
        select(Incident.category, func.count()).where(Incident.is_simulation.is_(False)).group_by(Incident.category)
    ).all()
    parking_rows = db.scalars(
        select(Incident).where(Incident.is_simulation.is_(False), Incident.category.ilike("%parking%"))
    ).all()
    parking_durations = [float(row.measurements_json.get("dwell_seconds")) for row in parking_rows if row.measurements_json.get("dwell_seconds") is not None]
    return {
        "jobs": jobs, "completed_jobs": completed, "total_tracks": tracks, "real_incidents": incidents,
        "plate_reads": plates, "plate_success_rate": readable / plates if plates else 0,
        "class_distribution": [{"name": name, "value": value} for name, value in classes],
        "directional_flow": [{"name": name, "value": value} for name, value in directional.items()],
        "average_calibrated_speed_kph": round(sum(speeds) / len(speeds), 1) if speeds else None,
        "speed_distribution": [{"name": f"{low}-{high}", "value": sum(low <= speed < high for speed in speeds)} for low, high in bins],
        "incident_frequency": [{"name": name, "value": value} for name, value in frequencies],
        "average_parking_seconds": round(sum(parking_durations) / len(parking_durations), 1) if parking_durations else None,
        "camera_job_comparison": [{"configuration_id": key, "jobs": value} for key, value in camera_jobs.items()],
        "note": "Speed and congestion analytics appear after configured zones/calibration and real video analysis.",
    }


@router.get("/analytics/vehicle-counts.csv")
def export_counts(db: Session = Depends(get_db)):
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(["class", "unique_tracks"])
    for name, value in db.execute(select(Track.object_class, func.count()).group_by(Track.object_class)).all():
        writer.writerow([name, value])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=trafficvision-counts.csv"})


@router.get("/camera-configurations")
def camera_configurations(db: Session = Depends(get_db)):
    rows = db.scalars(select(CameraConfiguration).order_by(CameraConfiguration.updated_at.desc())).all()
    return [{
        "id": row.id, "name": row.name, "camera_id": row.camera_id,
        "original_width": row.original_width, "original_height": row.original_height,
        "config": row.config_json, "updated_at": row.updated_at.isoformat(),
    } for row in rows]


@router.post("/camera-configurations", status_code=201)
def save_camera_configuration(request: CameraConfigurationInput, db: Session = Depends(get_db)):
    row = CameraConfiguration(
        name=request.name, camera_id=request.camera_id, original_width=request.original_width,
        original_height=request.original_height, config_json=request.config,
    )
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "config": row.config_json}


@router.put("/camera-configurations/{configuration_id}")
def update_camera_configuration(configuration_id: str, request: CameraConfigurationInput, db: Session = Depends(get_db)):
    row = db.get(CameraConfiguration, configuration_id)
    if row is None:
        raise HTTPException(404, "Configuration not found")
    row.name = request.name; row.camera_id = request.camera_id
    row.original_width = request.original_width; row.original_height = request.original_height
    row.config_json = request.config
    db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "config": row.config_json}


@router.post("/camera-configurations/{configuration_id}/duplicate", status_code=201)
def duplicate_camera_configuration(configuration_id: str, db: Session = Depends(get_db)):
    source = db.get(CameraConfiguration, configuration_id)
    if source is None:
        raise HTTPException(404, "Configuration not found")
    row = CameraConfiguration(
        name=f"{source.name} copy", camera_id=source.camera_id,
        original_width=source.original_width, original_height=source.original_height,
        config_json=source.config_json,
    )
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "config": row.config_json}


@router.get("/camera-configurations/{configuration_id}/export")
def export_camera_configuration(configuration_id: str, db: Session = Depends(get_db)):
    row = db.get(CameraConfiguration, configuration_id)
    if row is None:
        raise HTTPException(404, "Configuration not found")
    return JSONResponse({
        "schema": "trafficvision.camera.v1", "name": row.name,
        "original_width": row.original_width, "original_height": row.original_height,
        "config": row.config_json,
    }, headers={"Content-Disposition": f'attachment; filename="{row.name}.json"'})


@router.post("/calibrations", status_code=201)
def save_calibration(request: CalibrationInput, db: Session = Depends(get_db)):
    if db.get(CameraConfiguration, request.configuration_id) is None:
        raise HTTPException(404, "Camera configuration not found")
    row = Calibration(
        configuration_id=request.configuration_id, method=request.method,
        reference_json=request.reference, speed_region_json=request.speed_region,
        speed_limit_kph=request.speed_limit_kph, confidence=request.confidence,
    )
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "method": row.method, "speed_limit_kph": row.speed_limit_kph}


@router.get("/settings")
def get_application_settings(db: Session = Depends(get_db)):
    stored = {row.key: row.value_json for row in db.scalars(select(ApplicationSetting)).all()}
    return {
        "values": stored,
        "plate_profiles": [
            {"name": "Generic Latin / digits", "allowed_characters": "A-Z, 0-9", "min_length": 4, "max_length": 12, "regex": ""},
            {"name": "Ethiopian (editable placeholder)", "allowed_characters": "operator-defined", "min_length": 4, "max_length": 12, "regex": "", "verified_format": False},
        ],
    }


@router.put("/settings")
def update_application_settings(request: SettingsUpdate, db: Session = Depends(get_db)):
    forbidden = {"data_dir", "database_url", "host"}
    if forbidden.intersection(request.values):
        raise HTTPException(422, "Protected filesystem/network settings cannot be changed through this endpoint")
    for key, value in request.values.items():
        row = db.get(ApplicationSetting, key)
        if row is None:
            db.add(ApplicationSetting(key=key, value_json=value))
        else:
            row.value_json = value
    db.commit()
    return {"updated": sorted(request.values)}
