import cv2
import numpy as np

from app.services.signal import build_signal_timeline, classify_signal_state


def test_signal_state_requires_dominant_colored_region():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.circle(frame, (50, 50), 16, (0, 0, 255), -1)
    state, confidence = classify_signal_state(frame, [(.25, .25), (.75, .25), (.75, .75), (.25, .75)])
    assert state == "red"
    assert confidence >= .65
    assert classify_signal_state(np.zeros_like(frame), [(.25, .25), (.75, .25), (.75, .75), (.25, .75)])[0] == "unknown"


def test_signal_timeline_groups_stable_observations():
    result = build_signal_timeline([(0, "red", .9), (.5, "red", .8), (1, "unknown", 0), (2, "green", .9)])
    assert [item["state"] for item in result] == ["red", "green"]

