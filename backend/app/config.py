from __future__ import annotations

import shutil
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "TrafficVision"
    api_prefix: str = "/api"
    host: str = "127.0.0.1"
    port: int = 8000
    frontend_url: str = "http://127.0.0.1:5173"
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'trafficvision.db').as_posix()}"
    data_dir: Path = PROJECT_ROOT / "data"
    model_dir: Path = PROJECT_ROOT / "models"
    yolo_model: str = "yolo11n.pt"
    plate_ocr_enabled: bool = False
    privacy_acknowledged: bool = False
    performance_profile: str = "CPU Light"
    frame_skip: int = 2
    inference_size: int = 640
    detection_confidence: float = 0.35
    ocr_confidence: float = 0.65
    plate_detector_confidence: float = 0.40
    evidence_seconds_before: float = 4.0
    evidence_seconds_after: float = 6.0
    retention_days: int = 30
    demo_mode: bool = False

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_prefix="TV_", extra="ignore"
    )

    @property
    def ffmpeg_path(self) -> str | None:
        return self._binary("ffmpeg.exe")

    @property
    def ffprobe_path(self) -> str | None:
        return self._binary("ffprobe.exe")

    @staticmethod
    def _binary(filename: str) -> str | None:
        direct = shutil.which(Path(filename).stem)
        if direct:
            return direct
        local = os.environ.get("LOCALAPPDATA")
        if local:
            matches = list((Path(local) / "Microsoft" / "WinGet" / "Packages").glob(f"Gyan.FFmpeg_*/*/bin/{filename}"))
            if matches:
                return str(matches[-1])
        return None

    def ensure_directories(self) -> None:
        for name in (
            "input", "output", "evidence", "plate-crops", "thumbnails", "samples", "temp"
        ):
            (self.data_dir / name).mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
