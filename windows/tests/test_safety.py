"""Click-safety rules for the first real-PC test phase (safe mode, dry run, emergency stop).

Every test here proves that NOTHING is clicked in an unsafe situation, on the practice simulator
with real Tesseract OCR."""

import time

from smart360.core.models import Decision, Rect
from smart360.engine.engine import EngineSettings
from smart360.engine.input import SimulatorInputDriver
from smart360.platform.win32 import ClickTargetBlocked

from .conftest import requires_tesseract, truth_answer_fn

pytestmark = requires_tesseract

SAFE = dict(safe_mode=True, settle_s=0.05)


def _clicks(h):
    return [x for x in h.input.log if x[0] == "click"]


def _ready(h):
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    assert h.engine.prediction is not None


def test_unreadable_checkbox_state_never_clicks(harness, monkeypatch):
    """Regression: with unreadable checkbox states the executor clicked anyway, verification failed and the
    retries clicked the same boxes again (toggling them back). Now: no click at all, in any mode."""
    monkeypatch.setattr("smart360.engine.engine.checkbox_states", lambda *a, **k: None)
    h = harness()  # safe mode OFF - the rule is unconditional
    _ready(h)
    h.engine.approve(h.engine.question.question_id)
    ev = h.wait_event("execution")
    assert not ev.data["ok"] and "checkbox" in ev.data["message"]
    assert _clicks(h) == []


def test_ambiguous_target_never_clicks(harness, monkeypatch):
    """If an approved answer text matches more than one answer on screen, the target is not unique."""
    monkeypatch.setattr("smart360.engine.engine._same", lambda option, text: True)
    h = harness()
    _ready(h)
    h.engine.approve(h.engine.question.question_id)
    ev = h.wait_event("execution")
    assert not ev.data["ok"] and "ambiguous" in ev.data["message"]
    assert _clicks(h) == []


def test_safe_mode_low_confidence_is_not_clicked(harness):
    def unsure(req):
        r = truth_answer_fn(h.sim)(req)
        return {**r, "confidence": 0.5, "uncertain": True}

    from smart360.ai.mock_provider import MockProvider

    h = harness(settings=EngineSettings(**SAFE))
    h.engine.solver.provider = MockProvider(unsure, latency_s=0.02)
    _ready(h)
    assert h.engine.prediction.uncertain
    h.engine.approve(h.engine.question.question_id)
    ev = h.wait_event("execution")
    assert ev.data["blocked"] == "low_confidence" and "not clicked" in ev.data["message"].lower()
    time.sleep(0.3)
    assert _clicks(h) == [] and h.sim.state.selected == set()


def test_safe_mode_window_moved_since_question_was_read(harness):
    h = harness(settings=EngineSettings(**SAFE))
    _ready(h)
    r = h.engine._frame_rect
    h.engine._frame_rect = Rect(r.x + 40, r.y, r.w, r.h)  # the window was somewhere else when read
    h.engine.approve(h.engine.question.question_id)
    ev = h.wait_event("execution")
    assert ev.data["blocked"] == "window_changed"
    assert _clicks(h) == []


def test_safe_mode_checkbox_not_found(harness, monkeypatch):
    import smart360.vision.extractor as ex

    real = ex._find_checkbox
    monkeypatch.setattr(ex, "_find_checkbox", lambda *a: (real(*a)[0], False))
    h = harness(settings=EngineSettings(**SAFE))
    _ready(h)
    assert not any(a.checkbox_found for a in h.engine.question.answers)
    h.engine.approve(h.engine.question.question_id)
    ev = h.wait_event("execution")
    assert ev.data["blocked"] == "checkbox_not_found"
    assert _clicks(h) == []


def test_safe_mode_does_not_retry_clicks(harness):
    h = harness(settings=EngineSettings(**SAFE))
    _ready(h)
    h.input.fail_next = 1  # first click is lost
    h.engine.approve(h.engine.question.question_id)
    ev = h.wait_event("execution")
    assert not ev.data["ok"] and "not retried" in ev.data["message"]
    assert len(_clicks(h)) <= len(h.sim.displayed_correct())


