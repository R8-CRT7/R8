"""Final bug hunt: deliberately hostile inputs and environments."""

import json
import os

import pytest

from smart360.capture.simulator import PracticeSimulator, simulator_profile
from smart360.core.models import AnswerOption, NormRect, Question, Rect
from smart360.services import Services
from smart360.storage.cache import QuestionCache
from smart360.storage.config import ConfigStore
from smart360.vision.extractor import LayoutProfile, QuestionExtractor
from smart360.vision.ocr import NullOcr, OcrBackend, OcrLine

from .conftest import requires_tesseract


def test_invalid_profiles_are_skipped_not_fatal(tmp_path):
    svc = Services.create(tmp_path, demo=False)
    try:
        svc.store.config.detection.profiles = [
            {"name": "broken"},  # missing regions
            {"name": "negative", "question": [-1, 0, 0.5, 0.5], "answers": [0, 0, 1, 1]},
            {"name": "zero", "question": [0, 0, 0, 0], "answers": [0, 0, 1, 1]},
            "not a dict",
            simulator_profile("ok"),
        ]
        profiles = svc.profiles()
        assert [p.name for p in profiles] == ["ok"]
        assert len([e for e in svc.health.errors if "invalid profile" in e.message]) == 4
    finally:
        svc.shutdown()


class ExplodingOcr(OcrBackend):
    name = "boom"

    def available(self):
        return True

    def recognize(self, img):
        raise RuntimeError("ocr crashed")


class GarbageOcr(OcrBackend):
    name = "garbage"

    def available(self):
        return True

    def recognize(self, img):
        return [OcrLine("|||", Rect(0, 0, 3, 3), 0.1), OcrLine("??", Rect(0, 5, 3, 3), 0.1)]


@pytest.mark.parametrize(
    "region",
    [
        NormRect(0.999, 0.999, 0.001, 0.001),  # 1 px at the corner
        NormRect(0.0, 0.0, 1.0, 1.0),  # whole window
    ],
)
def test_extreme_regions_do_not_crash(region):
    sim = PracticeSimulator()
    prof = LayoutProfile("x", region, region, region, region)
    res = QuestionExtractor(GarbageOcr()).extract(sim.render(), sim.rect, prof)
    assert res.question is None and res.problem


def test_ocr_crash_is_contained_by_engine(harness):
    h = harness()
    h.engine.extractor.ocr = ExplodingOcr()
    h.engine.start()
    h.wait(lambda: any(e.component == "Vision" for e in h.health.errors), msg="vision error recorded")
    assert h.engine.alive
    assert len(h.input.log) == 0


def test_null_ocr_means_no_question_and_no_click(harness):
    h = harness()
    h.engine.extractor.ocr = NullOcr()
    h.engine.start()
    h.wait(lambda: h.engine.status == "Watching for questions", msg="watching")
    assert h.engine.question is None and len(h.input.log) == 0


def test_cache_file_deleted_while_running(tmp_path):
    c = QuestionCache(tmp_path / "c.db")
    q = Question("Wer hat Vorfahrt hier?", (AnswerOption(1, "Ich"), AnswerOption(2, "Du")))
    c.store(q, (1,), 0.9, "r", "m")
    for suffix in ("", "-wal", "-shm"):
        p = tmp_path / f"c.db{suffix}"
        if p.exists():
            try:
                os.remove(p)
            except PermissionError:  # Windows keeps the file locked - also fine
                pass
    # lookups keep working from the in-memory index, writes do not crash
    assert c.lookup(q) is not None
    c.store(q, (2,), 0.9, "r", "m")
    c.close()


def test_config_deleted_while_running(tmp_path):
    s = ConfigStore(tmp_path / "config.json")
    s.update(first_run_done=True)
    (tmp_path / "config.json").unlink()
    s.update(ai={"retries": 3})
    assert json.loads((tmp_path / "config.json").read_text())["ai"]["retries"] == 3


def test_config_with_wrong_types_recovers(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"ai": {"timeout_s": "fast", "retries": -4}}))
    s = ConfigStore(tmp_path / "config.json")
    assert s.recovered and s.config.ai.retries == 2


@requires_tesseract
def test_unknown_forced_profile_falls_back_to_auto(harness):
    h = harness()
    h.engine.forced_profile = "does-not-exist"
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")


def test_change_detected_between_similar_text_only_questions():
    """Regression (found by the soak test): q9 -> q10 are both text-only with a similar layout; the
    mean pixel difference (0.96) was below the threshold and the new question was never analysed."""
    from smart360.capture.change import ChangeDetector

    sim = PracticeSimulator()
    prof = LayoutProfile.from_dict(simulator_profile())
    frame = Rect(0, 0, sim.width, sim.height)
    q, a = prof.question.to_abs(frame), prof.answers.to_abs(frame)
    band = (min(q.x, a.x), min(q.y, a.y), max(q.x + q.w, a.x + a.w), max(q.y + q.h, a.y + a.h))
    for i in range(len(sim.bank)):
        sim.goto(i)
        before = sim.render().crop(band)
        sim.goto(i + 1)
        after = sim.render().crop(band)
        det = ChangeDetector()
        det.mark_processed(before)
        assert not det.observe(before, 0.0)  # unchanged screen never triggers
        det.observe(after, 0.1)
        assert det.observe(after, 0.2), f"question {i} -> {i + 1} not detected"


