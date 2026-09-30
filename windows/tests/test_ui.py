"""UI tests (pytest-qt, offscreen). Behaviour, not pixels - pixels are reviewed via tools/screenshots.py."""

import time

import pytest
from PySide6.QtCore import QPoint, Qt

from smart360.core.models import AnswerOption, Prediction, PredictionSource, Question
from smart360.ui import theme

from .conftest import requires_tesseract

Q = Question(
    "Wer hat Vorfahrt an dieser Kreuzung?", (AnswerOption(1, "Ich"), AnswerOption(2, "Der Radfahrer"))
)
P = Prediction(
    Q.question_id, (2,), 0.95, 0.94, "Rechts vor links.", False, PredictionSource.AI, "m", "Vorfahrt"
)
P_UNC = Prediction(Q.question_id, (1,), 0.5, 0.5, "Unklar.", True, PredictionSource.AI, "m", "Vorfahrt")


@pytest.fixture(autouse=True)
def _fonts(qapp):
    theme.load_fonts()
    qapp.setStyleSheet(theme.stylesheet())


@pytest.fixture
def services(tmp_path, monkeypatch):
    from smart360.services import Services

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    svc = Services.create(tmp_path, demo=True)
    yield svc
    svc.shutdown()


def test_overlay_states_and_modes(qtbot):
    from smart360.ui.overlay import OverlayWindow

    ov = OverlayWindow("full")
    qtbot.addWidget(ov)
    ov.show()
    ov.set_question(Q)
    ov.set_state("WAITING_FOR_CONFIRMATION")
    ov.set_prediction(P)
    assert ov.btn_confirm.isEnabled()
    assert ov.f_answer.text() == "2"
    assert ov.k_enter.isVisible()
    ov.set_prediction(P_UNC)
    assert ov.f_manual.isVisible()
    assert not ov.k_enter.isVisible()  # ENTER hint hidden for manual checks
    assert ov.btn_confirm.text() == "CONFIRM ANYWAY"
    ov.set_state("ANALYZING")
    assert not ov.btn_confirm.isEnabled()
    ov.set_state("PAUSED")
    assert ov.btn_resume.isVisible() and not ov.btn_confirm.isVisible()
    for mode, size in (("focus", ov.FOCUS_SIZE), ("orbit", ov.ORBIT_SIZE), ("full", ov.FULL_SIZE)):
        ov.set_mode(mode)
        assert ov.size() == size
    ov.cycle_mode()
    assert ov.mode == "focus"


def test_overlay_confirm_signal(qtbot):
    from smart360.ui.overlay import OverlayWindow

    ov = OverlayWindow("full")
    qtbot.addWidget(ov)
    ov.show()
    ov.set_question(Q)
    ov.set_state("WAITING_FOR_CONFIRMATION")
    ov.set_prediction(P)
    with qtbot.waitSignal(ov.confirm, timeout=1000):
        qtbot.mouseClick(ov.btn_confirm, Qt.MouseButton.LeftButton)


def test_pulse_all_states(qtbot):
    from smart360.ui.widgets import pulse

    w = pulse.NeuralPulse(64, wave=True)
    qtbot.addWidget(w)
    w.resize(300, 64)
    w.show()
    for st in (
        pulse.IDLE,
        pulse.CAPTURE,
        pulse.ANALYZING,
        pulse.READY,
        pulse.UNCERTAIN,
        pulse.CONFIRMED,
        pulse.ERROR,
        pulse.PAUSED,
    ):
        w.set_state(st)
        w.repaint()
    w.set_reduce_motion(True)
    w.repaint()
    w.hide()
    assert not w._timer.isActive()  # no CPU burn while hidden


def test_dashboard_pages_render_and_refresh(qtbot, services):
    from smart360.ui.bridge import EngineBridge
    from smart360.ui.dashboard import NAV, Dashboard
    from smart360.ui.pages.base import UiContext

    bridge = EngineBridge()
    services.build_engine(bridge.sink)
    dash = Dashboard(UiContext(services, bridge))
    qtbot.addWidget(dash)
    dash.show()
    for i in range(len(NAV)):
        dash.go(i)
        dash.pages[i].refresh()
    assert not [e for e in services.health.errors if e.component == "UI"]


def test_history_filters_and_empty_state(qtbot, services):
    from smart360.core.models import Decision, HistoryEntry
    from smart360.ui.bridge import EngineBridge
    from smart360.ui.pages.base import UiContext
    from smart360.ui.pages.history import HistoryPage

    page = HistoryPage(UiContext(services, EngineBridge()))
    qtbot.addWidget(page)
    page.show()
    page.refresh()
    assert page.empty.isVisible() and not page.view.isVisible()
    for i, d in enumerate((Decision.ACCEPTED, Decision.REJECTED, Decision.ACCEPTED)):
        services.history.add(
            HistoryEntry(
                f"q{i}",
                f"Frage {i}",
                ("a",),
                (1,),
                0.9 - i * 0.2,
                d,
                "Technik",
                "ai",
                100,
                time.time(),
                False,
                0.9,
            )
        )
    page.refresh()
    assert page.model.rowCount() == 3
    page._set_filter("rejected")
    assert page.model.rowCount() == 1
    page._set_filter("low")  # 0.7 and 0.5 are below the 0.75 threshold
    assert page.model.rowCount() == 2
    page._set_filter("all")
    page.search.setText("Frage 2")
    qtbot.wait(300)
    assert page.model.rowCount() == 1


