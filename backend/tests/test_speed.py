import pytest

from app.services.speed import estimate_segment_speeds, reference_scale, robust_speed_kph


def test_speed_uses_distance_and_time_not_plate_text():
    speeds = estimate_segment_speeds([(0, 0), (10, 0), (20, 0)], [0, 1, 2])
    assert speeds == pytest.approx([36, 36])
    assert robust_speed_kph(speeds) == 36


def test_speed_rejects_outlier_and_bad_reference():
    assert robust_speed_kph([40, 41, 39, 200]) < 50
    assert reference_scale(10, 100) == .1
    with pytest.raises(ValueError):
        reference_scale(10, 0)

