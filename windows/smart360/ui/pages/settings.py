"""AI, Detection, Appearance and Settings pages."""

from __future__ import annotations

import threading

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSlider,
    QSpinBox,
    QWidget,
)

from smart360 import TAGLINE, __version__
from smart360.ai.registry import PROVIDERS
from smart360.ai.schema import SolveRequest
from smart360.health.monitor import Health
from smart360.ui.pages.base import Page, UiContext
from smart360.ui.theme import ALIGN_LEFT, C, S, T, glass_gradient, with_alpha
from smart360.ui.widgets.controls import (
    Chip,
    Divider,
    GlowButton,
    KeyCap,
    SegmentedControl,
    SettingRow,
    Toggle,
    caption,
    clear_layout,
    hbox,
    label,
    set_label_color,
    vbox,
)

PROVIDER_BLURB = {
    "anthropic": "Claude · vision + strict JSON",
    "openai": "GPT · structured outputs",
    "gemini": "Gemini · fast multimodal",
    "mock": "Offline demo · free, simulator only",
}


class ProviderCard(QAbstractButton):
    def __init__(self, pid: str, name: str, blurb: str):
        super().__init__()
        self.pid, self.name, self.blurb = pid, name, blurb
        self.status = ""
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(104)

    def sizeHint(self) -> QSize:
        return QSize(200, 104)

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, 14, 14)
        p.fillPath(path, glass_gradient(r.top(), r.bottom(), 215))
        on = self.isChecked()
        if on:
            p.fillPath(path, with_alpha(C.PRIMARY, 26))
        p.setPen(QPen(with_alpha(C.PRIMARY, 200) if on else QColor(255, 255, 255, 30), 1.4 if on else 1))
        p.drawPath(path)
        p.setFont(T.title())
        p.setPen(C.TEXT)
        p.drawText(QRectF(r.left() + 16, r.top() + 14, r.width() - 32, 22), ALIGN_LEFT, self.name)
        p.setFont(T.small())
        p.setPen(C.TEXT_2)
        p.drawText(
            QRectF(r.left() + 16, r.top() + 38, r.width() - 32, 34),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),
            self.blurb,
        )
        p.setFont(T.caption())
        p.setPen(C.SUCCESS if ("READY" in self.status or "SELECTED" in self.status) else C.TEXT_3)
        p.drawText(QRectF(r.left() + 16, r.bottom() - 26, r.width() - 32, 16), ALIGN_LEFT, self.status)
        p.end()


def slider(lo: int, hi: int, value: int) -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(lo, hi)
    s.setValue(value)
    s.setFixedWidth(220)
    return s