def test_safe_mode_still_clicks_when_everything_is_certain(harness):
    h = harness(settings=EngineSettings(**SAFE))
    _ready(h)
    h.engine.approve(h.engine.question.question_id)
    ev = h.wait_event("execution")
    assert ev.data["ok"], ev.data
    assert h.sim.is_solved_correctly()


def test_covered_target_is_not_clicked_and_not_retried(harness):
    class Covered(SimulatorInputDriver):
        def click(self, x, y, expected_window=None):
            self.log.append(("blocked", (x, y)))
            raise ClickTargetBlocked("another window covers the answer (hwnd 42)")

    h = harness(settings=EngineSettings(**SAFE))
    h.engine.input = h.input = Covered(h.sim)
    _ready(h)
    h.engine.approve(h.engine.question.question_id)
    ev = h.wait_event("execution")
    assert not ev.data["ok"] and "covers" in ev.data["message"]
    assert ev.data["blocked"] == "covered"
    assert h.sim.state.selected == set()
    assert len([x for x in h.input.log if x[0] == "blocked"]) == 1


# ----------------------------------------------------------------------------- dry run
def test_dry_run_shows_targets_but_never_clicks(harness):
    h = harness(settings=EngineSettings(dry_run=True, **SAFE))
    _ready(h)
    q = h.engine.question
    h.engine.approve(q.question_id)
    ev = h.wait_event("execution")
    assert ev.data["dry_run"] and ev.data["ok"]
    planned = ev.data["clicks"]
    expected = sorted(h.sim.displayed_correct())
    assert sorted(c["answer"] for c in planned) == expected
    for c in planned:
        box = q.answer_by_index(c["answer"]).checkbox
        assert (c["x"], c["y"]) == box.center
    time.sleep(0.4)
    assert _clicks(h) == [] and h.sim.state.selected == set()
    h.wait(lambda: h.history.query()[0].decision is Decision.DRY_RUN, msg="history decision DRY_RUN")


def test_dry_run_reports_covered_target(harness):
    class Covered(SimulatorInputDriver):
        def blocked_reason(self, x, y, expected_window=None):
            return "another window covers the answer (hwnd 7)"

    h = harness(settings=EngineSettings(dry_run=True, **SAFE))
    h.engine.input = h.input = Covered(h.sim)
    _ready(h)
    h.engine.approve(h.engine.question.question_id)
    ev = h.wait_event("execution")
    assert ev.data["dry_run"] and all("covers" in c["blocked"] for c in ev.data["clicks"])
    assert _clicks(h) == []


# ----------------------------------------------------------------------------- emergency stop
def test_emergency_stop_while_waiting_blocks_everything(harness):
    h = harness()
    _ready(h)
    qid = h.engine.question.question_id
    h.engine.emergency_stop()
    assert h.engine.stopped
    h.wait(lambda: h.engine.status == "STOPPED", msg="STOPPED status")
    h.engine.approve(qid)
    time.sleep(0.5)
    assert _clicks(h) == []
    assert h.engine.sm.state.value == "PAUSED"
    assert any(e.kind == "estop" for e in h.events)
    # nothing is captured or analysed while stopped
    h.sim.goto(3)
    time.sleep(0.6)
    assert h.engine.question is None
    h.engine.resume()
    h.wait(lambda: not h.engine.stopped and h.engine.sm.state.value != "PAUSED", msg="resumed")


def test_emergency_stop_during_execution_drops_pending_clicks(harness):
    """Q1 needs two clicks. The stop arrives with the first click: the second is never sent."""

    class StopOnFirstClick(SimulatorInputDriver):
        def click(self, x, y, expected_window=None):
            super().click(x, y, expected_window)
            h.engine.emergency_stop()  # e.g. the user hits the hotkey right now

    h = harness()
    h.engine.input = h.input = StopOnFirstClick(h.sim)
    _ready(h)
    assert len(h.sim.displayed_correct()) == 2
    h.engine.approve(h.engine.question.question_id)
    ev = h.wait_event("execution")
    assert not ev.data["ok"]
    assert len(_clicks(h)) == 1


def test_emergency_stop_drops_running_analysis(harness):
    h = harness(latency=0.8)
    h.engine.start()
    h.wait_state("ANALYZING")
    h.engine.emergency_stop()
    time.sleep(1.4)
    assert h.engine.prediction is None and h.engine.sm.state.value == "PAUSED"
