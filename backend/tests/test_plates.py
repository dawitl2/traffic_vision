from app.services.plates import PlateCandidate, PlateProfile, normalize_plate, vote_plate_candidates


def test_normalizes_generic_plate_without_country_assumption():
    assert normalize_plate(" ab-12 3 ") == "AB123"


def test_multiframe_confidence_weighted_vote():
    values = [
        PlateCandidate("ABC-123", .91, 1.2), PlateCandidate("ABC123", .88, 1.1),
        PlateCandidate("A8C123", .55, .7),
    ]
    text, confidence, alternatives = vote_plate_candidates(values)
    assert text == "ABC123"
    assert confidence >= .65
    assert alternatives[0]["text"] == "ABC123"


def test_unstable_or_invalid_read_is_not_invented():
    profile = PlateProfile(confidence_threshold=.85)
    text, _, _ = vote_plate_candidates([PlateCandidate("AB12", .51), PlateCandidate("XY99", .50)], profile)
    assert text == "Insufficient confidence"
    assert vote_plate_candidates([PlateCandidate("?", .99)])[0] == "Unreadable"

