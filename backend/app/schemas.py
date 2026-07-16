from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    modules: list[str] = Field(default_factory=lambda: [
        "vehicle_counting", "congestion", "collision", "speed", "parking", "wrong_way",
        "red_light", "lane", "intrusion", "hazard",
    ])
    configuration_id: str | None = None
    performance_profile: Literal["CPU Light", "CPU Balanced", "GPU Balanced", "GPU Accuracy"] = "CPU Light"
    frame_skip: int = Field(default=2, ge=1, le=30)
    inference_size: int = Field(default=640, ge=320, le=1280)
    detection_confidence: float = Field(default=0.35, ge=0.05, le=0.95)
    enable_plate_ocr: bool = False
    privacy_acknowledged: bool = False


class IncidentUpdate(BaseModel):
    review_status: Literal[
        "New", "Under review", "Confirmed", "Rejected", "Needs more evidence", "False positive"
    ]
    operator_notes: str = Field(default="", max_length=5000)


class CameraConfigurationInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    camera_id: str | None = None
    original_width: int = Field(gt=0)
    original_height: int = Field(gt=0)
    config: dict[str, Any] = Field(default_factory=dict)


class SettingsUpdate(BaseModel):
    values: dict[str, Any]


class CalibrationInput(BaseModel):
    configuration_id: str
    method: Literal["measured_reference", "perspective"]
    reference: dict[str, Any]
    speed_region: list[list[float]] = Field(default_factory=list)
    speed_limit_kph: float = Field(gt=0, le=250)
    confidence: float = Field(ge=0, le=1)


class CameraInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: str = Field(default="Not specified", max_length=240)
    source_type: Literal["webcam", "rtsp", "http", "upload"] = "upload"
    source_uri: str | None = Field(default=None, max_length=2048)
    enabled: bool = True
