from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uid() -> str:
    return str(uuid.uuid4())


class JobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ReviewStatus(str, enum.Enum):
    new = "New"
    under_review = "Under review"
    confirmed = "Confirmed"
    rejected = "Rejected"
    needs_more_evidence = "Needs more evidence"
    false_positive = "False positive"


class Camera(Base):
    __tablename__ = "cameras"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(240), default="Not specified")
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), default="upload")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VideoSource(Base):
    __tablename__ = "video_sources"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    camera_id: Mapped[str | None] = mapped_column(ForeignKey("cameras.id"), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255))
    storage_name: Mapped[str] = mapped_column(String(255), unique=True)
    file_path: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frame_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    codec: Mapped[str | None] = mapped_column(String(60), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(ForeignKey("video_sources.id"))
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.queued.value)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    processed_frames: Mapped[int] = mapped_column(Integer, default=0)
    total_frames: Mapped[int] = mapped_column(Integer, default=0)
    processing_fps: Mapped[float] = mapped_column(Float, default=0.0)
    active_module: Mapped[str] = mapped_column(String(80), default="Queued")
    modules_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_video_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Track(Base):
    __tablename__ = "tracks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("analysis_jobs.id"))
    external_track_id: Mapped[int] = mapped_column(Integer)
    object_class: Mapped[str] = mapped_column(String(60))
    max_confidence: Mapped[float] = mapped_column(Float)
    first_seen_seconds: Mapped[float] = mapped_column(Float)
    last_seen_seconds: Mapped[float] = mapped_column(Float)
    best_speed_kph: Mapped[float | None] = mapped_column(Float, nullable=True)


class TrackPoint(Base):
    __tablename__ = "track_points"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id"))
    timestamp_seconds: Mapped[float] = mapped_column(Float)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    bbox_json: Mapped[list[float]] = mapped_column(JSON)
    speed_kph: Mapped[float | None] = mapped_column(Float, nullable=True)


class PlateRead(Base):
    __tablename__ = "plate_reads"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("analysis_jobs.id"))
    track_id: Mapped[str | None] = mapped_column(ForeignKey("tracks.id"), nullable=True)
    text: Mapped[str] = mapped_column(String(40), default="Unreadable")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(40), default="Unreadable")
    alternatives_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    crop_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at_seconds: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    incident_number: Mapped[str] = mapped_column(String(40), unique=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(30), default="medium")
    confidence: Mapped[float] = mapped_column(Float)
    review_status: Mapped[str] = mapped_column(String(40), default=ReviewStatus.new.value)
    is_simulation: Mapped[bool] = mapped_column(Boolean, default=False)
    track_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    vehicle_class: Mapped[str | None] = mapped_column(String(60), nullable=True)
    plate_text: Mapped[str] = mapped_column(String(40), default="Unreadable")
    plate_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    start_seconds: Mapped[float] = mapped_column(Float)
    peak_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    measurements_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    operator_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class IncidentEvidence(Base):
    __tablename__ = "incident_evidence"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"))
    evidence_type: Mapped[str] = mapped_column(String(40))
    file_path: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class CameraConfiguration(Base):
    __tablename__ = "camera_configurations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    camera_id: Mapped[str | None] = mapped_column(ForeignKey("cameras.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    original_width: Mapped[int] = mapped_column(Integer)
    original_height: Mapped[int] = mapped_column(Integer)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CameraZone(Base):
    __tablename__ = "camera_zones"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    configuration_id: Mapped[str] = mapped_column(ForeignKey("camera_configurations.id"))
    zone_type: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    points_json: Mapped[list[list[float]]] = mapped_column(JSON)
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Lane(Base):
    __tablename__ = "lanes"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    configuration_id: Mapped[str] = mapped_column(ForeignKey("camera_configurations.id"))
    name: Mapped[str] = mapped_column(String(120))
    points_json: Mapped[list[list[float]]] = mapped_column(JSON)
    direction_json: Mapped[list[float]] = mapped_column(JSON, default=lambda: [0, -1])
    lane_type: Mapped[str] = mapped_column(String(40), default="general")


class StopLine(Base):
    __tablename__ = "stop_lines"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    configuration_id: Mapped[str] = mapped_column(ForeignKey("camera_configurations.id"))
    name: Mapped[str] = mapped_column(String(120))
    start_json: Mapped[list[float]] = mapped_column(JSON)
    end_json: Mapped[list[float]] = mapped_column(JSON)


class TrafficLightRegion(Base):
    __tablename__ = "traffic_light_regions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    configuration_id: Mapped[str] = mapped_column(ForeignKey("camera_configurations.id"))
    name: Mapped[str] = mapped_column(String(120))
    points_json: Mapped[list[list[float]]] = mapped_column(JSON)
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Calibration(Base):
    __tablename__ = "calibrations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    configuration_id: Mapped[str] = mapped_column(ForeignKey("camera_configurations.id"))
    method: Mapped[str] = mapped_column(String(40))
    reference_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    speed_region_json: Mapped[list[list[float]]] = mapped_column(JSON, default=list)
    speed_limit_kph: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    calibrated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApplicationSetting(Base):
    __tablename__ = "application_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProcessingLog(Base):
    __tablename__ = "processing_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_jobs.id"), nullable=True)
    level: Mapped[str] = mapped_column(String(20), default="INFO")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

