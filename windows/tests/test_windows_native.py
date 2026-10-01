"""Native Windows tests - run on a real Windows desktop (CI: windows-latest runner).

    set QT_QPA_PLATFORM=windows && pytest -m windows tests/test_windows_native.py

These exercise the parts that cannot be tested on Linux: Win32 window detection, real
screen capture (mss), Windows.Media.Ocr, SendInput clicks, RegisterHotKey, capture
exclusion and the Windows Credential Manager.
"""

import ctypes
import sys
import time

import pytest

pytestmark = [
    pytest.mark.windows,
    pytest.mark.skipif(sys.platform != "win32", reason="requires Windows"),
]


@pytest.fixture(scope="module", autouse=True)
def _dpi():
    from smart360.platform import win32

    win32.enable_dpi_awareness()


def test_dpi_awareness():
    from smart360.platform import win32

    assert win32.enable_dpi_awareness() in ("per-monitor-v2", "per-monitor", "system")


def test_windows_ocr_reads_simulator():
    from smart360.capture.simulator import PracticeSimulator, simulator_profile
    from smart360.vision.extractor import LayoutProfile, QuestionExtractor
    from smart360.vision.ocr import WindowsOcr

    ocr = WindowsOcr()
    assert ocr.available(), "Windows.Media.Ocr not available"
    sim = PracticeSimulator()
    t0 = time.perf_counter()
    res = QuestionExtractor(ocr).extract(sim.render(), sim.rect, LayoutProfile.from_dict(simulator_profile()))
    dt = (time.perf_counter() - t0) * 1000
    print(f"Windows OCR extraction: {dt:.0f} ms")
    q = res.question
    assert q is not None, res.problem
    assert "Kreuzung" in q.text or "Kreuzung" in q.text.replace("  ", " ")
    assert len(q.answers) == 3


def test_windows_ocr_concurrent_calls():
    """Regression: one shared OcrEngine rejected the parallel question/answer OCR
    ("Another RecognizeAsync operation is already running!")."""
    from concurrent.futures import ThreadPoolExecutor

    from smart360.capture.simulator import PracticeSimulator
    from smart360.vision.ocr import WindowsOcr

    ocr = WindowsOcr()
    assert ocr.available()
    img = PracticeSimulator().render()
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda _: ocr.recognize(img), range(8)))
    assert all(len(r) > 3 for r in results)


def test_window_detection_and_capture_exclusion(qtbot):
    from PySide6.QtWidgets import QWidget

    from smart360.platform import win32

    w = QWidget()
    w.setWindowTitle("360° online - Theorie lernen")
    w.resize(640, 420)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    qtbot.wait(300)
    info = win32.find_learning_window()
    assert info is not None and info.hwnd == int(w.winId())
    rect = win32.client_rect(info.hwnd)
    assert rect is not None and rect.w > 0 and rect.h > 0
    assert win32.exclude_from_capture(int(w.winId()))


def test_keyring_is_windows_credential_manager():
    from smart360.storage.secrets import SecretStore

    s = SecretStore(use_keyring=True)
    assert s.secure, s.backend
    name = "SMART360_CI_TEST_KEY"
    assert s.set(name, "sk-test-123") is True
    assert s.get(name) == "sk-test-123"
    s.delete(name)
    assert s.get(name) is None
    assert "Windows" in s.backend_label or "Credential" in s.backend_label


def _press(vk: int) -> None:
    user32 = ctypes.windll.user32
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(vk, 0, 2, 0)


def test_global_hotkey_f8(qtbot):
    from smart360.platform import win32

    got = []
    hk = win32.GlobalHotkeys(got.append)
    assert hk.start()
    hk.set_bindings({"pause": "F8"})
    qtbot.wait(300)
    assert "pause" not in hk.failed
    _press(0x77)  # F8
    qtbot.waitUntil(lambda: "pause" in got, timeout=3000)
    hk.set_bindings({})
    qtbot.wait(200)
    hk.stop()


def _native_setup(qtbot, settings, tracer=None):
    """Real window (simulator in a Qt window titled like 360° online), real capture, Windows OCR,
    real Win32 input driver."""
    from PySide6.QtCore import Qt

    from smart360.ai.mock_provider import MockProvider
    from smart360.ai.resilience import ResilientSolver
    from smart360.capture.change import ChangeDetector, PollingPolicy
    from smart360.capture.simulator import PracticeSimulator, simulator_profile
    from smart360.capture.targets import WindowTarget
    from smart360.engine.engine import Engine
    from smart360.engine.input import Win32InputDriver
    from smart360.health.monitor import HealthMonitor
    from smart360.storage.cache import QuestionCache
    from smart360.storage.history import HistoryStore
    from smart360.ui.simulator_window import SimulatorWindow
    from smart360.vision.extractor import LayoutProfile, QuestionExtractor
    from smart360.vision.ocr import select_backend

    from .conftest import truth_answer_fn

    sim = PracticeSimulator(width=900, height=560)
    win = SimulatorWindow(sim)
    win.setWindowTitle("360° online - Simulator")
    win.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    qtbot.addWidget(win)
    win.move(40, 40)
    win.show()
    win.raise_()
    win.activateWindow()
    qtbot.waitExposed(win)
    qtbot.wait(800)

    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp())
    events = []
    engine = Engine(
        target=WindowTarget((r"360° online - Simulator",)),
        extractor=QuestionExtractor(select_backend("windows")),
        solver=ResilientSolver(MockProvider(truth_answer_fn(sim), latency_s=0.05), timeout_s=10),
        cache=QuestionCache(tmp / "c.db"),
        history=HistoryStore(tmp / "h.db"),
        health=HealthMonitor(),
        input_driver=Win32InputDriver(),
        profiles=[LayoutProfile.from_dict(simulator_profile())],
        settings=settings,
        detector=ChangeDetector(policy=PollingPolicy(fast_s=0.1, normal_s=0.2)),
        sink=events.append,
    )
    engine.tracer = tracer
    return sim, win, engine, events