class AIPage(Page):
    title = "AI"
    subtitle = "Provider, model and how much the AI may cost you."
    test_done = Signal(str, bool)

    def __init__(self, ctx: UiContext):
        super().__init__(ctx)
        cfg = ctx.services.config.ai
        self.cards: dict[str, ProviderCard] = {}
        g = self.grid()
        for i, (pid, cls) in enumerate(PROVIDERS.items()):
            card = ProviderCard(pid, cls.info.display_name, PROVIDER_BLURB.get(pid, ""))
            card.clicked.connect(lambda _c=False, x=pid: self._set_provider(x))
            self.cards[pid] = card
            g.addWidget(card, 0, i)
        self.body.addLayout(g)

        conn = self.section("Connection")
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setMinimumWidth(260)
        self.model.currentTextChanged.connect(self._model_changed)
        conn.lay.addWidget(SettingRow("Model", "Default is the provider's recommended model.", self.model))
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Paste API key")
        self.key.setMinimumWidth(260)
        self.key_save = GlowButton("Save key", "ghost", "key", compact=True)
        self.key_save.clicked.connect(self._save_key)
        self.key_status = label("", T.small(), C.TEXT_3)
        key_row = QWidget()
        key_row.setLayout(hbox(self.key, self.key_save))
        conn.lay.addWidget(
            SettingRow(
                "API key", "Stored in the Windows Credential Manager - never in files or logs.", key_row
            )
        )
        conn.lay.addWidget(self.key_status)
        self.test_btn = GlowButton("Test connection", "ghost", "bolt", compact=True)
        self.test_btn.clicked.connect(self._test)
        self.test_lbl = label("Sends one small text-only request.", T.small(), C.TEXT_3)
        conn.lay.addLayout(hbox(self.test_btn, self.test_lbl, None))
        self.test_done.connect(self._test_result)

        beh = self.section("Behaviour")
        self.thr = slider(50, 95, int(cfg.confidence_threshold * 100))
        self.thr_lbl = label("", T.telemetry(13), C.TEXT)
        self.thr.valueChanged.connect(lambda v: self.thr_lbl.setText(f"{v} %"))
        self.thr.sliderReleased.connect(lambda: self._save(confidence_threshold=self.thr.value() / 100))
        self.thr_lbl.setText(f"{self.thr.value()} %")
        thr_w = QWidget()
        thr_w.setLayout(hbox(self.thr, self.thr_lbl))
        beh.lay.addWidget(
            SettingRow(
                "Confidence threshold",
                "Below this the answer is flagged MANUAL CHECK and ENTER is disabled.",
                thr_w,
            )
        )
        self.timeout = QSpinBox()
        self.timeout.setRange(5, 120)
        self.timeout.setSuffix(" s")
        self.timeout.setValue(int(cfg.timeout_s))
        self.timeout.valueChanged.connect(lambda v: self._save(timeout_s=float(v)))
        beh.lay.addWidget(
            SettingRow("Timeout", "Per request. Slow answers are cancelled and retried.", self.timeout)
        )
        self.retries = QSpinBox()
        self.retries.setRange(0, 5)
        self.retries.setValue(cfg.retries)
        self.retries.valueChanged.connect(lambda v: self._save(retries=v))
        beh.lay.addWidget(
            SettingRow(
                "Retries", "With exponential backoff; a circuit breaker stops retry storms.", self.retries
            )
        )
        self.effort = SegmentedControl(
            [("low", "Fast"), ("medium", "Balanced"), ("high", "Thorough")], cfg.effort
        )
        self.effort.changed.connect(lambda v: self._save(effort=v))
        beh.lay.addWidget(
            SettingRow(
                "Reasoning effort", "Claude only. Fast is usually enough for theory questions.", self.effort
            )
        )

        cost = self.section("Cost saver")
        self.saver = Toggle(cfg.cost_saver)
        self.saver.toggled.connect(lambda v: self._save(cost_saver=v))
        cost.lay.addWidget(
            SettingRow(
                "Cost saver",
                "Cache first, OCR text first, images only when needed, duplicate requests merged.",
                self.saver,
            )
        )
        self.quality = SegmentedControl(
            [("low", "Low"), ("balanced", "Balanced"), ("high", "High")], cfg.vision_quality
        )
        self.quality.changed.connect(lambda v: self._save(vision_quality=v))
        cost.lay.addWidget(SettingRow("Vision quality", "Image resolution sent to the model.", self.quality))
        cost.lay.addWidget(Divider())
        self.usage = label("", T.telemetry(13), C.TEXT_2, wrap=True)
        cost.lay.addWidget(caption("Local usage estimate (no telemetry)"))
        cost.lay.addWidget(self.usage)
        self.body.addStretch(1)
        self._sync()

    # ------------------------------------------------------------------ logic
    def _save(self, **ai) -> None:  # type: ignore[no-untyped-def]
        try:
            self.ctx.services.store.update(ai=ai)
        except Exception as e:
            self.ctx.toast(f"Invalid setting: {e}", "error")
            return
        self.ctx.apply_engine_config()

    def _set_provider(self, pid: str) -> None:
        self._save(provider=pid, model="")
        self._sync()

    def _model_changed(self, text: str) -> None:
        if getattr(self, "_syncing", False):
            return
        cls = PROVIDERS[self.ctx.services.config.ai.provider]
        self._save(model="" if text == cls.info.default_model else text.strip())

    def _save_key(self) -> None:
        cls = PROVIDERS[self.ctx.services.config.ai.provider]
        value = self.key.text().strip()
        if not value or not cls.info.key_name:
            return
        secure = self.ctx.services.secrets.set(cls.info.key_name, value)
        self.key.clear()
        self.ctx.toast(
            "API key saved securely" if secure else "Key kept in memory only (no secure store)",
            "success" if secure else "warning",
        )
        self.ctx.apply_engine_config()
        self._sync()

    def _test(self) -> None:
        solver = self.ctx.services.solver
        if solver is None:
            self.test_lbl.setText("No provider configured (API key missing?)")
            set_label_color(self.test_lbl, C.WARNING)
            return
        self.test_btn.setEnabled(False)
        self.test_lbl.setText("Testing…")
        set_label_color(self.test_lbl, C.TEXT_2)

        def run() -> None:
            try:
                res = solver.solve(
                    SolveRequest("Test: Welche Farbe hat ein Stoppschild?", ("Rot", "Blau", "Grün"))
                )
                self.test_done.emit(
                    f"OK · {res.model} · {res.latency_ms / 1000:.1f} s · answer {res.response.answers}", True
                )
            except Exception as e:
                self.test_done.emit(f"Failed: {e}", False)

        threading.Thread(target=run, name="ai-test", daemon=True).start()

    def _test_result(self, text: str, ok: bool) -> None:
        self.test_btn.setEnabled(True)
        self.test_lbl.setText(text)
        set_label_color(self.test_lbl, C.SUCCESS if ok else C.ERROR)

    def _sync(self) -> None:
        self._syncing = True
        svc = self.ctx.services
        cfg = svc.config.ai
        for pid, card in self.cards.items():
            card.setChecked(pid == cfg.provider)
            info = PROVIDERS[pid].info
            if pid == "mock":
                card.status = "READY"
            else:
                card.status = "READY · KEY SET" if svc.secrets.get(info.key_name) else "NO KEY"
            card.update()
        info = PROVIDERS[cfg.provider].info
        self.model.clear()
        self.model.addItems(list(info.models))
        self.model.setCurrentText(cfg.model or info.default_model)
        has_key = info.key_name and svc.secrets.get(info.key_name)
        where = svc.secrets.backend_label
        self.key_status.setText(
            f"{info.key_name}: {svc.secrets.mask(svc.secrets.get(info.key_name))}  ·  store: {where}"
            if info.key_name
            else "No key needed."
        )
        set_label_color(self.key_status, C.SUCCESS if has_key or not info.key_name else C.WARNING)
        self.key.setEnabled(bool(info.key_name))
        self.key_save.setEnabled(bool(info.key_name))
        self.effort.setEnabled(cfg.provider == "anthropic")
        self._syncing = False

    def refresh(self) -> None:
        solver = self.ctx.services.solver
        if solver is None:
            self.usage.setText("No active provider.")
            return
        c = solver.costs.snapshot()
        pricing = bool(solver.provider.info.pricing.get(solver.provider.model))
        cost = f"≈ ${c['estimated_usd']:.4f}" if pricing else "price table not verified for this provider"
        self.usage.setText(
            f"Requests {c['requests']:.0f}   ·   failed {c['failures']:.0f}   ·   tokens in {c['input_tokens']:.0f} / "
            f"out {c['output_tokens']:.0f}   ·   {cost}   ·   breaker {solver.breaker.state.value}"
        )


