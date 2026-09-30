"""Capture targets: *where* to capture (window client area) and *how* (grabber)."""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod

from PIL import Image

from smart360.capture.simulator import PracticeSimulator
from smart360.core.models import Rect
from smart360.platform import win32


class CaptureError(RuntimeError):
    pass


class TargetLost(CaptureError):
    """The target window is closed/minimized/not found."""


class CaptureTarget(ABC):
    name = "target"

    @abstractmethod
    def locate(self) -> Rect:
        """Client area in screen coordinates. Raises TargetLost."""

    @abstractmethod
    def grab(self, rect: Rect) -> Image.Image:
        """Capture an absolute screen rect. Raises CaptureError."""

    def describe(self) -> str:
        return self.name


class MssGrabber:
    """mss is not thread-safe: one instance per thread."""

    def __init__(self) -> None:
        self._local = threading.local()

    def grab(self, rect: Rect) -> Image.Image:
        import mss

        sct = getattr(self._local, "sct", None)
        if sct is None:
            sct = mss.mss()
            self._local.sct = sct
        try:
            shot = sct.grab({"left": rect.x, "top": rect.y, "width": rect.w, "height": rect.h})
        except Exception as e:  # mss raises ScreenShotError
            self._local.sct = None
            raise CaptureError(f"screenshot failed: {e}") from e
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


class WindowTarget(CaptureTarget):
    """Tracks the 360° learning window (browser tab / desktop app) by HWND, re-detecting
    it when it is closed and reopened."""

    name = "window"

    def __init__(
        self,
        title_patterns: tuple[str, ...] = win32.DEFAULT_TITLE_PATTERNS,
        grabber: MssGrabber | None = None,
    ):
        self.patterns = title_patterns
        self.grabber = grabber or MssGrabber()
        self.hwnd: int | None = None
        self.title = ""
        self._last_search = 0.0

    def locate(self) -> Rect:
        if not win32.IS_WINDOWS:
            raise TargetLost("window capture requires Windows")
        if self.hwnd is None or not win32.is_window(self.hwnd):
            now = time.monotonic()
            if now - self._last_search < 1.0:
                raise TargetLost("learning window not found")
            self._last_search = now
            info = win32.find_learning_window(self.patterns)
            if info is None:
                self.hwnd = None
                raise TargetLost("learning window not found")
            self.hwnd, self.title = info.hwnd, info.title
        rect = win32.client_rect(self.hwnd)
        info = win32.window_info(self.hwnd)
        if rect is None or info is None or info.minimized:
            raise TargetLost("learning window minimized")
        return rect

    def grab(self, rect: Rect) -> Image.Image:
        return self.grabber.grab(rect)

    def describe(self) -> str:
        return self.title or "not found"


class RegionTarget(CaptureTarget):
    """Fixed screen region (fallback when the window cannot be detected)."""

    name = "region"

    def __init__(self, rect: Rect, grabber: MssGrabber | None = None):
        self.rect = rect
        self.grabber = grabber or MssGrabber()

    def locate(self) -> Rect:
        return self.rect

    def grab(self, rect: Rect) -> Image.Image:
        return self.grabber.grab(rect)


class SimulatorTarget(CaptureTarget):
    """Captures the built-in practice simulator (demo mode and tests)."""

    name = "simulator"

    def __init__(self, sim: PracticeSimulator):
        self.sim = sim
        self.fail_next = 0  # chaos hook: number of upcoming grabs that fail

    def locate(self) -> Rect:
        if not self.sim.visible:
            raise TargetLost("simulator hidden")
        return self.sim.rect

    def grab(self, rect: Rect) -> Image.Image:
        if self.fail_next > 0:
            self.fail_next -= 1
            raise CaptureError("simulated screenshot failure")
        sim_rect = self.sim.rect
        frame = self.sim.render()
        local = (
            rect.x - sim_rect.x,
            rect.y - sim_rect.y,
            rect.x - sim_rect.x + rect.w,
            rect.y - sim_rect.y + rect.h,
        )
        return frame.crop(local)

    def describe(self) -> str:
        return "Practice simulator"
