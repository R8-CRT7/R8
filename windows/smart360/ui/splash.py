"""Startup diagnostics splash: 360 SMART · Running diagnostics… · Capture ✓ … Ready."""

from __future__ import annotations

import time

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QWidget

from smart360 import TAGLINE, __version__
from smart360.health.diagnostics import CheckResult
from smart360.ui.icons import draw_icon
from smart360.ui.theme import ALIGN_CENTER, ALIGN_LEFT, C, T, font, glass_gradient, pen_color, rim_gradient
from smart360.ui.widgets.pulse import ANALYZING, READY, NeuralPulse

SHOWN = ("Capture", "Vision", "AI", "Cache", "State machine", "Hotkeys")


class StartupSplash(QWidget):
    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.SplashScreen
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(460, 420)
        self.pulse = NeuralPulse(72, parent=self)
        self.pulse.move((self.width() - 72) // 2, 44)
        self.pulse.set_state(ANALYZING)
        self.results: list[CheckResult] = []
        self.revealed = 0
        self.headline = "Running diagnostics…"
        self._timer = QTimer(self, interval=140)
        self._timer.timeout.connect(self._reveal)

    def center(self) -> None:
        scr = QApplication.primaryScreen()
        if scr:
            g = scr.availableGeometry()
            self.move(g.center().x() - self.width() // 2, g.center().y() - self.height() // 2)

    def run(self, results: list[CheckResult]) -> None:
        self.results = [r for r in results if r.name in SHOWN]
        self._timer.start()

    def _reveal(self) -> None:
        self.revealed += 1
        if self.revealed > len(self.results):
            self._timer.stop()
            fails = [r for r in self.results if r.status == "fail"]
            self.headline = "Ready." if not fails else "Ready - with warnings"
            self.pulse.set_state(READY)
        self.update()

    @property
    def done(self) -> bool:
        return self.revealed > len(self.results)

    def wait_done(self, max_s: float = 3.0) -> None:
        end = time.monotonic() + max_s
        app = QApplication.instance()
        while not self.done and time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)
        end = time.monotonic() + 0.45
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)

    def fade_out(self) -> None:
        a = QPropertyAnimation(
            self, b"windowOpacity", self, duration=240, easingCurve=QEasingCurve.Type.InCubic
        )
        a.setStartValue(1.0)
        a.setEndValue(0.0)
        a.finished.connect(self.close)
        a.start()
        self._fade = a

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        path = QPainterPath()
        path.addRoundedRect(r, 24, 24)
        p.fillPath(path, glass_gradient(r.top(), r.bottom(), 248))
        p.setPen(QPen(rim_gradient(r.top(), r.bottom(), 50), 1))
        p.drawPath(path)
        p.setPen(C.TEXT)
        p.setFont(font(24, T.heading().weight(), 1.5))
        p.drawText(QRectF(r.left(), 128, r.width(), 32), ALIGN_CENTER, "360 SMART")
        p.setFont(T.small())
        p.setPen(C.TEXT_2)
        p.drawText(QRectF(r.left(), 160, r.width(), 18), ALIGN_CENTER, f"{TAGLINE}  ·  {__version__}")
        p.setFont(T.caption())
        p.setPen(C.PRIMARY)
        p.drawText(QRectF(r.left(), 196, r.width(), 18), ALIGN_CENTER, self.headline)
        y = 230
        x = r.center().x() - 100
        for i, res in enumerate(self.results[: self.revealed]):
            col = pen_color(res.status)
            p.setFont(T.body_medium())
            p.setPen(C.TEXT)
            p.drawText(QRectF(x, y + i * 26, 160, 20), ALIGN_LEFT, res.name)
            icon = "check" if res.status == "ok" else ("warning" if res.status == "warn" else "close")
            draw_icon(p, icon, QRectF(x + 180, y + i * 26 + 1, 18, 18), col, 2.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(C.PRIMARY)
        _ = QPointF
        p.end()
