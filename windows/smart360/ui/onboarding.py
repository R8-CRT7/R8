"""First-run experience: Welcome → Choose AI → Detection → Calibration → Test → Ready."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLineEdit, QWidget

from smart360.ai.registry import PROVIDERS
from smart360.health.diagnostics import run_self_test
from smart360.health.monitor import Health
from smart360.ui.pages.base import UiContext
from smart360.ui.pages.settings import PROVIDER_BLURB, ProviderCard
from smart360.ui.theme import ALIGN_CENTER, C, S, T, font, paint_canvas, pen_color, rim_gradient, with_alpha
from smart360.ui.widgets.controls import (
    Chip,
    FadeStack,
    GlowButton,
    KeyCap,
    caption,
    clear_layout,
    hbox,
    label,
    set_label_color,
    vbox,
)
from smart360.ui.widgets.pulse import IDLE, READY, NeuralPulse

STEP_NAMES = ("Choose AI", "Detection", "Calibration", "Test", "Ready")


class Progress(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.step = 0
        self.setFixedHeight(36)

    def set_step(self, i: int) -> None:
        self.step = i
        self.update()

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = len(STEP_NAMES)
        w = self.width() / n
        p.setFont(T.caption())
        for i, name in enumerate(STEP_NAMES):
            x = i * w
            done, cur = i < self.step, i == self.step
            col = C.PRIMARY if (done or cur) else QColor(255, 255, 255, 40)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(x + 4, 4, w - 8, 3), 1.5, 1.5)
            p.setPen(C.TEXT if cur else (C.TEXT_2 if done else C.TEXT_3))
            p.drawText(QRectF(x, 12, w, 20), ALIGN_CENTER, name)
        p.end()


class Onboarding(QWidget):
    finished = Signal()
    request_calibration = Signal()
    demo_chosen = Signal(bool)

    def __init__(self, ctx: UiContext):
        super().__init__(None)
        self.ctx = ctx
        self.setWindowTitle("Welcome to 360 SMART")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setFixedSize(820, 600)
        self.stack = FadeStack()
        self.progress = Progress()
        self.btn_back = GlowButton("Back", "ghost")
        self.btn_next = GlowButton("Continue", "primary", "chevron")
        self.btn_skip = GlowButton("Skip setup", "subtle", compact=True)
        self.btn_back.clicked.connect(self.back)
        self.btn_next.clicked.connect(self.next)
        self.btn_skip.clicked.connect(self._finish)
        self.nav = hbox(self.btn_skip, None, self.btn_back, self.btn_next, spacing=S.SM)
        self.pages = [
            self._welcome(),
            self._ai(),
            self._detection(),
            self._calibration(),
            self._test(),
            self._ready(),
        ]
        for pg in self.pages:
            self.stack.addWidget(pg)
        root = vbox(self.progress, 8, self.stack, self.nav, spacing=S.MD, margins=(S.XXL, S.XL, S.XXL, S.XL))
        self.setLayout(root)
        self.index = 0
        self._poll = QTimer(self, interval=800)
        self._poll.timeout.connect(self._poll_detection)
        self._sync()

    # ------------------------------------------------------------------ pages
    def _welcome(self) -> QWidget:
        w = QWidget()
        self.w_pulse = NeuralPulse(120)
        self.w_pulse.set_state(IDLE)
        t = label("360 SMART", font(40, T.display().weight(), 2.0), C.TEXT)
        s = label("Your intelligent theory companion.", T.title(), C.TEXT_2)
        d = label(
            "Reads the question on screen, explains the rule and recommends an answer - and only ever "
            "acts after you confirm.",
            T.body(),
            C.TEXT_3,
            wrap=True,
        )
        d.setFixedWidth(460)  # fixed width -> correct height-for-width when centered
        for x in (t, s, d):
            x.setAlignment(ALIGN_CENTER)
        lay = vbox(None, spacing=S.MD)
        lay.addWidget(self.w_pulse, 0, ALIGN_CENTER)
        lay.addSpacing(S.LG)
        for x in (t, s, d):
            lay.addWidget(x, 0, ALIGN_CENTER)
        lay.addStretch(1)
        w.setLayout(lay)
        return w

    def _ai(self) -> QWidget:
        w = QWidget()
        lay = vbox(
            label("Choose your AI", T.display()),
            label(
                "Bring your own API key - it is stored in the Windows Credential Manager. Or start with the free "
                "offline demo.",
                T.body(),
                C.TEXT_2,
                wrap=True,
            ),
            spacing=S.SM,
        )
        cards = hbox(spacing=S.MD)
        self.ai_cards: dict[str, ProviderCard] = {}
        for pid, cls in PROVIDERS.items():
            c = ProviderCard(pid, cls.info.display_name, PROVIDER_BLURB.get(pid, ""))
            c.clicked.connect(lambda _c=False, x=pid: self._pick(x))
            self.ai_cards[pid] = c
            cards.addWidget(c)
        lay.addSpacing(S.MD)
        lay.addLayout(cards)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("API key")
        self.key_hint = label("", T.small(), C.TEXT_3, wrap=True)
        lay.addSpacing(S.MD)
        lay.addWidget(self.key)
        lay.addWidget(self.key_hint)
        lay.addStretch(1)
        w.setLayout(lay)
        self._pick(self.ctx.services.config.ai.provider if not self.ctx.services.config.demo_mode else "mock")
        return w

    def _pick(self, pid: str) -> None:
        self.provider = pid
        for k, c in self.ai_cards.items():
            c.setChecked(k == pid)
            c.status = "SELECTED" if k == pid else ""
            c.update()
        info = PROVIDERS[pid].info
        self.key.setVisible(bool(info.key_name))
        existing = self.ctx.services.secrets.get(info.key_name) if info.key_name else None
        self.key.setPlaceholderText(f"{info.key_name}  ·  already set" if existing else f"{info.key_name}")
        self.key_hint.setText(
            "Demo mode uses a built-in practice simulator - perfect to try everything for free."
            if pid == "mock"
            else "Costs are billed by the provider per request. The cache and "
            "cost saver keep it low; usage is estimated locally on the AI page."
        )

    def _detection(self) -> QWidget:
        w = QWidget()
        self.det_pulse = NeuralPulse(56, wave=True)
        self.det_status = label("Looking for 360° online…", T.heading())
        self.det_detail = label("", T.body(), C.TEXT_2, wrap=True)
        self.det_ocr = Chip("OCR", C.TEXT_3, dot=True)
        tips = label(
            "Open 360° online in Edge or Chrome (or the desktop app) and log in. 360 SMART finds the "
            "window by its title. You can edit the patterns later under Detection.",
            T.small(),
            C.TEXT_3,
            wrap=True,
        )
        w.setLayout(
            vbox(
                label("Detection", T.display()),
                label("Let's find your learning window.", T.body(), C.TEXT_2),
                S.LG,
                self.det_pulse,
                S.MD,
                self.det_status,
                self.det_detail,
                hbox(self.det_ocr, None),
                S.LG,
                tips,
                None,
                spacing=S.SM,
            )
        )
        return w

    def _calibration(self) -> QWidget:
        w = QWidget()
        self.cal_status = label("", T.body(), C.TEXT_2, wrap=True)
        btn = GlowButton("Calibrate now", "primary", "detection")
        btn.clicked.connect(self.request_calibration.emit)
        steps = vbox(spacing=6)
        for i, (t, d) in enumerate(
            (
                ("Question area", "where the question text is"),
                ("Answers area", "checkboxes + answer texts"),
                ("Image & action", "optional"),
                ("Test", "live detection check"),
                ("Save", "as Laptop / Desktop / Fullscreen"),
            )
        ):
            steps.addLayout(
                hbox(
                    label(str(i + 1), T.telemetry(14), C.PRIMARY),
                    label(t, T.body_medium()),
                    label(d, T.small(), C.TEXT_3),
                    None,
                    spacing=S.MD,
                )
            )
        w.setLayout(
            vbox(
                label("Calibration", T.display()),
                label(
                    "Tell 360 SMART once where question and answers are. Regions are stored relative to the window, so "
                    "moving and resizing keeps working.",
                    T.body(),
                    C.TEXT_2,
                    wrap=True,
                ),
                S.LG,
                steps,
                S.LG,
                hbox(btn, None),
                self.cal_status,
                None,
                spacing=S.SM,
            )
        )
        return w

    def _test(self) -> QWidget:
        w = QWidget()
        self.test_box = vbox(spacing=6)
        w.setLayout(
            vbox(
                label("System test", T.display()),
                label("Checking everything before your first session.", T.body(), C.TEXT_2),
                S.LG,
                self.test_box,
                None,
                spacing=S.SM,
            )
        )
        return w

    def _ready(self) -> QWidget:
        w = QWidget()
        self.r_pulse = NeuralPulse(96)
        self.r_pulse.set_state(READY)
        t = label("You're ready.", T.display())
        t.setAlignment(ALIGN_CENTER)
        s = label("360 SMART watches for questions. You decide.", T.body(), C.TEXT_2)
        s.setAlignment(ALIGN_CENTER)
        keys = hbox(
            None,
            KeyCap("ENTER", "Confirm"),
            KeyCap("ESC", "Reject"),
            KeyCap("F8", "Pause"),
            KeyCap("F9", "Recheck"),
            KeyCap("Ctrl+Shift+M", "Mode"),
            None,
            spacing=14,
        )
        lay = vbox(None, spacing=S.MD)
        lay.addWidget(self.r_pulse, 0, ALIGN_CENTER)
        lay.addWidget(t, 0, ALIGN_CENTER)
        lay.addWidget(s, 0, ALIGN_CENTER)
        lay.addSpacing(S.LG)
        lay.addLayout(keys)
        lay.addStretch(1)
        w.setLayout(lay)
        return w

    # ------------------------------------------------------------------ flow
    def _sync(self) -> None:
        self.stack.fade_to(self.index)
        self.progress.setVisible(self.index > 0)
        self.progress.set_step(self.index - 1)
        self.btn_back.setVisible(self.index > 0)
        last = self.index == len(self.pages) - 1
        self.btn_next.setText({0: "Get started"}.get(self.index, "Start 360 SMART" if last else "Continue"))
        self.btn_next.updateGeometry()
        self.btn_skip.setVisible(not last)
        if self.index == 2:
            self._poll.start()
            self._poll_detection()
        else:
            self._poll.stop()
        if self.index == 3:
            self.update_calibration_status()
        if self.index == 4:
            self._run_test()

    def next(self) -> None:
        if self.index == 1:
            self._apply_ai()
        if self.index == len(self.pages) - 1:
            self._finish()
            return
        self.index += 1
        self._sync()

    def back(self) -> None:
        self.index = max(0, self.index - 1)
        self._sync()

    def _apply_ai(self) -> None:
        svc = self.ctx.services
        demo = self.provider == "mock"
        if not demo:
            info = PROVIDERS[self.provider].info
            if self.key.text().strip():
                svc.secrets.set(info.key_name, self.key.text().strip())
                self.key.clear()
            svc.store.update(ai={"provider": self.provider, "model": ""})
        if demo != svc.config.demo_mode:
            svc.store.update(demo_mode=demo)
            self.demo_chosen.emit(demo)
        else:
            self.ctx.apply_engine_config()

    def _poll_detection(self) -> None:
        svc = self.ctx.services
        cap = svc.health.components["Capture"]
        ok = cap.state is Health.HEALTHY
        eng = svc.engine
        self.det_pulse.set_state(READY if ok else IDLE)
        self.det_status.setText("Connected" if ok else "Looking for 360° online…")
        set_label_color(self.det_status, C.SUCCESS if ok else C.TEXT)
        self.det_detail.setText(eng.target.describe() if (ok and eng) else (cap.detail or "Not found yet."))
        self.det_ocr.set(f"OCR · {svc.ocr.name}", C.SUCCESS if svc.ocr.available() else C.WARNING)

    def update_calibration_status(self) -> None:
        svc = self.ctx.services
        n = len(svc.config.detection.profiles)
        if svc.config.demo_mode:
            self.cal_status.setText("Demo mode uses the simulator profile automatically - you can skip this.")
            set_label_color(self.cal_status, C.SUCCESS)
        elif n:
            self.cal_status.setText(f"✓ {n} profile(s) saved.")
            set_label_color(self.cal_status, C.SUCCESS)
        else:
            self.cal_status.setText("No profile yet.")
            set_label_color(self.cal_status, C.TEXT_3)

    def _run_test(self) -> None:
        clear_layout(self.test_box)
        for r in run_self_test(self.ctx.services):
            self.test_box.addLayout(
                hbox(
                    Chip(r.status.upper(), pen_color(r.status), dot=True),
                    label(r.name, T.body_medium()),
                    label(r.detail, T.small(), C.TEXT_2),
                    None,
                )
            )

    def _finish(self) -> None:
        self.ctx.services.store.update(first_run_done=True)
        self._poll.stop()
        self.finished.emit()
        self.close()

    # ------------------------------------------------------------------ paint / drag
    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_canvas(p, self.rect())
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRect(r)
        p.setPen(QPen(rim_gradient(r.top(), r.bottom(), 30), 1))
        p.drawPath(path)
        _ = (QPointF, with_alpha, caption)
        p.end()

    def mousePressEvent(self, e):  # type: ignore[no-untyped-def]
        h = self.windowHandle()
        if h is not None:
            h.startSystemMove()
