from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np


def classify_signal_state(
    frame: np.ndarray, normalized_polygon: Sequence[tuple[float, float]], minimum_color_fraction: float = .01
) -> tuple[str, float]:
    if frame.size == 0 or len(normalized_polygon) < 3:
        return "unknown", 0.0
    height, width = frame.shape[:2]
    polygon = np.asarray([[(int(x * width), int(y * height)) for x, y in normalized_polygon]], dtype=np.int32)
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(mask, polygon, 255)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    valid = mask > 0
    region_size = int(valid.sum())
    if not region_size:
        return "unknown", 0.0
    saturation = hsv[:, :, 1] >= 100
    brightness = hsv[:, :, 2] >= 110
    hue = hsv[:, :, 0]
    common = valid & saturation & brightness
    counts = {
        "red": int((common & ((hue <= 12) | (hue >= 168))).sum()),
        "amber": int((common & (hue >= 15) & (hue <= 38)).sum()),
        "green": int((common & (hue >= 40) & (hue <= 95)).sum()),
    }
    state = max(counts, key=counts.get)
    colored = sum(counts.values())
    fraction = colored / region_size
    if fraction < minimum_color_fraction or counts[state] == 0:
        return "unknown", 0.0
    dominance = counts[state] / colored
    confidence = min(1.0, dominance * min(1.0, fraction / (minimum_color_fraction * 2)))
    return (state, round(confidence, 3)) if confidence >= .65 else ("unknown", round(confidence, 3))


def build_signal_timeline(observations: list[tuple[float, str, float]]) -> list[dict[str, float | str]]:
    known = [item for item in observations if item[1] != "unknown" and item[2] >= .65]
    if not known:
        return []
    timeline: list[dict[str, float | str]] = []
    start, state, confidence = known[0]
    end = start
    scores = [confidence]
    for timestamp, new_state, score in known[1:]:
        if new_state != state or timestamp - end > 1.5:
            timeline.append({"start": start, "end": end, "state": state, "confidence": round(sum(scores) / len(scores), 3)})
            start, state, scores = timestamp, new_state, [score]
        else:
            scores.append(score)
        end = timestamp
    timeline.append({"start": start, "end": end, "state": state, "confidence": round(sum(scores) / len(scores), 3)})
    return timeline

