from types import SimpleNamespace

from app.services.analysis_modules import CongestionModule, build_modules
from app.services.evaluation import collision_contact_metrics
from app.services.incidents import IncidentCandidate, suppress_duplicates


def test_all_ten_modules_are_independently_registered():
    registry = build_modules()
    assert set(registry) == {
        "collision", "congestion", "vehicle_counting", "speed", "parking", "wrong_way",
        "red_light", "lane", "intrusion", "hazard",
    }
    assert all(module.title and module.model_status for module in registry.values())


def test_congestion_scoring():
    score, label = CongestionModule.score(vehicle_count=18, stationary_count=16, region_capacity=20)
    assert score > .85
    assert label == "Gridlocked"
    assert CongestionModule.score(1, 0, 20)[1] == "Free flowing"


def test_duplicate_incidents_keep_stronger_candidate():
    values = [
        IncidentCandidate("Possible speeding", (7,), 10, .7),
        IncidentCandidate("Possible speeding", (7,), 13, .91),
        IncidentCandidate("Possible speeding", (8,), 13, .8),
    ]
    result = suppress_duplicates(values)
    assert len(result) == 2
    assert result[0].confidence == .91


def _point(timestamp, x, y, width=.12, height=.1):
    return SimpleNamespace(
        timestamp_seconds=timestamp, x=x, y=y,
        bbox_json=[x - width / 2, y - height / 2, x + width / 2, y + height / 2],
    )


def test_collision_requires_contact_approach_and_motion_anomaly():
    first = [
        _point(0, .20, .50), _point(.2, .26, .50), _point(.4, .32, .50),
        _point(.6, .38, .50), _point(.8, .44, .50), _point(1.0, .50, .50),
        _point(1.2, .50, .56), _point(1.4, .50, .62),
    ]
    second = [
        _point(0, .80, .50), _point(.2, .75, .50), _point(.4, .70, .50),
        _point(.6, .65, .50), _point(.8, .60, .50), _point(1.0, .54, .50),
        _point(1.2, .54, .50), _point(1.4, .54, .50),
    ]
    evidence = collision_contact_metrics(first, second)
    assert evidence is not None
    assert evidence["direction_change"] or evidence["speed_drop"]


def test_parallel_nearby_traffic_is_not_a_collision():
    first = [_point(index / 5, .2 + index * .04, .45) for index in range(8)]
    second = [_point(index / 5, .2 + index * .04, .60) for index in range(8)]
    assert collision_contact_metrics(first, second) is None
