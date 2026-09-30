"""Composite confidence engine.

The model's self-reported confidence is only one signal. A perfect model answer is
useless if OCR misread the question, so the final score is a weighted geometric
blend of all signals plus hard caps:

* any signal below its floor caps the result (a chain is as strong as its weakest link)
* `uncertain=True` from the model caps at the manual-check threshold
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

DEFAULT_WEIGHTS: dict[str, float] = {
    "model": 0.50,
    "ocr": 0.18,
    "layout": 0.12,
    "image_clarity": 0.08,
    "question_match": 0.07,
    "cache_similarity": 0.05,
}

# signal -> (floor, cap applied when below the floor)
FLOORS: dict[str, tuple[float, float]] = {
    "ocr": (0.55, 0.60),
    "layout": (0.50, 0.60),
    "question_match": (0.80, 0.50),
}


@dataclass(frozen=True, slots=True)
class ConfidenceInputs:
    model: float
    ocr: float = 1.0
    layout: float = 1.0
    image_clarity: float = 1.0
    question_match: float = 1.0
    cache_similarity: float | None = None  # None = not a cache hit, signal ignored
    model_uncertain: bool = False
    has_image: bool = False


@dataclass(frozen=True, slots=True)
class ConfidenceResult:
    value: float
    breakdown: dict[str, float] = field(default_factory=dict)
    capped_by: str | None = None

    def below(self, threshold: float) -> bool:
        return self.value < threshold


def _clamp(x: float) -> float:
    if math.isnan(x):
        return 0.0
    return max(0.0, min(1.0, x))


def composite_confidence(
    inp: ConfidenceInputs,
    manual_threshold: float = 0.75,
    weights: dict[str, float] | None = None,
) -> ConfidenceResult:
    w = dict(weights or DEFAULT_WEIGHTS)
    signals: dict[str, float] = {
        "model": _clamp(inp.model),
        "ocr": _clamp(inp.ocr),
        "layout": _clamp(inp.layout),
        "question_match": _clamp(inp.question_match),
    }
    if inp.has_image:
        signals["image_clarity"] = _clamp(inp.image_clarity)
    if inp.cache_similarity is not None:
        signals["cache_similarity"] = _clamp(inp.cache_similarity)

    total_w = sum(w.get(k, 0.0) for k in signals)
    if total_w <= 0:
        return ConfidenceResult(0.0, signals, "no-weights")
    # weighted geometric mean: one weak signal pulls the score down harder than an arithmetic mean
    log_sum = sum(w.get(k, 0.0) * math.log(max(v, 1e-4)) for k, v in signals.items())
    value = math.exp(log_sum / total_w)

    capped_by = None
    for key, (floor, cap) in FLOORS.items():
        if key in signals and signals[key] < floor and value > cap:
            value, capped_by = cap, key
    # a true cap (min), not "reset when above the threshold": values in [threshold - 0.01, threshold)
    # stayed above the cap, so more model confidence could lower the result (found by hypothesis)
    if inp.model_uncertain and value > manual_threshold - 0.01:
        value, capped_by = manual_threshold - 0.01, "model_uncertain"
    return ConfidenceResult(round(_clamp(value), 4), signals, capped_by)
