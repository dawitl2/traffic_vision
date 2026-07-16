from app.services.analysis_modules import CongestionModule, build_modules
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

