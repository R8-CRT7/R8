"""360 SMART application entry point and controller."""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from smart360 import APP_NAME, __version__


def setup_logging(debug: bool) -> None:
    from smart360.storage import paths
    from smart360.storage.secrets import RedactingFilter

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(threadName)-10s %(name)s: %(message)s")
    fh = logging.handlers.RotatingFileHandler(
        paths.log_dir() / "360smart.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    fh.addFilter(RedactingFilter())
    root.addHandler(fh)
    if debug:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        sh.addFilter(RedactingFilter())
        root.addHandler(sh)


class AppController:
    """Owns the windows and wires services <-> UI. Lives on the UI thread."""

    def __init__(self, app, services, demo_window: bool = True):  # type: ignore[no-untyped-def]
        from PySide6.QtCore import QTimer

        from smart360.platform import win32
        from smart360.ui.bridge import EngineBridge
        from smart360.ui.dashboard import Dashboard
        from smart360.ui.overlay import OverlayWindow
        from smart360.ui.pages.base import UiContext
        from smart360.ui.sound import SoundBoard

        self.app = app
        self.svc = services
        self.win32 = win32
        self.bridge = EngineBridge()
        self.sounds = SoundBoard()
        self.ctx = UiContext(
            services,
            self.bridge,
            open_calibration=self.open_calibration,
            apply_appearance=self.apply_appearance,
            apply_engine_config=self.apply_engine_config,
            toast=self.toast,
        )
        self.ctx.extra["rebuild_engine"] = self.rebuild_engine
        self.ctx.extra["sync_hotkeys"] = self.sync_hotkeys
        a = services.config.appearance
        self.overlay = OverlayWindow(
            a.overlay_mode if services.config.flags.orbit_mode or a.overlay_mode != "orbit" else "full",
            a.overlay_opacity,
            a.overlay_pinned,
        )
        self.overlay.set_overlay_opacity(a.overlay_opacity)
        self.dashboard = Dashboard(self.ctx)
        self.sim_window: QWidget | None = None
        self.demo_window = demo_window
        self._wire()
        self.hotkeys = win32.GlobalHotkeys(self.bridge.hotkey.emit) if win32.IS_WINDOWS else None
        self._lag_last = time.perf_counter()
        self._lag = QTimer(interval=250)
        self._lag.timeout.connect(self._measure_lag)
        self._lag.start()
        self._last_state = ""

    # ------------------------------------------------------------------ wiring
    def _wire(self) -> None:
        b, ov = self.bridge, self.overlay
        b.state.connect(self._on_state)
        b.question.connect(ov.set_question)
        b.prediction.connect(self._on_prediction)
        b.execution.connect(self._on_execution)
        b.error.connect(lambda m, k: self.sounds.play("error"))
        b.hotkey.connect(self.on_hotkey)
        ov.confirm.connect(self.confirm)
        ov.reject.connect(self.reject)
        ov.recheck.connect(lambda: self.svc.engine and self.svc.engine.reanalyze())
        ov.pause_toggled.connect(lambda: self.svc.engine and self.svc.engine.toggle_pause())
        ov.open_dashboard.connect(self.show_dashboard)
        ov.mode_changed.connect(lambda m: self.svc.store.update(appearance={"overlay_mode": m}))
        ov.moved.connect(lambda pt: self.svc.store.update(appearance={"overlay_pos": [pt.x(), pt.y()]}))
        self.dashboard.overlay_toggle.connect(self.toggle_overlay)
        self._install_shortcuts()

    def _install_shortcuts(self) -> None:
        """In-app shortcuts (all platforms). Global hotkeys are added on Windows."""
        from PySide6.QtGui import QKeySequence, QShortcut

        c = self.svc.config.controls
        for widget in (self.dashboard, self.overlay):
            for seq, action in (
                (c.pause, "pause"),
                (c.reanalyze, "reanalyze"),
                (c.mini_mode, "mini_mode"),
                (c.quit, "quit"),
            ):
                sc = QShortcut(QKeySequence(seq.replace("CTRL", "Ctrl").replace("SHIFT", "Shift")), widget)
                sc.activated.connect(lambda a=action: self.on_hotkey(a))
        for seq, action in (("Return", "confirm"), ("Escape", "reject")):
            sc = QShortcut(QKeySequence(seq), self.overlay)
            sc.activated.connect(lambda a=action: self.on_hotkey(a))

    # ------------------------------------------------------------------ engine
    def start(self) -> None:
        self.svc.build_engine(self.bridge.sink)
        self.overlay.set_threshold(self.svc.config.ai.confidence_threshold)
        self._maybe_show_simulator()
        self.svc.engine.start()
        self.svc.watchdog.start()
        if self.hotkeys:
            self.hotkeys.start()
        self.sync_hotkeys()
        self.apply_appearance()

    def rebuild_engine(self) -> None:
        if self.svc.engine:
            self.svc.engine.stop()
        self.svc.engine = None
        if not self.svc.config.demo_mode and self.sim_window is not None:
            self.sim_window.close()
            self.sim_window = None
        self.svc.build_engine(self.bridge.sink)
        self._maybe_show_simulator()
        self.svc.engine.start()
        self.overlay.set_question(None)

    def _maybe_show_simulator(self) -> None:
        if self.svc.config.demo_mode and self.demo_window and self.svc.simulator is not None:
            from smart360.ui.simulator_window import SimulatorWindow

            if self.sim_window is None:
                self.sim_window = SimulatorWindow(self.svc.simulator)
            self.sim_window.show()

    def apply_engine_config(self) -> None:
        self.svc.apply_config()
        self.overlay.set_threshold(self.svc.config.ai.confidence_threshold)

    def apply_appearance(self) -> None:
        a = self.svc.config.appearance
        self.overlay.set_overlay_opacity(a.overlay_opacity)
        if self.overlay.mode != a.overlay_mode:
            self.overlay.set_mode(a.overlay_mode)
        if self.overlay.pinned != a.overlay_pinned:
            self.overlay.set_pinned(a.overlay_pinned)
        self.overlay.set_reduce_motion(a.reduce_motion)
        self.dashboard.set_reduce_motion(a.reduce_motion)
        self.sounds.enabled = a.sounds

    # ------------------------------------------------------------------ state reactions
    def _on_state(self, state: str, _reason: str) -> None:
        self.overlay.set_state(state)
        if state == "WAITING_FOR_CONFIRMATION" and self._last_state != state:
            self.sounds.play("ready")
        self._last_state = state
        self.sync_hotkeys()

    def _on_prediction(self, p) -> None:  # type: ignore[no-untyped-def]
        self.overlay.set_prediction(p)
        self.sync_hotkeys()

    def _on_execution(self, d: dict) -> None:
        ok = bool(d.get("ok"))
        self.overlay.flash_result(ok, d.get("message", ""))
        self.sounds.play("confirm" if ok else "error")
        if not ok:
            self.toast(d.get("message", "Action failed"), "warning")

    def sync_hotkeys(self) -> None:
        """ENTER/ESC are only registered globally while a question awaits confirmation (and ENTER not at all
        for manual-check predictions), so they never swallow Enter in other apps."""
        if not self.hotkeys:
            return
        c = self.svc.config.controls
        if not c.global_hotkeys:
            self.hotkeys.set_bindings({})
            return
        eng = self.svc.engine
        bindings = {"pause": c.pause, "reanalyze": c.reanalyze, "mini_mode": c.mini_mode, "quit": c.quit}
        if eng and eng.sm.state.value == "WAITING_FOR_CONFIRMATION":
            bindings["reject"] = c.reject
            if eng.prediction is not None and not eng.prediction.uncertain:
                bindings["confirm"] = c.confirm
        self.hotkeys.set_bindings(bindings)

    # ------------------------------------------------------------------ actions
    def on_hotkey(self, action: str) -> None:
        eng = self.svc.engine
        if action == "confirm":
            p = eng.prediction if eng else None
            if p is not None and p.uncertain:
                self.toast("Manual check - confirm with the button, not ENTER", "warning")
                return
            self.confirm()
        elif action == "reject":
            self.reject()
        elif action == "pause" and eng:
            eng.toggle_pause()
        elif action == "reanalyze" and eng:
            eng.reanalyze()
        elif action == "mini_mode":
            self.overlay.cycle_mode()
        elif action == "quit":
            self.quit()

    def confirm(self) -> None:
        eng = self.svc.engine
        q = eng.question if eng else None
        if eng and q is not None:
            eng.approve(q.question_id)  # the engine + state machine validate everything again

    def reject(self) -> None:
        eng = self.svc.engine
        q = eng.question if eng else None
        if eng and q is not None:
            eng.reject(q.question_id)

    def open_calibration(self) -> None:
        from smart360.capture.targets import CaptureError, TargetLost
        from smart360.ui.calibration import CalibrationWizard

        eng = self.svc.engine
        if eng is None:
            return
        try:
            rect = eng.target.locate()
            snap = eng.target.grab(rect)
        except (TargetLost, CaptureError) as e:
            self.toast(f"Open 360° online first ({e})", "warning")
            return
        wiz = CalibrationWizard(
            snap, rect, eng.extractor, [p.get("name", "") for p in self.svc.config.detection.profiles]
        )
        wiz.saved.connect(self._profile_saved)
        wiz.showFullScreen() if os.environ.get("QT_QPA_PLATFORM") != "offscreen" else wiz.show()
        self._wizard = wiz

    def _profile_saved(self, prof: dict) -> None:
        profs = [p for p in self.svc.config.detection.profiles if p.get("name") != prof["name"]] + [prof]
        self.svc.store.update(detection={"profiles": profs})
        self.apply_engine_config()
        self.toast(f"Profile '{prof['name']}' saved", "success")
        onb = getattr(self, "onboarding", None)
        if onb is not None:
            onb.update_calibration_status()

    def toast(self, text: str, kind: str = "info") -> None:
        if self.dashboard.isVisible():
            self.dashboard.toast.show_message(text, kind)
        else:
            logging.getLogger(__name__).info("toast: %s", text)

    def show_dashboard(self) -> None:
        self.dashboard.showNormal()
        self.dashboard.raise_()
        self.dashboard.activateWindow()

    def toggle_overlay(self) -> None:
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.overlay.show()

    def place_overlay(self) -> None:
        pos = self.svc.config.appearance.overlay_pos
        scr = self.app.primaryScreen()
        if (
            pos
            and scr
            and any(s.availableGeometry().contains(pos[0] + 20, pos[1] + 20) for s in self.app.screens())
        ):
            self.overlay.move(pos[0], pos[1])
        elif scr:
            g = scr.availableGeometry()
            self.overlay.move(g.right() - self.overlay.width() - 24, g.top() + 80)

    def _measure_lag(self) -> None:
        from smart360.health.monitor import Health

        now = time.perf_counter()
        lag = max(0.0, (now - self._lag_last) * 1000 - 250)
        self._lag_last = now
        m = self.svc.health.metrics["ui_lag_ms"]
        m.add(lag)
        state = Health.HEALTHY if m.avg < 50 else Health.DEGRADED
        self.svc.health.set("UI", state, f"event lag {m.avg:.0f} ms")

    def quit(self) -> None:
        if self.hotkeys:
            self.hotkeys.stop()
        self.svc.shutdown()
        self.app.quit()


if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="360smart", description=f"{APP_NAME} {__version__}")
    parser.add_argument(
        "--demo", action="store_true", help="start in demo mode (built-in simulator, offline)"
    )
    parser.add_argument("--debug", action="store_true", help="verbose logging to console")
    parser.add_argument("--data-dir", type=Path, help="override the data directory")
    parser.add_argument(
        "--self-test", action="store_true", help="run diagnostics and exit (exit code 1 on fail)"
    )
    parser.add_argument("--no-splash", action="store_true")
    args = parser.parse_args(argv)

    if args.data_dir:
        os.environ["SMART360_HOME"] = str(args.data_dir)

    from smart360.platform import win32

    dpi = win32.enable_dpi_awareness()
    setup_logging(args.debug)
    log = logging.getLogger("smart360")
    log.info("%s %s starting (dpi=%s)", APP_NAME, __version__, dpi)

    from smart360.services import Services

    services = Services.create(demo=True if args.demo else None)

    if args.self_test:
        from smart360.health.diagnostics import run_self_test

        results = run_self_test(services)
        for r in results:
            print(f"{r.status.upper():5} {r.name:<14} {r.detail}")
        services.shutdown()
        return 1 if any(r.status == "fail" for r in results) else 0

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)

    from smart360.ui import theme

    theme.load_fonts()
    app.setStyleSheet(theme.stylesheet())

    from smart360.health.diagnostics import run_self_test
    from smart360.ui.splash import StartupSplash

    results = run_self_test(services)
    if not args.no_splash:
        splash = StartupSplash()
        splash.center()
        splash.show()
        splash.run(results)
        splash.wait_done()
        splash.fade_out()

    ctrl = AppController(app, services)
    ctrl.start()
    _install_tray(app, ctrl)

    def show_main() -> None:
        ctrl.place_overlay()
        ctrl.overlay.animate_in()
        ctrl.show_dashboard()

    if not services.config.first_run_done:
        from smart360.ui.onboarding import Onboarding

        onb = Onboarding(ctrl.ctx)
        ctrl.onboarding = onb  # type: ignore[attr-defined]
        onb.request_calibration.connect(ctrl.open_calibration)
        onb.demo_chosen.connect(lambda _d: ctrl.rebuild_engine())
        onb.finished.connect(show_main)
        onb.show()
    else:
        show_main()

    ctrl.dashboard.closing.connect(lambda: ctrl.toast("Still running in the tray", "info"))
    code = app.exec()
    services.shutdown()
    return code


def _install_tray(app, ctrl: AppController) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QMenu, QSystemTrayIcon

    from smart360.ui.icons import icon
    from smart360.ui.theme import C

    if not QSystemTrayIcon.isSystemTrayAvailable():
        return
    tray = QSystemTrayIcon(icon("orbit", C.PRIMARY, 32), app)
    tray.setToolTip(f"{APP_NAME} {__version__}")
    menu = QMenu()
    for text, fn in (
        ("Open dashboard", ctrl.show_dashboard),
        ("Show / hide overlay", ctrl.toggle_overlay),
        ("Pause / resume", lambda: ctrl.on_hotkey("pause")),
        (None, None),
        ("Quit", ctrl.quit),
    ):
        if text is None:
            menu.addSeparator()
            continue
        act = QAction(text, menu)
        act.triggered.connect(fn)
        menu.addAction(act)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: ctrl.show_dashboard() if reason == QSystemTrayIcon.ActivationReason.Trigger else None
    )
    tray.show()
    ctrl.tray = tray  # type: ignore[attr-defined]


if __name__ == "__main__":
    sys.exit(main())
