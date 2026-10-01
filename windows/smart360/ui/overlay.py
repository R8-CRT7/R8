"""Floating AI overlay: FULL, FOCUS and ORBIT modes.

Never steals focus from the learning window (WA_ShowWithoutActivating, Tool window) and
is excluded from screen capture on Windows so it can sit on top of the question area
without polluting OCR.
"""

from __future__ import annotations

import time

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizeGrip, QStackedLayout, QVBoxLayout, QWidget

from smart360.core.models import Prediction, Question
from smart360.platform import win32
from smart360.ui.theme import (
    ALIGN_CENTER,
    ALIGN_LEFT,
    C,
    S,
    T,
    font,
    glass_gradient,
    rim_gradient,
    with_alpha,
)
from smart360.ui.widgets.controls import (
    Chip,
    ConfidenceMeter,
    GlowButton,
    IconButton,
    KeyCap,
    Skeleton,
    caption,
    confidence_color,
    hbox,
    label,
    set_label_color,
    vbox,
)
from smart360.ui.widgets.pulse import (
    CONFIRMED,
    ERROR,
    NeuralPulse,
    state_for_engine,
)

STATE_TITLES = {
    "WAITING_FOR_QUESTION": "WATCHING",
    "CAPTURING": "SCANNING",
    "ANALYZING": "ANALYZING",
    "ANSWER_READY": "ANSWER READY",
    "WAITING_FOR_CONFIRMATION": "QUESTION DETECTED",
    "EXECUTING_CONFIRMED_ACTION": "SELECTING",
    "VERIFYING": "VERIFYING",
    "WAITING_FOR_NEXT_QUESTION": "READY FOR NEXT",
    "PAUSED": "PAUSED",
    "ERROR": "ATTENTION",
}


def answer_text(pred: Prediction | None) -> str:
    if pred is None:
        return "—"
    if pred.number_answer:
        return pred.number_answer
    return "  +  ".join(str(a) for a in pred.answers) if pred.answers else "?"


class _GlassShell(QWidget):
    """Paints the overlay glass body (the window itself is transparent)."""

    def __init__(self, parent: QWidget, radius: float = S.RADIUS_XL):
        super().__init__(parent)
        self.radius = radius
        self.accent: QColor | None = None

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(10, 10, -10, -10)
        rad = min(self.radius, r.height() / 2)
        # soft shadow (painted, cheaper than QGraphicsDropShadowEffect)
        for i in range(10, 0, -2):
            sp = QPainterPath()
            sp.addRoundedRect(r.adjusted(-i * 0.8, -i * 0.4, i * 0.8, i * 1.2), rad + i, rad + i)
            p.fillPath(sp, QColor(0, 0, 0, 7))
        path = QPainterPath()
        path.addRoundedRect(r, rad, rad)
        p.fillPath(path, glass_gradient(r.top(), r.bottom(), 238))
        if self.accent is not None:
            from PySide6.QtGui import QRadialGradient

            g = QRadialGradient(QPointF(r.left() + 30, r.top() + 20), r.width() * 0.9)
            g.setColorAt(0, with_alpha(self.accent, 36))
            g.setColorAt(1, with_alpha(self.accent, 0))
            p.fillPath(path, g)
        p.setPen(QPen(rim_gradient(r.top(), r.bottom(), 46), 1))
        p.drawPath(path)
        p.end()