class DetectionPage(Page):
    title = "Detection"
    subtitle = "How 360 SMART finds the learning window and reads questions."

    def __init__(self, ctx: UiContext):
        super().__init__(ctx)
        d = ctx.services.config.detection
        win = self.section("Learning window")
        self.win_status = label("", T.title())
        self.win_detail = label("", T.small(), C.TEXT_2)
        win.lay.addLayout(hbox(vbox(self.win_status, self.win_detail, spacing=2), None))
        self.patterns = QPlainTextEdit("\n".join(d.title_patterns))
        self.patterns.setFixedHeight(96)
        self.patterns.setFont(T.telemetry(12))
        save_p = GlowButton("Save patterns", "ghost", compact=True)
        save_p.clicked.connect(self._save_patterns)
        win.lay.addWidget(caption("Window title patterns (regex, one per line)"))
        win.lay.addWidget(self.patterns)
        win.lay.addLayout(hbox(None, save_p))

        prof = self.section(
            "Layout profiles",
            "Regions are stored relative to the window, so moving or resizing "
            "keeps working. Several profiles (laptop, desktop, fullscreen) are chosen automatically.",
        )
        self.active = QComboBox()
        self.active.currentIndexChanged.connect(self._active_changed)
        prof.lay.addWidget(
            SettingRow("Active profile", "Automatic picks the closest window size.", self.active)
        )
        self.prof_box = vbox(spacing=4)
        prof.lay.addLayout(self.prof_box)
        cal = GlowButton("Calibrate new profile", "primary", "detection")
        cal.clicked.connect(ctx.open_calibration)
        prof.lay.addLayout(hbox(None, cal))

        ocr = self.section("Recognition")
        self.ocr = SegmentedControl(
            [("auto", "Automatic"), ("windows", "Windows OCR"), ("tesseract", "Tesseract")], d.ocr_backend
        )
        self.ocr.changed.connect(self._ocr_changed)
        ocr.lay.addWidget(
            SettingRow("OCR engine", "Windows OCR is built in and fast; Tesseract is the fallback.", self.ocr)
        )
        self.ocr_status = label("", T.small(), C.TEXT_3)
        ocr.lay.addWidget(self.ocr_status)
        self.sens = slider(5, 100, int(d.change_threshold * 10))
        self.sens.sliderReleased.connect(lambda: self._save(change_threshold=self.sens.value() / 10))
        ocr.lay.addWidget(
            SettingRow("Change sensitivity", "Lower = reacts to smaller screen changes.", self.sens)
        )
        self.body.addStretch(1)
        self._sync_profiles()

    def _save(self, **det) -> None:  # type: ignore[no-untyped-def]
        try:
            self.ctx.services.store.update(detection=det)
        except Exception as e:
            self.ctx.toast(f"Invalid setting: {e}", "error")
            return
        self.ctx.apply_engine_config()

    def _save_patterns(self) -> None:
        import re

        pats = [x.strip() for x in self.patterns.toPlainText().splitlines() if x.strip()]
        try:
            for x in pats:
                re.compile(x)
        except re.error as e:
            self.ctx.toast(f"Invalid pattern: {e}", "error")
            return
        self._save(title_patterns=pats)
        eng = self.ctx.services.engine
        if eng is not None and hasattr(eng.target, "patterns"):
            eng.target.patterns = tuple(pats)
            eng.target.hwnd = None
        self.ctx.toast("Patterns saved", "success")

    def _ocr_changed(self, v: str) -> None:
        from smart360.vision.ocr import select_backend

        self._save(ocr_backend=v)
        svc = self.ctx.services
        svc.ocr = select_backend(v)
        if svc.engine:
            svc.engine.extractor.ocr = svc.ocr
        svc.health.set(
            "Vision", Health.HEALTHY if svc.ocr.available() else Health.DEGRADED, f"OCR: {svc.ocr.name}"
        )

    def _active_changed(self, _i: int) -> None:
        if getattr(self, "_syncing", False):
            return
        self._save(active_profile=self.active.currentData() or "")

    def _delete_profile(self, name: str) -> None:
        profs = [p for p in self.ctx.services.config.detection.profiles if p.get("name") != name]
        active = self.ctx.services.config.detection.active_profile
        self._save(profiles=profs, active_profile="" if active == name else active)
        self._sync_profiles()

    def _sync_profiles(self) -> None:
        self._syncing = True
        d = self.ctx.services.config.detection
        self.active.clear()
        self.active.addItem("Automatic", "")
        clear_layout(self.prof_box)
        for pr in d.profiles:
            name = pr.get("name", "?")
            self.active.addItem(name, name)
            row = QWidget()
            dl = GlowButton("", "subtle", "trash", compact=True)
            dl.setToolTip("Delete profile")
            dl.clicked.connect(lambda _c=False, n=name: self._delete_profile(n))
            row.setLayout(
                hbox(
                    label(name, T.body_medium()),
                    label(f"{pr.get('ref_width')}×{pr.get('ref_height')}", T.telemetry(12), C.TEXT_3),
                    None,
                    dl,
                )
            )
            self.prof_box.addWidget(row)
        if not d.profiles:
            hint = (
                "Demo mode uses the built-in simulator profile."
                if self.ctx.services.config.demo_mode
                else "No profile yet - calibrate once so 360 SMART knows where question and answers are."
            )
            self.prof_box.addWidget(
                label(
                    hint,
                    T.small(),
                    C.WARNING if not self.ctx.services.config.demo_mode else C.TEXT_2,
                    wrap=True,
                )
            )
        idx = self.active.findData(d.active_profile)
        self.active.setCurrentIndex(max(0, idx))
        self._syncing = False

    def refresh(self) -> None:
        eng = self.ctx.services.engine
        svc = self.ctx.services
        cap = svc.health.components["Capture"]
        if eng is None:
            return
        found = cap.state is Health.HEALTHY
        self.win_status.setText(("Connected · " + eng.target.describe()) if found else "Not connected")
        set_label_color(self.win_status, C.SUCCESS if found else C.WARNING)
        self.win_detail.setText(cap.detail or "Open 360° online in your browser.")
        self.ocr_status.setText(f"Active: {svc.ocr.name}" + ("" if svc.ocr.available() else " (unavailable)"))
        if self.prof_box.count() != max(1, len(svc.config.detection.profiles)):
            self._sync_profiles()