def test_calibration_wizard_creates_valid_profile(qtbot):
    from smart360.capture.simulator import LAYOUT, PracticeSimulator
    from smart360.ui.calibration import CalibrationWizard
    from smart360.vision.extractor import LayoutProfile, QuestionExtractor
    from smart360.vision.ocr import NullOcr

    sim = PracticeSimulator()
    wiz = CalibrationWizard(sim.render(), sim.rect, QuestionExtractor(NullOcr()))
    qtbot.addWidget(wiz)
    wiz.resize(1280, 800)
    wiz.show()
    got = []
    wiz.saved.connect(got.append)

    def drag(norm):
        ir = wiz._image_rect()
        a = QPoint(int(ir.left() + norm.x * ir.width()), int(ir.top() + norm.y * ir.height()))
        b = QPoint(
            int(ir.left() + (norm.x + norm.w) * ir.width()), int(ir.top() + (norm.y + norm.h) * ir.height())
        )
        qtbot.mousePress(wiz, Qt.MouseButton.LeftButton, pos=a)
        qtbot.mouseMove(wiz, pos=b)
        qtbot.mouseRelease(wiz, Qt.MouseButton.LeftButton, pos=b)

    assert not wiz.btn_next.isEnabled()
    drag(LAYOUT["question"])
    assert "question" in wiz.regions and wiz.btn_next.isEnabled()
    wiz.next()
    drag(LAYOUT["answers"])
    wiz.next()
    drag(LAYOUT["image"])
    drag(LAYOUT["action"])  # advances to test automatically
    assert wiz.step == 3
    wiz.next()
    wiz.name.setText("Laptop")
    wiz.next()
    assert got and got[0]["name"] == "Laptop"
    prof = LayoutProfile.from_dict(got[0])
    assert abs(prof.question.x - LAYOUT["question"].x) < 0.01
    assert abs(prof.answers.h - LAYOUT["answers"].h) < 0.01


def test_onboarding_flow_demo(qtbot, services):
    from smart360.ui.bridge import EngineBridge
    from smart360.ui.onboarding import Onboarding
    from smart360.ui.pages.base import UiContext

    services.build_engine(None)
    onb = Onboarding(UiContext(services, EngineBridge()))
    qtbot.addWidget(onb)
    onb.show()
    demo = []
    onb.demo_chosen.connect(demo.append)
    services.store.update(demo_mode=False)
    onb.next()  # welcome -> AI
    onb._pick("mock")
    onb.next()  # AI -> detection (applies demo)
    assert demo == [True] and services.config.demo_mode
    onb.next()  # -> calibration
    onb.next()  # -> test (runs self-test)
    assert onb.test_box.count() >= 6
    onb.next()  # -> ready
    with qtbot.waitSignal(onb.finished, timeout=1000):
        onb.next()
    assert services.config.first_run_done


@requires_tesseract
def test_app_controller_demo_round_trip(qtbot, qapp, services):
    """Whole app in demo mode: detect -> recommend -> ENTER hotkey -> verified selection."""
    from smart360.app import AppController

    services.store.update(first_run_done=True)
    ctrl = AppController(qapp, services, demo_window=False)
    qtbot.addWidget(ctrl.dashboard)
    qtbot.addWidget(ctrl.overlay)
    ctrl.start()
    eng = services.engine
    eng.detector.policy.normal_s = 0.08
    qtbot.waitUntil(lambda: eng.sm.state.value == "WAITING_FOR_CONFIRMATION", timeout=30000)
    # the prediction signal is delivered (queued) no later than the state signal
    qtbot.waitUntil(lambda: ctrl.overlay.prediction is not None, timeout=2000)
    sim = services.simulator
    ctrl.on_hotkey("confirm")
    qtbot.waitUntil(lambda: eng.sm.state.value == "WAITING_FOR_NEXT_QUESTION", timeout=20000)
    assert sim.is_solved_correctly()
    # manual-check predictions refuse ENTER
    from dataclasses import replace

    sim.next()
    qtbot.waitUntil(lambda: eng.sm.state.value == "WAITING_FOR_CONFIRMATION", timeout=30000)
    eng.prediction = replace(eng.prediction, uncertain=True)
    before = list(sim.clicks)
    ctrl.on_hotkey("confirm")
    qtbot.wait(800)
    assert sim.clicks == before
    assert eng.sm.state.value == "WAITING_FOR_CONFIRMATION"
    ctrl.on_hotkey("pause")
    qtbot.waitUntil(lambda: eng.sm.state.value == "PAUSED", timeout=5000)
    services.engine.stop()


def test_ui_lag_health(qtbot, qapp, services):
    from smart360.app import AppController

    ctrl = AppController(qapp, services, demo_window=False)
    qtbot.addWidget(ctrl.dashboard)
    qtbot.addWidget(ctrl.overlay)
    qtbot.wait(700)
    assert services.health.components["UI"].state.value == "HEALTHY"
