"""NEURAL PULSE - the signature element of 360 SMART.

A small orb (+ optional neural waveform) that visualises the assistant state:

IDLE        slow breathing
CAPTURE     short scan ring
ANALYZING   travelling neural wave, orbiting arcs
READY       calm steady glow
UNCERTAIN   amber glow (manual check)
CONFIRMED   green burst, then settles
ERROR       brief red distortion
PAUSED      desaturated, still

Subtle by design: low amplitudes, no RGB cycling. Animation stops when hidden.
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QSizePolicy, QWidget

from smart360.ui.theme import C, with_alpha

IDLE, CAPTURE, ANALYZING, READY, UNCERTAIN, CONFIRMED, ERROR, PAUSED = (
    "idle",
    "capture",
    "analyzing",
    "ready",
    "uncertain",
    "confirmed",
    "error",
    "paused",
)

_STATE_COLORS = {
    IDLE: (C.PRIMARY, C.SECONDARY),
    CAPTURE: (C.PRIMARY, C.PRIMARY),
    ANALYZING: (C.PRIMARY, C.SECONDARY),
    READY: (C.PRIMARY, QColor("#5FE3FF")),
    UNCERTAIN: (C.WARNING, QColor("#FF8A47")),
    CONFIRMED: (C.SUCCESS, QColor("#2BD4A0")),
    ERROR: (C.ERROR, QColor("#FF3B7F")),
    PAUSED: (QColor("#6B7785"), QColor("#4A5561")),
}


def state_for_engine(state: str, uncertain: bool = False) -> str:
    return {
        "WAITING_FOR_QUESTION": IDLE,
        "WAITING_FOR_NEXT_QUESTION": IDLE,
        "CAPTURING": CAPTURE,
        "ANALYZING": ANALYZING,
        "ANSWER_READY": UNCERTAIN if uncertain else READY,
        "WAITING_FOR_CONFIRMATION": UNCERTAIN if uncertain else READY,
        "EXECUTING_CONFIRMED_ACTION": ANALYZING,
        "VERIFYING": ANALYZING,
        "PAUSED": PAUSED,
        "ERROR": ERROR,
    }.get(state, IDLE)


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
        round(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


class NeuralPulse(QWidget):
    def __init__(self, size: int = 48, wave: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self._size = size
        self.wave = wave
        self.state = IDLE
        self._state_t = time.monotonic()
        self._t0 = time.monotonic()
        self._from = _STATE_COLORS[IDLE]
        self._to = _STATE_COLORS[IDLE]
        self.reduce_motion = False
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self.update)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if wave:
            self.setMinimumSize(size * 3, size)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        else:
            self.setFixedSize(size, size)

    def sizeHint(self) -> QSize:
        return QSize(self._size * (4 if self.wave else 1), self._size)

    # ------------------------------------------------------------------ state
    def set_state(self, state: str) -> None:
        if state == self.state:
            return
        self._from = self._current_colors()
        self._to = _STATE_COLORS.get(state, _STATE_COLORS[IDLE])
        self.state = state
        self._state_t = time.monotonic()
        self._retime()
        self.update()

    def set_reduce_motion(self, on: bool) -> None:
        self.reduce_motion = on
        self._retime()

    def _retime(self) -> None:
        if not self.isVisible():
            return
        if self.reduce_motion or self.state == PAUSED:
            self._timer.start(250)  # only colour transitions
        elif self.state in (IDLE, READY):
            self._timer.start(33)  # 30 fps is plenty for slow breathing
        else:
            self._timer.start(16)

    def showEvent(self, e):  # type: ignore[no-untyped-def]
        self._retime()
        super().showEvent(e)

    def hideEvent(self, e):  # type: ignore[no-untyped-def]
        self._timer.stop()
        super().hideEvent(e)

    def _current_colors(self) -> tuple[QColor, QColor]:
        k = min(1.0, (time.monotonic() - self._state_t) / 0.45)
        return (_mix(self._from[0], self._to[0], k), _mix(self._from[1], self._to[1], k))

    # ------------------------------------------------------------------ paint
    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        now = time.monotonic()
        t = 0.0 if self.reduce_motion else now - self._t0
        since = now - self._state_t
        c1, c2 = self._current_colors()

        h = self.height()
        r = h * 0.26
        cx = h / 2
        cy = h / 2

        # --- state-specific motion parameters
        breathe = 0.5 + 0.5 * math.sin(t * 1.6)
        halo_scale, halo_alpha, jitter = 1.0, 70, 0.0
        if self.state == IDLE:
            halo_scale, halo_alpha = 0.95 + 0.12 * breathe, 45 + int(35 * breathe)
        elif self.state in (READY, UNCERTAIN):
            halo_scale, halo_alpha = 1.05 + 0.05 * breathe, 90 + int(20 * breathe)
        elif self.state == ANALYZING:
            halo_scale, halo_alpha = 1.1 + 0.08 * math.sin(t * 5), 95
        elif self.state == CONFIRMED:
            k = min(1.0, since / 0.8)
            halo_scale, halo_alpha = 1.0 + 0.5 * (1 - k), 120
        elif self.state == ERROR and since < 0.55 and not self.reduce_motion:
            jitter = math.sin(since * 90) * 2.2 * (1 - since / 0.55)
        elif self.state == PAUSED:
            halo_alpha = 25
        cx += jitter

        # --- waveform (line mode)
        if self.wave and self.width() > h * 1.5:
            self._paint_wave(p, h, t, c1, c2)

        # --- halo
        halo = QRadialGradient(QPointF(cx, cy), r * 2.0 * halo_scale)
        halo.setColorAt(0.0, with_alpha(c1, halo_alpha))
        halo.setColorAt(0.45, with_alpha(c2, halo_alpha // 3))
        halo.setColorAt(1.0, with_alpha(c2, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QPointF(cx, cy), r * 2.0 * halo_scale, r * 2.0 * halo_scale)

        # --- scan ring / confirm burst
        if self.state in (CAPTURE, CONFIRMED) and not self.reduce_motion:
            period = 0.9
            k = (since % period) / period if self.state == CAPTURE else min(1.0, since / 0.9)
            if self.state == CAPTURE or since < 0.9:
                ring_r = r * (1.0 + 1.3 * k)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(with_alpha(c1, int(200 * (1 - k))), max(1.0, h * 0.03)))
                p.drawEllipse(QPointF(cx, cy), ring_r, ring_r)

        # --- orbiting arcs while analyzing
        if self.state == ANALYZING and not self.reduce_motion:
            p.setBrush(Qt.BrushStyle.NoBrush)
            for i, (speed, span, rr) in enumerate(((140, 70, 1.45), (-95, 110, 1.7), (60, 40, 1.95))):
                pen = QPen(with_alpha(c1 if i != 1 else c2, 170 - i * 40), max(1.0, h * 0.025))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                rect = QRectF(cx - r * rr, cy - r * rr, r * rr * 2, r * rr * 2)
                p.drawArc(rect, int((t * speed + i * 120) * 16), int(span * 16))

        # --- core orb
        core = QRadialGradient(QPointF(cx - r * 0.35, cy - r * 0.4), r * 1.35)
        core.setColorAt(0.0, QColor(255, 255, 255, 235))
        core.setColorAt(0.28, c1)
        core.setColorAt(1.0, _mix(c2, QColor(8, 12, 18), 0.35))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(core)
        wobble = 1.0 + (0.035 * math.sin(t * 7) if self.state == ANALYZING and not self.reduce_motion else 0)
        p.drawEllipse(QPointF(cx, cy), r * wobble, r * wobble)
        # inner rim highlight
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.drawEllipse(QPointF(cx, cy), r * wobble - 0.5, r * wobble - 0.5)
        p.end()

    def _paint_wave(self, p: QPainter, h: float, t: float, c1: QColor, c2: QColor) -> None:
        x0 = h * 1.05
        x1 = self.width() - 4
        cy = h / 2
        amp = {
            IDLE: 0.06,
            READY: 0.05,
            UNCERTAIN: 0.08,
            ANALYZING: 0.28,
            CAPTURE: 0.18,
            CONFIRMED: 0.12,
            ERROR: 0.22,
            PAUSED: 0.0,
        }.get(self.state, 0.05) * h
        if self.reduce_motion:
            amp *= 0.3
        path = QPainterPath()
        steps = max(24, int((x1 - x0) / 3))
        for i in range(steps + 1):
            u = i / steps
            x = x0 + (x1 - x0) * u
            env = math.sin(math.pi * u) ** 1.5  # fade at both ends
            y = cy + amp * env * (
                math.sin(u * 14 - t * 3.2) * 0.6
                + math.sin(u * 31 + t * 5.1) * 0.25
                + math.sin(u * 6 - t * 1.3) * 0.4
            )
            if self.state == ERROR and time.monotonic() - self._state_t < 0.5:
                y += math.sin(u * 90 + t * 60) * h * 0.04
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        from PySide6.QtGui import QLinearGradient

        g = QLinearGradient(x0, 0, x1, 0)
        g.setColorAt(0, with_alpha(c1, 0))
        g.setColorAt(0.25, with_alpha(c1, 200))
        g.setColorAt(0.75, with_alpha(c2, 160))
        g.setColorAt(1, with_alpha(c2, 0))
        pen = QPen(g, max(1.2, h * 0.035))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        # faint echo line
        p.setPen(QPen(with_alpha(c2, 45), 1))
        p.translate(0, h * 0.06)
        p.drawPath(path)
        p.translate(0, -h * 0.06)