class AppearancePage(Page):
    title = "Appearance"
    subtitle = "Make the overlay yours."

    def __init__(self, ctx: UiContext):
        super().__init__(ctx)
        a = ctx.services.config.appearance
        ov = self.section("Overlay")
        self.mode = SegmentedControl(
            [("full", "Full"), ("focus", "Focus"), ("orbit", "Orbit")], a.overlay_mode
        )
        self.mode.changed.connect(lambda v: self._save(overlay_mode=v))
        ov.lay.addWidget(
            SettingRow(
                "Mode", "Full: everything. Focus: answer + confidence. Orbit: a single AI orb.", self.mode
            )
        )
        self.opacity = slider(35, 100, int(a.overlay_opacity * 100))
        self.opacity.valueChanged.connect(lambda v: self._save(overlay_opacity=v / 100))
        ov.lay.addWidget(SettingRow("Opacity", "", self.opacity))
        self.pinned = Toggle(a.overlay_pinned)
        self.pinned.toggled.connect(lambda v: self._save(overlay_pinned=v))
        ov.lay.addWidget(
            SettingRow("Always on top", "Keep the overlay above the learning window.", self.pinned)
        )

        fx = self.section("Motion & sound")
        self.motion = Toggle(a.reduce_motion)
        self.motion.toggled.connect(lambda v: self._save(reduce_motion=v))
        fx.lay.addWidget(
            SettingRow("Reduce motion", "Calmer Neural Pulse and no page transitions.", self.motion)
        )
        self.sounds = Toggle(a.sounds)
        self.sounds.toggled.connect(lambda v: self._save(sounds=v))
        fx.lay.addWidget(
            SettingRow("Subtle sounds", "Answer ready, confirm and error. Off by default.", self.sounds)
        )
        self.backdrop = Toggle(a.system_backdrop)
        self.backdrop.toggled.connect(lambda v: self._save(system_backdrop=v))
        fx.lay.addWidget(
            SettingRow(
                "Windows 11 backdrop", "Use the system acrylic material for the dashboard.", self.backdrop
            )
        )
        self.body.addStretch(1)

    def _save(self, **app) -> None:  # type: ignore[no-untyped-def]
        try:
            self.ctx.services.store.update(appearance=app)
        except Exception as e:
            self.ctx.toast(f"Invalid setting: {e}", "error")
            return
        self.ctx.apply_appearance()