class OverlayWindow(QWidget):
    confirm = Signal()
    reject = Signal()
    recheck = Signal()
    pause_toggled = Signal()
    emergency_stop = Signal()
    open_dashboard = Signal()
    mode_changed = Signal(str)
    moved = Signal(QPoint)

    FULL_SIZE = QSize(380, 468)
    FOCUS_SIZE = QSize(300, 96)
    ORBIT_SIZE = QSize(84, 84)

    def __init__(self, mode: str = "full", opacity: float = 0.96, pinned: bool = True):
        super().__init__(None)
        self.setWindowTitle("360 SMART Overlay")
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if pinned:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(opacity)
        self.mode = mode
        self.pinned = pinned
        self.threshold = 0.75
        self.state = "WAITING_FOR_QUESTION"
        self.question: Question | None = None
        self.prediction: Prediction | None = None
        self._drag: QPoint | None = None
        self._orbit_expanded = False
        self._flash_until = 0.0
        self.stopped = False
        self.safe_mode = False
        self.dry_run = False

        self.shell = _GlassShell(self)
        self.stack = QStackedLayout(self.shell)
        self.stack.setContentsMargins(10, 10, 10, 10)
        self.full = self._build_full()
        self.focus = self._build_focus()
        self.orbit = self._build_orbit()
        for w in (self.full, self.focus, self.orbit):
            self.stack.addWidget(w)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.shell)
        self._status_timer = QTimer(self, singleShot=True)
        self._status_timer.timeout.connect(self._refresh)
        self.set_mode(mode)
        self._refresh()

    # ================================================================== build
    def _build_full(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(S.XL, S.LG, S.XL, S.LG)
        lay.setSpacing(0)

        # header (drag handle)
        self.f_pulse = NeuralPulse(26)
        brand = label("360 SMART", font(13.5, T.title().weight(), 0.6), C.TEXT)
        self.f_ai = Chip("AI", C.SUCCESS, dot=True)
        self.btn_focus = IconButton("focus", "Focus mode (Ctrl+Shift+M)", 28)
        self.btn_orbit = IconButton("orbit", "Orbit mode", 28)
        self.btn_pin = IconButton("pin", "Pin on top", 28)
        self.btn_pin.setCheckable(True)
        self.btn_pin.setChecked(self.pinned)
        self.btn_dash = IconButton("expand", "Open dashboard", 28)
        self.btn_focus.clicked.connect(lambda: self._switch("focus"))
        self.btn_orbit.clicked.connect(lambda: self._switch("orbit"))
        self.btn_pin.clicked.connect(self._toggle_pin)
        self.btn_dash.clicked.connect(self.open_dashboard.emit)
        header = hbox(
            self.f_pulse,
            brand,
            None,
            self.f_ai,
            6,
            self.btn_focus,
            self.btn_orbit,
            self.btn_pin,
            self.btn_dash,
            spacing=4,
        )
        lay.addLayout(header)
        lay.addSpacing(S.LG)

        self.f_state = caption("WATCHING", C.PRIMARY)
        self.f_question = label("Open a question in 360° online.", T.small(), C.TEXT_2, wrap=True)
        self.f_question.setMaximumHeight(36)
        lay.addWidget(self.f_state)
        lay.addSpacing(6)
        lay.addWidget(self.f_question)
        lay.addSpacing(S.LG)

        lay.addWidget(caption("Recommended"))
        lay.addSpacing(2)
        self.f_answer = label("—", T.hero(), C.TEXT)
        self.f_skel = Skeleton(30, 0.45)
        self.f_skel.hide()
        lay.addWidget(self.f_answer)
        lay.addWidget(self.f_skel)
        self.f_answers_detail = label("", T.small(), C.TEXT_2, wrap=True)
        lay.addWidget(self.f_answers_detail)
        lay.addSpacing(S.MD)

        self.f_conf_label = caption("Confidence")
        self.f_conf_value = label("", T.telemetry(15), C.TEXT)
        self.f_manual = Chip("MANUAL CHECK", C.WARNING)
        self.f_manual.hide()
        lay.addLayout(hbox(self.f_conf_label, None, self.f_manual, 8, self.f_conf_value))
        lay.addSpacing(8)
        self.f_meter = ConfidenceMeter()
        lay.addWidget(self.f_meter)
        lay.addSpacing(S.MD)

        self.f_reason = label("", T.body(), C.TEXT, wrap=True)
        self.f_reason.setMinimumHeight(40)
        self.f_reason.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self.f_reason, 1)
        lay.addSpacing(S.MD)

        self.btn_confirm = GlowButton("CONFIRM", "primary", "check")
        self.btn_recheck = GlowButton("RECHECK", "ghost", "refresh")
        self.btn_confirm.clicked.connect(self.confirm.emit)
        self.btn_recheck.clicked.connect(self.recheck.emit)
        self.btn_resume = GlowButton("RESUME", "primary", "play")
        self.btn_resume.clicked.connect(self.pause_toggled.emit)
        self.btn_resume.hide()
        self.btn_stop = GlowButton("STOP", "danger", "pause")
        self.btn_stop.setToolTip("Emergency stop (Ctrl+Shift+X): stops everything, nothing is clicked")
        self.btn_stop.clicked.connect(self.emergency_stop.emit)
        row = hbox(self.btn_confirm, self.btn_resume, self.btn_recheck, self.btn_stop, spacing=S.SM)
        row.setStretch(0, 3)
        row.setStretch(1, 3)
        row.setStretch(2, 2)
        row.setStretch(3, 2)
        lay.addLayout(row)
        lay.addSpacing(S.MD)
        self.k_enter = KeyCap("ENTER", "Confirm")
        self.k_esc = KeyCap("ESC", "Reject")
        self.k_pause = KeyCap("F8", "Pause")
        self.k_resume = KeyCap("F8", "Resume")
        self.k_resume.hide()
        self.f_keys = hbox(self.k_enter, self.k_esc, None, self.k_pause, self.k_resume, spacing=10)
        lay.addLayout(self.f_keys)
        grip_row = QHBoxLayout()
        grip_row.addStretch(1)
        self.grip = QSizeGrip(w)
        self.grip.setFixedSize(14, 14)
        self.grip.setStyleSheet("background: transparent;")
        grip_row.addWidget(self.grip)
        grip_row.setContentsMargins(0, 0, -14, -8)
        lay.addLayout(grip_row)
        return w

    def _build_focus(self) -> QWidget:
        w = QWidget()
        self.c_pulse = NeuralPulse(42)
        self.c_answer = label("—", font(24, T.title().weight(), -0.5, tabular=True), C.TEXT)
        self.c_conf = label("", T.telemetry(12.5), C.TEXT_2)
        self.c_hint = KeyCap("ENTER ↵")
        self.c_expand = IconButton("expand", "Full overlay", 26)
        self.c_expand.clicked.connect(lambda: self._switch("full"))
        left = vbox(self.c_answer, self.c_conf, spacing=0)
        lay = hbox(
            self.c_pulse,
            6,
            left,
            None,
            self.c_hint,
            self.c_expand,
            spacing=8,
            margins=(S.LG, S.SM, S.MD, S.SM),
        )
        w.setLayout(lay)
        return w

    def _build_orbit(self) -> QWidget:
        w = QWidget()
        self.o_pulse = NeuralPulse(56)
        self.o_bubble = QLabel("", w)
        self.o_bubble.setFont(T.telemetry(12))
        self.o_bubble.hide()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.o_pulse, 0, ALIGN_CENTER)
        w.setToolTip("360 SMART - click to expand")
        return w

    # ================================================================== mode
    def _switch(self, mode: str) -> None:
        self.set_mode(mode)
        self.mode_changed.emit(mode)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        idx = {"full": 0, "focus": 1, "orbit": 2}.get(mode, 0)
        self.stack.setCurrentIndex(idx)
        size = {0: self.FULL_SIZE, 1: self.FOCUS_SIZE, 2: self.ORBIT_SIZE}[idx]
        self.shell.radius = {0: S.RADIUS_XL, 1: 30, 2: 40}[idx]
        if idx == 0:
            self.setMinimumSize(340, 420)
            self.setMaximumSize(640, 900)
        else:
            self.setMinimumSize(size)
            self.setMaximumSize(size)
        self.resize(size)
        self._refresh()

    def cycle_mode(self) -> None:
        self._switch({"full": "focus", "focus": "orbit", "orbit": "full"}[self.mode])

    def _toggle_pin(self) -> None:
        self.set_pinned(self.btn_pin.isChecked())

    def set_pinned(self, pinned: bool) -> None:
        self.pinned = pinned
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, pinned)
        if visible:
            self.show()
            self._apply_native()

    def showEvent(self, e):  # type: ignore[no-untyped-def]
        super().showEvent(e)
        self._apply_native()

    def _apply_native(self) -> None:
        if win32.IS_WINDOWS:
            win32.exclude_from_capture(int(self.winId()))

    # ================================================================== data
    def set_threshold(self, t: float) -> None:
        self.threshold = t
        self.f_meter.threshold = t

    def set_state(self, state: str) -> None:
        self.state = state
        self._refresh()

    def set_question(self, q: Question | None) -> None:
        self.question = q
        if q is None:
            self.prediction = None
        self._refresh()

    def set_prediction(self, p: Prediction | None) -> None:
        self.prediction = p
        self._refresh()

    def set_ai_status(self, text: str, color: QColor) -> None:
        self.f_ai.set(text, color)

    def flash_result(self, ok: bool, message: str, hold_s: float = 1.6) -> None:
        pulse_state = CONFIRMED if ok else ERROR
        for pl in (self.f_pulse, self.c_pulse, self.o_pulse):
            pl.set_state(pulse_state)
        self.f_reason.setText(message)
        set_label_color(self.f_reason, C.SUCCESS if ok else C.ERROR)
        self._flash_until = time.monotonic() + hold_s
        self._status_timer.start(int(hold_s * 1000) + 100)

    def set_safety(self, safe_mode: bool, dry_run: bool) -> None:
        self.safe_mode, self.dry_run = safe_mode, dry_run
        self._refresh()

    def set_stopped(self, stopped: bool) -> None:
        self.stopped = stopped
        if stopped:
            self._flash_until = 0.0
        self._refresh()

    def set_reduce_motion(self, on: bool) -> None:
        for pl in (self.f_pulse, self.c_pulse, self.o_pulse):
            pl.set_reduce_motion(on)

    # ================================================================== render state
    def _refresh(self) -> None:
        if time.monotonic() < self._flash_until:
            return
        st = self.state
        p = self.prediction
        uncertain = bool(p and p.uncertain)
        pulse_state = state_for_engine(st, uncertain)
        for pl in (self.f_pulse, self.c_pulse, self.o_pulse):
            pl.set_state(pulse_state)
        waiting = st == "WAITING_FOR_CONFIRMATION" and p is not None
        analyzing = st in ("CAPTURING", "ANALYZING")

        # ---- full
        title = STATE_TITLES.get(st, st)
        if waiting and uncertain:
            title = "CHECK THIS ONE"
        if self.stopped:
            title = "STOPPED"
        elif self.dry_run:
            title = f"DRY RUN · {title}"
        self.f_state.setText(title)
        state_color = {"ERROR": C.ERROR, "PAUSED": C.TEXT_2}.get(st, C.WARNING if uncertain else C.PRIMARY)
        if self.stopped:
            state_color = C.ERROR
        set_label_color(self.f_state, state_color)
        self.shell.accent = state_color if st in ("ERROR",) or uncertain else (C.PRIMARY if waiting else None)
        q = self.question
        self.f_question.setText(
            _elide(q.text, 150)
            if q
            else "Open a question in 360° online - 360 SMART detects it automatically."
        )
        self.f_answer.setVisible(not analyzing)
        self.f_skel.setVisible(analyzing)
        self.f_answer.setText(answer_text(p) if p else "—")
        set_label_color(self.f_answer, confidence_color(p.confidence, self.threshold) if p else C.TEXT_3)
        if p and q and p.answers:
            parts = []
            for i in p.answers:
                a = q.answer_by_index(i)
                if a:
                    parts.append(f"{i}  {_elide(a.text, 48)}")
            self.f_answers_detail.setText("\n".join(parts))
        else:
            self.f_answers_detail.setText("")
        if p:
            self.f_meter.set_value(p.confidence)
            self.f_conf_value.setText(f"{p.confidence * 100:.0f} %")
            self.f_reason.setText(p.reason)
            set_label_color(self.f_reason, C.TEXT)
        else:
            self.f_meter.set_value(0)
            self.f_conf_value.setText("")
            self.f_reason.setText(
                {
                    "ANALYZING": "Reading the situation and the answers…",
                    "CAPTURING": "Scanning the screen…",
                    "PAUSED": "Paused - nothing is captured or sent.",
                    "ERROR": "",
                }.get(st, "Waiting for the next question.")
            )
            set_label_color(self.f_reason, C.TEXT_2)
        if self.stopped:
            self.f_reason.setText(
                "EMERGENCY STOP - nothing is captured, sent or clicked. Press RESUME (or F8) to continue."
            )
            set_label_color(self.f_reason, C.ERROR)
        self.f_manual.setVisible(waiting and uncertain)
        self.btn_confirm.setEnabled(waiting)
        self.btn_confirm.kind = "warning" if uncertain else "primary"
        if uncertain and self.safe_mode:
            self.btn_confirm.setText("ACCEPT · NO CLICK")
        elif self.dry_run:
            self.btn_confirm.setText("CONFIRM (DRY RUN)")
        else:
            self.btn_confirm.setText("CONFIRM" if not uncertain else "CONFIRM ANYWAY")
        self.btn_confirm.update()
        paused = st == "PAUSED" or self.stopped
        self.btn_confirm.setVisible(not paused)
        self.btn_resume.setVisible(paused)
        self.btn_recheck.setEnabled(st not in ("PAUSED", "EXECUTING_CONFIRMED_ACTION", "VERIFYING"))
        # keyboard hints only for what the keys can do right now (ENTER is off for manual checks)
        self.k_enter.setVisible(waiting and not uncertain)
        self.k_esc.setVisible(waiting)
        self.k_pause.setVisible(not paused)
        self.k_resume.setVisible(paused)

        # ---- focus
        self.c_answer.setText(
            "STOPPED"
            if self.stopped
            else answer_text(p)
            if p
            else {"PAUSED": "Paused", "ERROR": "Attention"}.get(
                st, "Watching" if not analyzing else "Analyzing…"
            )
        )
        set_label_color(self.c_answer, confidence_color(p.confidence, self.threshold) if p else C.TEXT_2)
        self.c_conf.setText(
            f"{p.confidence * 100:.0f} %  ·  {'check' if uncertain else 'ready'}"
            if p
            else STATE_TITLES.get(st, "").title()
        )
        self.c_hint.setVisible(waiting and not uncertain)

        # ---- orbit tooltip
        tip = f"{answer_text(p)}   {p.confidence * 100:.0f} %" if p else STATE_TITLES.get(st, st).title()
        if self.stopped:
            tip = "STOPPED (emergency stop)"
        self.orbit.setToolTip(f"360 SMART · {tip}\nClick to expand")

    # ================================================================== interaction
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._press_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if self._drag is not None:
            moved = (e.globalPosition().toPoint() - self._press_pos).manhattanLength() > 4
            self._drag = None
            if moved:
                self.moved.emit(self.pos())
            elif self.mode == "orbit":
                self._switch("full")

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
        if self.mode == "focus":
            self._switch("full")

    def animate_in(self) -> None:
        self.setWindowOpacity(0.0)
        self.show()
        anim = QPropertyAnimation(
            self, b"windowOpacity", self, duration=260, easingCurve=QEasingCurve.Type.OutCubic
        )
        anim.setStartValue(0.0)
        anim.setEndValue(self._target_opacity if hasattr(self, "_target_opacity") else 0.96)
        anim.start()
        self._fade = anim

    def set_overlay_opacity(self, v: float) -> None:
        self._target_opacity = v
        self.setWindowOpacity(v)


def _elide(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


__all__ = ["ALIGN_LEFT", "OverlayWindow"]