def test_real_end_to_end_capture_ocr_click(qtbot):
    """Real window, real screen capture, real Windows OCR, real SendInput clicks - only after approval -
    in SAFE MODE (the shipped default): the checkboxes must be really found on the real rendering."""
    from smart360.engine.engine import EngineSettings

    sim, _win, engine, events = _native_setup(qtbot, EngineSettings(settle_s=0.4, safe_mode=True))
    engine.start()
    try:
        qtbot.waitUntil(lambda: engine.sm.state.value == "WAITING_FOR_CONFIRMATION", timeout=40000)
        print("OCR question:", engine.question.text)
        print("OCR answers:", [a.text for a in engine.question.answers])
        print("checkboxes:", [(a.index, a.checkbox, a.checkbox_found) for a in engine.question.answers])
        print("truth answers:", list(sim.question.answers))
        assert engine.prediction.answers == sim.displayed_correct()
        assert all(a.checkbox_found for a in engine.question.answers)
        qtbot.wait(700)
        assert len(sim.clicks) == 0, "clicked before confirmation!"
        engine.approve(engine.question.question_id)
        qtbot.waitUntil(lambda: any(e.kind == "execution" for e in events), timeout=30000)
        ev = next(e for e in events if e.kind == "execution")
        print("execution:", ev.data)
        assert ev.data["ok"], ev.data
        assert sim.is_solved_correctly()
    finally:
        engine.stop()


def test_real_dry_run_shows_targets_and_sends_no_input(qtbot, tmp_path):
    """Dry run on the real desktop: everything up to SendInput, the planned click points are the real
    checkbox centres, and NO input reaches the window. The trace picture with the red crosses is written."""
    from smart360.engine.engine import EngineSettings
    from smart360.engine.trace import SessionTrace, latest_trace, read_trace

    tracer = SessionTrace(tmp_path)
    sim, win, engine, events = _native_setup(
        qtbot, EngineSettings(settle_s=0.4, safe_mode=True, dry_run=True), tracer
    )
    engine.start()
    try:
        qtbot.waitUntil(lambda: engine.sm.state.value == "WAITING_FOR_CONFIRMATION", timeout=40000)
        engine.approve(engine.question.question_id)
        qtbot.waitUntil(lambda: any(e.kind == "execution" for e in events), timeout=30000)
        ev = next(e for e in events if e.kind == "execution")
        print("dry run:", ev.data["message"])
        assert ev.data["ok"] and ev.data["dry_run"]
        qtbot.wait(600)
        assert len(sim.clicks) == 0 and sim.state.selected == set()  # deque, not list
        from PySide6.QtCore import QPoint

        for c in ev.data["clicks"]:
            # the same mapping a real click takes: screen -> simulator window -> checkbox (runner: 100 % DPI)
            local = win.mapFromGlobal(QPoint(c["x"], c["y"]))
            box = sim._checkboxes[c["answer"]]
            assert box.x - 4 <= local.x() <= box.x + box.w + 4, (c, local, box)
            assert box.y - 4 <= local.y() <= box.y + box.h + 4, (c, local, box)
            assert c["blocked"] is None, c  # nothing covers the simulator window
        images = [e["image"] for e in read_trace(latest_trace(tmp_path)) if e.get("image")]
        assert any("dryrun" in i for i in images)
    finally:
        engine.stop()


def test_display_info_and_windows_version():
    from smart360.platform import win32

    mons = win32.display_info()
    print("monitors:", mons, "|", win32.windows_version())
    assert len(mons) >= 1 and all(m["dpi"] >= 96 and m["rect"][2] > 0 for m in mons)
    assert "Windows" in win32.windows_version()


def test_diagnosis_zip_on_windows(tmp_path, monkeypatch):
    import json
    import zipfile

    from smart360.health.bundle import create_bundle
    from smart360.services import Services

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    svc = Services.create(tmp_path / "home", demo=True)
    try:
        svc.build_engine(None)
        out = create_bundle(svc, tmp_path)
    finally:
        svc.shutdown()
    with zipfile.ZipFile(out) as z:
        report = json.loads(z.read("report.json"))
    print("system:", report["system"])
    assert report["system"]["monitor_count"] >= 1
    assert report["system"]["dpi_awareness"] in ("per-monitor-v2", "per-monitor", "system")


def test_click_refused_when_window_covers_target(qtbot):
    """If the overlay (or any window) covers the answer, nothing is clicked."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget

    from smart360.platform import win32

    target = QWidget()
    target.setWindowTitle("360° online - target")
    target.setGeometry(100, 100, 400, 300)
    cover = QWidget()
    cover.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    cover.setGeometry(150, 150, 120, 120)
    for w in (target, cover):
        qtbot.addWidget(w)
        w.show()
        qtbot.waitExposed(w)
    qtbot.wait(300)
    got = []
    target.mousePressEvent = lambda e: got.append(e)  # type: ignore[method-assign]
    pt = cover.geometry().center()
    with pytest.raises(win32.ClickTargetBlocked):
        win32.click(pt.x(), pt.y(), expected_hwnd=int(target.winId()))
    qtbot.wait(200)
    assert got == []
    # the dry run reports the same situation without sending anything
    from smart360.engine.input import Win32InputDriver

    reason = Win32InputDriver().blocked_reason(pt.x(), pt.y(), expected_window=int(target.winId()))
    assert reason and "covers" in reason