class SettingsPage(Page):
    title = "Settings"
    subtitle = "General, controls, privacy and experimental features."

    def __init__(self, ctx: UiContext):
        super().__init__(ctx)
        c = ctx.services.config
        gen = self.section("General")
        self.demo = Toggle(c.demo_mode)
        self.demo.toggled.connect(self._demo)
        gen.lay.addWidget(
            SettingRow("Demo mode", "Practise with the built-in simulator - free and offline.", self.demo)
        )

        ctl = self.section("Controls")
        keys = [
            ("confirm", "Confirm"),
            ("reject", "Reject"),
            ("pause", "Pause / resume"),
            ("reanalyze", "Reanalyze"),
            ("mini_mode", "Cycle overlay mode"),
            ("quit", "Quit"),
        ]
        g = self.grid(S.SM)
        for i, (k, text) in enumerate(keys):
            g.addWidget(KeyCap(getattr(c.controls, k)), i // 2, (i % 2) * 2)
            g.addWidget(label(text, T.body(), C.TEXT_2), i // 2, (i % 2) * 2 + 1)
        ctl.lay.addLayout(g)
        ctl.lay.addWidget(
            label(
                "ENTER and ESC are registered globally only while a question awaits your "
                "confirmation, so they never block Enter in other apps.",
                T.small(),
                C.TEXT_3,
                wrap=True,
            )
        )
        self.global_hk = Toggle(c.controls.global_hotkeys)
        self.global_hk.toggled.connect(lambda v: self._save("controls", global_hotkeys=v))
        ctl.lay.addWidget(
            SettingRow("Global hotkeys", "Work while the browser has focus (Windows).", self.global_hk)
        )
        self.execute = Toggle(c.controls.execute_on_confirm)
        self.execute.toggled.connect(lambda v: self._save("controls", execute_on_confirm=v))
        ctl.lay.addWidget(
            SettingRow(
                "Select confirmed answer for me",
                "After YOUR confirmation 360 SMART re-checks the question and clicks the "
                "boxes. Off = advisory only.",
                self.execute,
            )
        )

        pr = self.section(
            "Privacy", "Screenshots are ephemeral: kept in memory only and discarded after analysis."
        )
        self.debug = Toggle(c.privacy.debug_screenshots)
        self.debug.toggled.connect(lambda v: self._save("privacy", debug_screenshots=v))
        pr.lay.addWidget(
            SettingRow(
                "Debug screenshots", "Keeps the last 50 frames locally for troubleshooting.", self.debug
            )
        )
        self.store_text = Toggle(c.privacy.store_question_text)
        self.store_text.toggled.connect(lambda v: self._save("privacy", store_question_text=v))
        pr.lay.addWidget(
            SettingRow("Store question text in history", "Needed for search and insights.", self.store_text)
        )
        self.ret = QSpinBox()
        self.ret.setRange(1, 3650)
        self.ret.setSuffix(" days")
        self.ret.setValue(c.privacy.history_retention_days)
        self.ret.valueChanged.connect(lambda v: self._save("privacy", history_retention_days=v))
        pr.lay.addWidget(SettingRow("Keep history for", "", self.ret))
        clear_h = GlowButton("Clear history", "ghost", "trash", compact=True)
        clear_c = GlowButton("Clear question cache", "ghost", "trash", compact=True)
        clear_h.clicked.connect(self._clear_history)
        clear_c.clicked.connect(self._clear_cache)
        pr.lay.addLayout(hbox(None, clear_h, clear_c))

        fl = self.section(
            "Experimental", "Feature flags - production behaviour stays stable when these are off."
        )
        for key, title, desc in (
            ("orbit_mode", "Orbit mode", "The minimal AI-orb overlay."),
            (
                "auto_advance",
                "Auto-advance",
                "Click the 'next' button after a verified answer (needs an action area).",
            ),
            (
                "number_input",
                "Type number answers",
                "Enter numbers for 'Zahl eingeben' questions after confirmation.",
            ),
        ):
            t = Toggle(getattr(c.flags, key))
            t.toggled.connect(lambda v, k=key: self._save("flags", **{k: v}))
            row = SettingRow(title, desc, t)
            fl.lay.addWidget(row)

        ab = self.section("About")
        ab.lay.addWidget(label(f"360 SMART {__version__}", T.title()))
        ab.lay.addWidget(label(TAGLINE, T.body(), C.TEXT_2))
        ab.lay.addWidget(
            label(
                "A study companion for the 360° online learning software. It explains its recommendations so you "
                "learn the rule - it cannot be used in the official theory exam, and it never acts without your "
                "confirmation. Not affiliated with DEGENER Verlag.",
                T.small(),
                C.TEXT_3,
                wrap=True,
            )
        )
        ab.lay.addWidget(
            label(
                "Open source: Qt for Python (LGPLv3), Inter typeface (SIL OFL 1.1), Pillow, NumPy, "
                "RapidFuzz, mss, pydantic, keyring, psutil (MIT/BSD), Anthropic SDK (MIT).",
                T.small(),
                C.TEXT_3,
                wrap=True,
            )
        )
        self.body.addStretch(1)

    def _save(self, section: str, **values) -> None:  # type: ignore[no-untyped-def]
        try:
            self.ctx.services.store.update(**{section: values})
        except Exception as e:
            self.ctx.toast(f"Invalid setting: {e}", "error")
            return
        self.ctx.apply_engine_config()
        if section == "controls":
            self.ctx.extra.get("sync_hotkeys", lambda: None)()

    def _demo(self, on: bool) -> None:
        self.ctx.services.store.update(demo_mode=on)
        self.ctx.extra.get("rebuild_engine", lambda: None)()
        self.ctx.toast("Demo mode on - simulator window opened" if on else "Demo mode off", "info")

    def _confirm(self, text: str) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle("360 SMART")
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _clear_history(self) -> None:
        if self._confirm("Delete the whole history? This cannot be undone."):
            self.ctx.services.history.clear()
            self.ctx.toast("History cleared", "success")

    def _clear_cache(self) -> None:
        if self._confirm("Clear the question cache? Future questions will be sent to the AI again."):
            self.ctx.services.cache.clear()
            self.ctx.toast("Cache cleared", "success")


__all__ = ["AIPage", "AppearancePage", "Chip", "DetectionPage", "SettingsPage"]
