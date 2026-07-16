from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from sqlalchemy import select

from ..config import get_settings
from ..database import SessionLocal
from ..entities import AnalysisJob, CameraConfiguration, JobStatus, PlateRead, ProcessingLog, Track, TrackPoint, VideoSource
from .plates import PlateCandidate, PlateProfile, vote_plate_candidates
from .evaluation import evaluate_configured_rules
from .evidence import create_incident_evidence, overlay_incident_alerts
from .signal import build_signal_timeline, classify_signal_state


LOGGER = logging.getLogger(__name__)
VEHICLE_CLASSES = {"car", "motorcycle", "bus", "truck", "bicycle"}
RELEVANT_CLASSES = VEHICLE_CLASSES | {"person", "dog", "cat", "horse", "sheep", "cow", "bird"}


class PipelineRuntime:
    def __init__(self) -> None:
        self._threads: dict[str, threading.Thread] = {}
        self._models: dict[str, Any] = {}
        self._alpr: Any = None
        self._lock = threading.Lock()
        self._analysis_lock = threading.Lock()

    def start(self, job_id: str) -> None:
        thread = threading.Thread(target=self._run, args=(job_id,), daemon=True, name=f"analysis-{job_id[:8]}")
        self._threads[job_id] = thread
        thread.start()

    def _log(self, db, job_id: str, message: str, level: str = "INFO") -> None:
        db.add(ProcessingLog(job_id=job_id, message=message, level=level))
        db.commit()

    def _load_detector(self, model_name: str):
        with self._lock:
            if model_name not in self._models:
                from ultralytics import YOLO
                settings = get_settings()
                model_path = Path(model_name)
                if not model_path.is_absolute() and model_path.parent == Path("."):
                    model_path = settings.model_dir / model_path.name
                self._models[model_name] = YOLO(str(model_path))
            return self._models[model_name]

    def _load_alpr(self):
        with self._lock:
            if self._alpr is None:
                from fast_alpr import ALPR
                settings = get_settings()
                self._alpr = ALPR(
                    detector_model="yolo-v9-t-384-license-plate-end2end",
                    ocr_model="cct-xs-v2-global-model",
                    detector_conf_thresh=settings.plate_detector_confidence,
                    # The main YOLO tracker uses PyTorch/CUDA. These compact ONNX
                    # plate models run reliably on CPU without requiring a second,
                    # system-wide CUDA/cuDNN runtime whose ABI may differ from
                    # PyTorch's bundled CUDA libraries.
                    detector_providers=["CPUExecutionProvider"],
                    ocr_device="cpu",
                    ocr_providers=["CPUExecutionProvider"],
                )
            return self._alpr

    @staticmethod
    def _extract_plate_results(results: Any) -> list[PlateCandidate]:
        candidates: list[PlateCandidate] = []
        for result in results or []:
            ocr = getattr(result, "ocr", None) or (result.get("ocr") if isinstance(result, dict) else None)
            if ocr is None:
                continue
            text = getattr(ocr, "text", None) or (ocr.get("text") if isinstance(ocr, dict) else None)
            confidence = getattr(ocr, "confidence", None)
            if confidence is None and isinstance(ocr, dict):
                confidence = ocr.get("confidence")
            if text and confidence is not None:
                candidates.append(PlateCandidate(str(text), float(confidence)))
        return candidates

    @staticmethod
    def _plate_crops(results: Any, vehicle_crop: np.ndarray) -> list[tuple[float, np.ndarray]]:
        crops: list[tuple[float, np.ndarray]] = []
        height, width = vehicle_crop.shape[:2]
        for result in results or []:
            detection = getattr(result, "detection", None)
            box = getattr(detection, "bounding_box", None)
            if box is None:
                continue
            x1, y1 = max(0, int(box.x1)), max(0, int(box.y1))
            x2, y2 = min(width, int(box.x2)), min(height, int(box.y2))
            plate = vehicle_crop[y1:y2, x1:x2]
            if plate.size:
                crops.append((float(getattr(detection, "confidence", 0.0)), plate.copy()))
        return crops

    def _run(self, job_id: str) -> None:
        # Ultralytics tracker state is model-bound; serialize jobs so IDs never leak across videos.
        with self._analysis_lock:
            self._run_locked(job_id)

    def _run_locked(self, job_id: str) -> None:
        settings = get_settings()
        db = SessionLocal()
        capture: cv2.VideoCapture | None = None
        writer: cv2.VideoWriter | None = None
        try:
            job = db.get(AnalysisJob, job_id)
            if job is None:
                return
            if job.cancel_requested:
                job.status = JobStatus.cancelled.value
                job.active_module = "Cancelled before processing"
                db.commit()
                return
            video = db.get(VideoSource, job.video_id)
            if video is None:
                raise RuntimeError("Video source no longer exists")
            job.status = JobStatus.processing.value
            job.started_at = datetime.now(timezone.utc)
            job.active_module = "Loading object detector"
            db.commit()
            self._log(db, job_id, "Starting local analysis; no footage leaves this computer")
            requested_profile = str(job.config_json.get("performance_profile", settings.performance_profile))
            detector_name = "yolo11s.pt" if requested_profile == "GPU Accuracy" else settings.yolo_model
            model = self._load_detector(detector_name)
            if getattr(model, "predictor", None) is not None:
                model.predictor = None
            enable_ocr = bool(job.config_json.get("enable_plate_ocr"))
            if enable_ocr and not job.config_json.get("privacy_acknowledged"):
                enable_ocr = False
                self._log(db, job_id, "Plate OCR disabled: privacy acknowledgement was not provided", "WARNING")
            alpr = self._load_alpr() if enable_ocr else None
            capture = cv2.VideoCapture(video.file_path)
            if not capture.isOpened():
                raise RuntimeError("OpenCV could not decode this video")
            fps = float(capture.get(cv2.CAP_PROP_FPS)) or video.fps or 25.0
            total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or video.frame_count or 0
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            output_path = settings.data_dir / "output" / f"{job_id}.mp4"
            writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
            if not writer.isOpened():
                raise RuntimeError("Could not create the annotated output video")
            job.total_frames = total
            job.output_video_path = str(output_path)
            job.active_module = "Object detection & ByteTrack"
            db.commit()
            frame_index = 0
            processed = 0
            started = time.perf_counter()
            track_rows: dict[int, Track] = {}
            plate_candidates: dict[int, list[PlateCandidate]] = defaultdict(list)
            best_plate_crops: dict[int, tuple[float, np.ndarray, float]] = {}
            signal_observations: list[tuple[float, str, float]] = []
            signal_polygon: list[tuple[float, float]] = []
            configuration_id = job.config_json.get("configuration_id")
            if configuration_id:
                configuration = db.get(CameraConfiguration, configuration_id)
                for shape in (configuration.config_json.get("shapes", []) if configuration else []):
                    if str(shape.get("type", "")).lower() in {"traffic light", "traffic_light"}:
                        signal_polygon = [
                            (float(point.get("x")), float(point.get("y"))) if isinstance(point, dict) else (float(point[0]), float(point[1]))
                            for point in shape.get("points", [])
                        ]
                        break
            frame_skip = max(1, int(job.config_json.get("frame_skip", settings.frame_skip)))
            inference_size = int(job.config_json.get("inference_size", settings.inference_size))
            confidence = float(job.config_json.get("detection_confidence", settings.detection_confidence))
            enabled_modules = set(job.modules_json or [])
            if requested_profile == "GPU Accuracy":
                frame_skip = 1
                inference_size = max(inference_size, 960)
                confidence = min(confidence, .18)
            elif "collision" in enabled_modules:
                frame_skip = 1
                confidence = min(confidence, .22)
            inference_device: str | int = "cpu"
            if requested_profile.startswith("GPU"):
                try:
                    import torch
                    if torch.cuda.is_available():
                        inference_device = 0
                    else:
                        self._log(db, job_id, "GPU profile requested but CUDA is unavailable; using CPU", "WARNING")
                except Exception:
                    self._log(db, job_id, "GPU runtime check failed; using CPU", "WARNING")
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                frame_index += 1
                job = db.get(AnalysisJob, job_id)
                if job and job.cancel_requested:
                    job.status = JobStatus.cancelled.value
                    job.active_module = "Cancelled safely"
                    db.commit()
                    self._log(db, job_id, "Analysis cancelled by operator", "WARNING")
                    return
                if frame_index % frame_skip:
                    writer.write(frame)
                    continue
                timestamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                if timestamp <= 0:
                    timestamp = frame_index / fps
                try:
                    results = model.track(
                        frame, persist=True, tracker="bytetrack.yaml", conf=confidence, iou=.45, imgsz=inference_size,
                        device=inference_device, verbose=False,
                    )
                except RuntimeError as exc:
                    if inference_device != "cpu" and "out of memory" in str(exc).lower():
                        import torch
                        torch.cuda.empty_cache()
                        inference_device = "cpu"
                        self._log(db, job_id, "CUDA memory exhausted; continuing this job on CPU", "WARNING")
                        results = model.track(
                            frame, persist=True, tracker="bytetrack.yaml", conf=confidence,
                            iou=.45, imgsz=min(inference_size, 640), device="cpu", verbose=False,
                        )
                    else:
                        raise
                annotated = frame.copy()
                if signal_polygon:
                    signal_observations.append((timestamp, *classify_signal_state(frame, signal_polygon)))
                boxes = results[0].boxes if results else None
                if boxes is not None and boxes.id is not None:
                    ids = boxes.id.int().cpu().tolist()
                    coords = boxes.xyxy.cpu().tolist()
                    classes = boxes.cls.int().cpu().tolist()
                    scores = boxes.conf.cpu().tolist()
                    names = results[0].names
                    for external_id, bbox, class_id, score in zip(ids, coords, classes, scores, strict=True):
                        label = str(names[class_id])
                        if label not in RELEVANT_CLASSES:
                            continue
                        x1, y1, x2, y2 = (int(value) for value in bbox)
                        center = ((x1 + x2) / 2, y2)
                        row = track_rows.get(external_id)
                        if row is None:
                            row = Track(
                                job_id=job_id, external_track_id=external_id, object_class=label,
                                max_confidence=float(score), first_seen_seconds=timestamp,
                                last_seen_seconds=timestamp,
                            )
                            db.add(row); db.flush(); track_rows[external_id] = row
                        row.last_seen_seconds = timestamp
                        row.max_confidence = max(row.max_confidence, float(score))
                        db.add(TrackPoint(
                            track_id=row.id, timestamp_seconds=timestamp, x=center[0] / width,
                            y=center[1] / height, bbox_json=[x1 / width, y1 / height, x2 / width, y2 / height],
                        ))
                        color = (28, 192, 150) if label in VEHICLE_CLASSES else (64, 191, 255)
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                        cv2.putText(annotated, f"{label} #{external_id}", (x1, max(18, y1 - 7)), cv2.FONT_HERSHEY_SIMPLEX, .52, color, 2)
                        if alpr is not None and label in VEHICLE_CLASSES and frame_index % (frame_skip * 6) == 0:
                            crop = frame[max(0, y1):min(height, y2), max(0, x1):min(width, x2)]
                            if crop.size and crop.shape[0] >= 40 and crop.shape[1] >= 80:
                                sharpness = float(cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
                                if sharpness >= 35:
                                    try:
                                        alpr_results = alpr.predict(crop)
                                        plate_candidates[external_id].extend(self._extract_plate_results(alpr_results))
                                        for detection_confidence, plate_crop in self._plate_crops(alpr_results, crop):
                                            plate_sharpness = float(cv2.Laplacian(cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
                                            quality = detection_confidence * max(1.0, plate_sharpness)
                                            previous = best_plate_crops.get(external_id)
                                            if previous is None or quality > previous[0]:
                                                best_plate_crops[external_id] = (quality, plate_crop, timestamp)
                                    except Exception as exc:  # OCR failure must not abort video analysis
                                        self._log(db, job_id, f"Plate OCR skipped a crop: {exc}", "WARNING")
                writer.write(annotated)
                processed += 1
                if processed % 5 == 0:
                    elapsed = max(time.perf_counter() - started, 0.001)
                    job = db.get(AnalysisJob, job_id)
                    if job:
                        job.processed_frames = frame_index
                        job.progress = min(frame_index / total, 0.99) if total else 0.0
                        job.processing_fps = processed / elapsed
                        db.commit()
            for external_id, row in track_rows.items():
                if not enable_ocr or row.object_class not in VEHICLE_CLASSES:
                    continue
                profile = PlateProfile(
                    allowed_characters=str(job.config_json.get("plate_allowed_characters", "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")),
                    minimum_length=int(job.config_json.get("plate_minimum_length", 4)),
                    maximum_length=int(job.config_json.get("plate_maximum_length", 12)),
                    pattern=str(job.config_json.get("plate_regex", "")),
                    confidence_threshold=float(job.config_json.get("ocr_confidence", settings.ocr_confidence)),
                )
                text, plate_confidence, alternatives = vote_plate_candidates(plate_candidates[external_id], profile)
                crop_path: str | None = None
                if external_id in best_plate_crops:
                    crop_file = settings.data_dir / "plate-crops" / f"{job_id}-{external_id}.jpg"
                    cv2.imwrite(str(crop_file), best_plate_crops[external_id][1])
                    crop_path = str(crop_file)
                db.add(PlateRead(
                    job_id=job_id, track_id=row.id, text=text, confidence=plate_confidence,
                    status="Read" if text not in {"Unreadable", "Insufficient confidence"} else text,
                    alternatives_json=alternatives, crop_path=crop_path,
                    observed_at_seconds=best_plate_crops.get(external_id, (0, None, row.last_seen_seconds))[2],
                ))
            db.commit()
            job = db.get(AnalysisJob, job_id)
            if signal_observations:
                job.config_json = {**job.config_json, "signal_timeline": build_signal_timeline(signal_observations)}
            job.active_module = "Configured traffic rules"
            db.commit()
            incidents = evaluate_configured_rules(db, job)
            if writer is not None:
                writer.release()
                writer = None
            if incidents:
                job.active_module = "Incident evidence"
                db.commit()
                overlay_incident_alerts(db, str(output_path), incidents)
                for incident in incidents:
                    create_incident_evidence(db, incident, video.file_path, str(output_path))
            job = db.get(AnalysisJob, job_id)
            job.status = JobStatus.completed.value
            job.progress = 1.0
            job.processed_frames = frame_index
            job.active_module = "Completed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            self._log(db, job_id, f"Completed {frame_index} frames and {len(track_rows)} persistent tracks")
        except Exception as exc:
            LOGGER.exception("Analysis failed")
            db.rollback()
            job = db.get(AnalysisJob, job_id)
            if job:
                job.status = JobStatus.failed.value
                job.error_message = str(exc)
                job.active_module = "Failed"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                self._log(db, job_id, str(exc), "ERROR")
        finally:
            if capture is not None:
                capture.release()
            if writer is not None:
                writer.release()
            db.close()
            self._threads.pop(job_id, None)


pipeline_runtime = PipelineRuntime()
