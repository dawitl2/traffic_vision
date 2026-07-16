from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import cv2

from ..config import get_settings


def _ratio(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        numerator, denominator = value.split("/")
        return float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        return None


def probe_video(path: Path) -> dict[str, Any]:
    settings = get_settings()
    if settings.ffprobe_path:
        command = [
            settings.ffprobe_path, "-v", "error", "-show_streams", "-show_format",
            "-of", "json", str(path),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=True)
            payload = json.loads(completed.stdout)
            video = next((stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"), {})
            fps = _ratio(video.get("avg_frame_rate")) or _ratio(video.get("r_frame_rate"))
            duration = video.get("duration") or payload.get("format", {}).get("duration")
            frames = video.get("nb_frames")
            return {
                "width": int(video.get("width") or 0), "height": int(video.get("height") or 0),
                "fps": fps, "duration_seconds": float(duration) if duration else None,
                "frame_count": int(frames) if frames and str(frames).isdigit() else None,
                "codec": video.get("codec_name"), "format": payload.get("format", {}).get("format_name"),
                "variable_frame_rate": video.get("avg_frame_rate") != video.get("r_frame_rate"),
                "probe": "ffprobe",
            }
        except (subprocess.SubprocessError, ValueError, json.JSONDecodeError):
            pass
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError("The uploaded file is not a readable video")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS)) or None
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or None
        return {
            "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": fps, "frame_count": frames,
            "duration_seconds": frames / fps if frames and fps else None,
            "codec": None, "format": path.suffix.lstrip("."), "variable_frame_rate": None,
            "probe": "opencv-fallback",
        }
    finally:
        capture.release()

