"""Change detection + adaptive polling.

The AI is only called when the visible question actually changed. We compare a tiny
grayscale signature of the question+answers band (cheap: ~1 ms) and require the new
screen to be *stable* for a moment (animations / page transitions settle) before a
capture is triggered.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from smart360.core.imaging import mean_abs_diff, region_signature


@dataclass
class PollingPolicy:
    fast_s: float = 0.15  # right after a change, while waiting for stability
    normal_s: float = 0.35
    idle_s: float = 1.2  # nothing changed for a while
    idle_after_s: float = 20.0


class ChangeDetector:
    def __init__(self, threshold: float = 3.0, stable_frames: int = 2, policy: PollingPolicy | None = None):
        self.threshold = threshold
        self.stable_frames = stable_frames
        self.policy = policy or PollingPolicy()
        self._baseline: np.ndarray | None = None  # signature of the last *processed* screen
        self._candidate: np.ndarray | None = None
        self._stable_count = 0
        self._last_change_t = 0.0

    def reset(self) -> None:
        self._baseline = None
        self._candidate = None
        self._stable_count = 0

    def mark_processed(self, img: Image.Image) -> None:
        self._baseline = region_signature(img)
        self._candidate = None
        self._stable_count = 0

    def observe(self, img: Image.Image, now: float) -> bool:
        """Returns True exactly once per settled change (or for the very first frame)."""
        sig = region_signature(img)
        if self._baseline is not None and mean_abs_diff(sig, self._baseline) < self.threshold:
            self._candidate = None
            self._stable_count = 0
            return False
        self._last_change_t = now
        if self._candidate is not None and mean_abs_diff(sig, self._candidate) < self.threshold:
            self._stable_count += 1
        else:
            self._candidate = sig
            self._stable_count = 1
        return self._stable_count >= self.stable_frames

    def next_interval(self, now: float) -> float:
        if self._candidate is not None:
            return self.policy.fast_s
        if now - self._last_change_t > self.policy.idle_after_s:
            return self.policy.idle_s
        return self.policy.normal_s
