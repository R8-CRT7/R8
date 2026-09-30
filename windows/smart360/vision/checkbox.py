"""Checkbox state reading for execution + verification."""

from __future__ import annotations

import numpy as np
from PIL import Image

from smart360.core.models import Question, Rect


def interior_darkness(frame: Image.Image, frame_rect: Rect, box: Rect) -> float:
    """Mean darkness (0..255) of the inner 50% of a checkbox (screen coordinates)."""
    x = box.x - frame_rect.x + box.w // 4
    y = box.y - frame_rect.y + box.h // 4
    w, h = max(2, box.w // 2), max(2, box.h // 2)
    crop = frame.crop((max(0, x), max(0, y), max(1, x + w), max(1, y + h))).convert("L")
    a = np.asarray(crop, dtype=np.float32)
    return float(255.0 - a.mean()) if a.size else 0.0


def checkbox_states(frame: Image.Image, frame_rect: Rect, q: Question) -> dict[int, bool] | None:
    """Returns {answer_index: checked} or None if the states cannot be told apart reliably."""
    values = {a.index: interior_darkness(frame, frame_rect, a.checkbox) for a in q.answers if a.checkbox}
    if not values:
        return None
    lo, hi = min(values.values()), max(values.values())
    if hi - lo < 25:
        # all look the same: either all unchecked (common) or unreadable
        if hi < 40:
            return {k: False for k in values}
        return None
    cut = lo + (hi - lo) / 2
    return {k: v > cut for k, v in values.items()}
