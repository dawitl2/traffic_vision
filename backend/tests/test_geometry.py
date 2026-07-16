import numpy as np
import pytest

from app.services.geometry import (
    direction_similarity, dwell_time, homography, movement_direction, point_in_polygon,
    segments_cross, transform_point,
)


def test_point_in_polygon_includes_boundary():
    polygon = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon((5, 5), polygon)
    assert point_in_polygon((0, 5), polygon)
    assert not point_in_polygon((11, 5), polygon)


def test_line_crossing_and_direction():
    assert segments_cross((0, 0), (10, 10), (0, 10), (10, 0))
    direction = movement_direction([(1, 1), (1, 9)])
    assert direction == pytest.approx((0, 1))
    assert direction_similarity(direction, (0, -1)) == pytest.approx(-1)


def test_longest_stationary_dwell():
    assert dwell_time([0, 2, 4, 6, 8], [False, True, True, False, True]) == 4


def test_perspective_calibration_maps_points():
    image = [(0, 0), (100, 0), (100, 50), (0, 50)]
    world = [(0, 0), (20, 0), (20, 10), (0, 10)]
    matrix = homography(image, world)
    assert transform_point((50, 25), matrix) == pytest.approx((10, 5), abs=1e-4)
    with pytest.raises(ValueError):
        homography([(0, 0)] * 4, world)

