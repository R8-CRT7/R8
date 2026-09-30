"""Render UI screens to PNG for visual review / visual regression (works headless).

QT_QPA_PLATFORM=offscreen python tools/screenshots.py [outdir] [only...]
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication, QWidget

from smart360.core.models import AnswerOption, Prediction, PredictionSource, Question
from smart360.ui import theme

QUESTION = Question(
    text="Sie nähern sich einer Kreuzung ohne Verkehrszeichen. Von rechts kommt ein Radfahrer. "
    "Wie verhalten Sie sich?",
    answers=(
        AnswerOption(1, "Ich lasse den Radfahrer zuerst fahren"),
        AnswerOption(2, "Ich fahre zügig vor dem Radfahrer"),
        AnswerOption(3, "Ich verringere die Geschwindigkeit und bin bremsbereit"),
    ),
    has_image=True,
    image_hash=0xABCDEF,
    ocr_confidence=0.93,
)
PRED = Prediction(
    question_id=QUESTION.question_id,
    answers=(1, 3),
    model_confidence=0.97,
    confidence=0.96,
    reason="Ohne Verkehrszeichen gilt rechts vor links - auch gegenüber Radfahrern. Bremsbereit bleiben.",
    uncertain=False,
    source=PredictionSource.AI,
    model="claude-opus-5-5",
    topic="Vorfahrt",
    latency_ms=1840,
    confidence_breakdown=(
        ("model", 0.97),
        ("ocr", 0.93),
        ("layout", 1.0),
        ("image_clarity", 0.88),
        ("question_match", 1.0),
    ),
)
PRED_UNCERTAIN = Prediction(
    question_id=QUESTION.question_id,
    answers=(2,),
    model_confidence=0.62,
    confidence=0.58,
    reason="Das Situationsbild ist unscharf; bitte die Antwort selbst prüfen.",
    uncertain=True,
    source=PredictionSource.AI,
    model="claude-opus-5-5",
    topic="Vorfahrt",
)


def grab(w: QWidget, path: Path, bg: bool = True, settle: float = 0.9) -> None:
    """Composite a translucent top-level widget onto the app canvas and save it."""
    app = QApplication.instance()
    end = time.monotonic() + settle
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
    pm = w.grab()
    img = QImage(pm.size(), QImage.Format.Format_ARGB32_Premultiplied)
    img.setDevicePixelRatio(pm.devicePixelRatio())
    p = QPainter(img)
    if bg:
        theme.paint_canvas(p, QRect(0, 0, pm.width(), pm.height()))
    else:
        p.fillRect(img.rect(), QColor(0, 0, 0, 0))
    p.drawPixmap(QPoint(0, 0), pm)
    p.end()
    img.save(str(path))
    print("saved", path)


def shots_overlay(out: Path) -> None:
    from smart360.ui.overlay import OverlayWindow

    ov = OverlayWindow("full")
    ov.set_question(QUESTION)
    ov.set_state("WAITING_FOR_CONFIRMATION")
    ov.set_prediction(PRED)
    ov.show()
    grab(ov, out / "overlay_full_ready.png")
    ov.set_prediction(PRED_UNCERTAIN)
    grab(ov, out / "overlay_full_uncertain.png")
    ov.set_prediction(None)
    ov.set_state("ANALYZING")
    grab(ov, out / "overlay_full_analyzing.png")
    ov.set_question(None)
    ov.set_state("WAITING_FOR_QUESTION")
    grab(ov, out / "overlay_full_idle.png")
    ov.set_state("PAUSED")
    grab(ov, out / "overlay_full_paused.png")
    ov.set_question(QUESTION)
    ov.set_state("WAITING_FOR_CONFIRMATION")
    ov.set_prediction(PRED)
    ov.set_mode("focus")
    grab(ov, out / "overlay_focus.png")
    ov.set_mode("orbit")
    grab(ov, out / "overlay_orbit.png")
    ov.close()


def _seed_history(svc) -> None:  # type: ignore[no-untyped-def]
    import random

    from smart360.core.models import Decision, HistoryEntry

    rng = random.Random(4)
    samples = [
        ("Vorfahrt", "Sie nähern sich einer Kreuzung ohne Verkehrszeichen. Wer hat Vorfahrt?"),
        ("Verkehrszeichen", "Was bedeutet dieses Verkehrszeichen?"),
        ("Geschwindigkeit", "Welche Höchstgeschwindigkeit gilt innerorts für Pkw?"),
        ("Gefahrenlehre", "Womit müssen Sie rechnen, wenn Kinder am Fahrbahnrand stehen?"),
        ("Überholen", "Wann ist das Überholen verboten?"),
        ("Technik", "Was müssen Sie vor Fahrtantritt regelmäßig prüfen?"),
        ("Umwelt", "Wie fahren Sie umweltschonend?"),
        ("Abstand", "Wie groß muss der Sicherheitsabstand bei 100 km/h mindestens sein?"),
    ]
    now = time.time()
    for i in range(26):
        topic, text = samples[i % len(samples)]
        conf = rng.uniform(0.55, 0.99) if topic != "Vorfahrt" else rng.uniform(0.5, 0.85)
        dec = rng.choice([Decision.ACCEPTED] * 5 + [Decision.REJECTED, Decision.SKIPPED])
        svc.history.add(
            HistoryEntry(
                f"q{i}",
                text,
                ("A", "B", "C"),
                (1,) if i % 3 else (1, 3),
                conf,
                dec,
                topic,
                rng.choice(["ai", "ai", "cache"]),
                rng.uniform(900, 3200),
                now - i * 97,
                conf < 0.7,
                rng.uniform(0.62, 0.97),
                "claude-opus-5-5",
            )
        )


def shots_dashboard(out: Path) -> None:
    import tempfile

    from smart360.services import Services
    from smart360.ui.bridge import EngineBridge
    from smart360.ui.dashboard import Dashboard
    from smart360.ui.pages.base import UiContext

    tmp = Path(tempfile.mkdtemp())
    svc = Services.create(tmp, demo=True)
    svc.store.config.first_run_done = True
    bridge = EngineBridge()
    svc.build_engine(bridge.sink)
    _seed_history(svc)
    ctx = UiContext(svc, bridge)
    dash = Dashboard(ctx)
    dash.resize(1320, 860)
    dash.show()
    svc.engine.start()
    svc.watchdog.sample()
    app = QApplication.instance()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and svc.engine.sm.state.value != "WAITING_FOR_CONFIRMATION":
        app.processEvents()
        time.sleep(0.02)
    from smart360.health.diagnostics import run_self_test

    for i, (key, _t, _c) in enumerate(__import__("smart360.ui.dashboard", fromlist=["NAV"]).NAV):
        dash.go(i)
        if key == "diagnostics":
            dash.pages[i]._run()
        grab(dash, out / f"dash_{i:02d}_{key}.png", bg=False, settle=0.8)
    _ = run_self_test
    svc.shutdown()
    dash.close()


def shots_flow(out: Path) -> None:
    import tempfile

    from smart360.capture.simulator import LAYOUT, PracticeSimulator
    from smart360.core.models import Rect
    from smart360.health.diagnostics import run_self_test
    from smart360.services import Services
    from smart360.ui.bridge import EngineBridge
    from smart360.ui.calibration import CalibrationWizard
    from smart360.ui.onboarding import Onboarding
    from smart360.ui.pages.base import UiContext
    from smart360.ui.splash import StartupSplash
    from smart360.vision.extractor import QuestionExtractor
    from smart360.vision.ocr import select_backend

    svc = Services.create(Path(tempfile.mkdtemp()), demo=True)
    svc.build_engine(None)
    sp = StartupSplash()
    sp.show()
    sp.run(run_self_test(svc))
    sp.wait_done()
    grab(sp, out / "splash.png")
    sp.close()
    onb = Onboarding(UiContext(svc, EngineBridge()))
    onb.show()
    for i in range(6):
        grab(onb, out / f"onboarding_{i}.png", bg=False, settle=0.5)
        if i < 5:
            onb.next()
    onb.close()
    sim = PracticeSimulator()
    wiz = CalibrationWizard(
        sim.render(), Rect(0, 0, sim.width, sim.height), QuestionExtractor(select_backend())
    )
    wiz.resize(1280, 800)
    wiz.show()
    ir = wiz._image_rect()
    from PySide6.QtCore import QRectF

    for k in ("question", "answers", "image"):
        n = LAYOUT[k]
        wiz.regions[k] = QRectF(n.x * sim.width, n.y * sim.height, n.w * sim.width, n.h * sim.height)
    wiz.step = 1
    wiz._sync()
    grab(wiz, out / "calibration_select.png", bg=False)
    wiz.step = 3
    wiz._sync()
    grab(wiz, out / "calibration_test.png", bg=False)
    wiz.close()
    _ = ir
    sim.render().save(out / "simulator.png")
    svc.shutdown()


SHOTS = {"overlay": shots_overlay, "dashboard": shots_dashboard, "flow": shots_flow}


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("artifacts/screens")
    only = set(sys.argv[2:])
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    theme.load_fonts()
    app.setStyleSheet(theme.stylesheet())
    for name, fn in SHOTS.items():
        if only and name not in only:
            continue
        fn(out)
    _ = Qt


if __name__ == "__main__":
    main()
