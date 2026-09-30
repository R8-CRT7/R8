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
    assert h.input.log == []


def test_null_ocr_means_no_question_and_no_click(harness):
    h = harness()
    h.engine.extractor.ocr = NullOcr()
    h.engine.start()
    h.wait(lambda: h.engine.status == "Watching for questions", msg="watching")
    assert h.engine.question is None and h.input.log == []


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


def test_unknown_forced_profile_falls_back_to_auto(harness):
    h = harness()
    h.engine.forced_profile = "does-not-exist"
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
