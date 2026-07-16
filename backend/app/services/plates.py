from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PlateCandidate:
    text: str
    confidence: float
    sharpness: float = 1.0


@dataclass(frozen=True)
class PlateProfile:
    name: str = "Generic Latin / digits"
    allowed_characters: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    minimum_length: int = 4
    maximum_length: int = 12
    pattern: str = ""
    confidence_threshold: float = 0.65


GENERIC_PROFILE = PlateProfile()
ETHIOPIAN_PLACEHOLDER = PlateProfile(
    name="Ethiopian (editable placeholder)",
    allowed_characters="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    pattern="",
)


def normalize_plate(text: str, profile: PlateProfile = GENERIC_PROFILE) -> str:
    allowed = set(profile.allowed_characters.upper())
    return "".join(character for character in text.upper() if character in allowed)


def is_valid_plate(text: str, profile: PlateProfile = GENERIC_PROFILE) -> bool:
    value = normalize_plate(text, profile)
    if not profile.minimum_length <= len(value) <= profile.maximum_length:
        return False
    if profile.pattern and re.fullmatch(profile.pattern, value) is None:
        return False
    return True


def vote_plate_candidates(
    candidates: Iterable[PlateCandidate], profile: PlateProfile = GENERIC_PROFILE
) -> tuple[str, float, list[dict[str, float | str]]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for candidate in candidates:
        normalized = normalize_plate(candidate.text, profile)
        if is_valid_plate(normalized, profile) and 0 <= candidate.confidence <= 1:
            grouped[normalized].append(candidate.confidence * max(0.25, candidate.sharpness))
    if not grouped:
        return "Unreadable", 0.0, []
    ranked = sorted(
        ((text, sum(scores) / max(1.0, len(scores) ** 0.5), len(scores)) for text, scores in grouped.items()),
        key=lambda item: (item[1], item[2]),
        reverse=True,
    )
    total = sum(item[1] for item in ranked) or 1.0
    alternatives = [
        {"text": text, "confidence": round(min(score / total + 0.15 * min(count, 3), 1.0), 3)}
        for text, score, count in ranked[:5]
    ]
    best = alternatives[0]
    confidence = float(best["confidence"])
    if confidence < profile.confidence_threshold or (len(ranked) > 1 and ranked[0][1] < ranked[1][1] * 1.2):
        return "Insufficient confidence", confidence, alternatives
    return str(best["text"]), confidence, alternatives