@pytest.mark.parametrize(
    "raw",
    [
        "C] Ich lasse den Radfahrer zuerst fahren",
        "c] Ich lasse den Radfahrer zuerst fahren",
        "[C Ich lasse den Radfahrer zuerst fahren",
        "U] Ich lasse den Radfahrer zuerst fahren",
        "[_] Ich lasse den Radfahrer zuerst fahren",
        "Cl Ich lasse den Radfahrer zuerst fahren",
        "cl Ich lasse den Radfahrer zuerst fahren",
        "Ü Ich lasse den Radfahrer zuerst fahren",
        "ü Ich lasse den Radfahrer zuerst fahren",
        "Ich lasse den Radfahrer zuerst fahren",
    ],
)
def test_windows_ocr_checkbox_artefacts_are_stripped(raw):
    """Regression (native Windows CI): Windows OCR prefixes some answers with "C]" for the empty
    checkbox, inconsistently between captures - the answer text must not depend on it."""
    from smart360.vision.extractor import _clean

    assert _clean(raw) == "Ich lasse den Radfahrer zuerst fahren"


def test_real_words_are_not_stripped_as_checkbox():
    from smart360.vision.extractor import _clean

    for text in (
        "Ca. 50 Meter", "Um 10 km/h", "Es ist erlaubt", "Durch Hupen", "Ob ich darf",
        "Überholen ist verboten", "Old-timer", "Du musst warten", "0,5 Promille",
    ):
        assert _clean(text) == text


@pytest.mark.parametrize(
    ("raw", "clean"),
    [  # verbatim Windows OCR output from the CI benchmark (mismatch samples)
        ("ü vorfahrt gewähren", "vorfahrt gewähren"),
        ("Ü 50 km/h", "50 km/h"),
        ("cl 30 km/h", "30 km/h"),
        ("Cl dass die Kinder stehen bleiben", "dass die Kinder stehen bleiben"),
        ("ü Reifendruck und Profiltiefe", "Reifendruck und Profiltiefe"),
    ],
)
def test_windows_ocr_glyph_tokens_are_stripped(raw, clean):
    from smart360.vision.extractor import _clean

    assert _clean(raw) == clean


# ----------------------------------------------------------------------------- checkbox detection
def _row(text, box=None, filled=False, scale=1.0):
    from PIL import Image, ImageDraw, ImageFont

    from smart360.ui.theme import ASSETS

    font = ImageFont.truetype(str(ASSETS / "fonts" / "Inter-Regular.ttf"), int(20 * scale))
    img = Image.new("RGB", (int(560 * scale), int(48 * scale)), (255, 255, 255))
    d = ImageDraw.Draw(img)
    x = int(8 * scale)
    if box:
        s = int(22 * scale)
        d.rectangle((x, int(12 * scale), x + s, int(12 * scale) + s), outline=(90, 100, 112), width=2,
                    fill=(0, 84, 147) if filled else (255, 255, 255))
        x += s + int(14 * scale)
    d.text((x, int(12 * scale)), text, font=font, fill=(20, 28, 38))
    return img, Rect(x, int(12 * scale), int(400 * scale), int(24 * scale))


@pytest.mark.parametrize("scale", [0.75, 1.0, 1.5])
@pytest.mark.parametrize("filled", [False, True])
def test_checkbox_square_is_found(scale, filled):
    from smart360.vision.extractor import _find_checkbox

    img, line = _row("Ich lasse den Radfahrer zuerst fahren", box=True, filled=filled, scale=scale)
    rect, found = _find_checkbox(img, line, line)
    assert found
    s = int(22 * scale)
    assert abs(rect.center[0] - (int(8 * scale) + s // 2)) <= 3
    assert abs(rect.center[1] - (int(12 * scale) + s // 2)) <= 3


@pytest.mark.parametrize(
    "text", ["Ich lasse den Radfahrer zuerst fahren", "DO NOT OVERTAKE 0 km/h", "[ ] Halt", "Hupen IIII"]
)
def test_text_without_checkbox_is_never_reported_as_found(text):
    """No false positives: letters (D, O, 0, I, brackets) are not a checkbox -> safe mode won't click."""
    from smart360.vision.extractor import _find_checkbox

    img, line = _row(text, box=False)
    line = Rect(8, line.y, line.w, line.h)  # the line starts at the left edge
    _rect, found = _find_checkbox(img, line, line)
    assert not found
