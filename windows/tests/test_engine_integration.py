"""End-to-end engine tests on the practice simulator with REAL OCR (tesseract).

These cover the full loop and the race/chaos cases required for release:
confirmation required, no stale execution, pause during analysis, window lost,
AI failures, cache use, verification and retries."""

import time

import pytest

from smart360.ai.base import ProviderError
from smart360.ai.mock_provider import MockProvider
from smart360.core.models import Decision
from smart360.core.state_machine import State
from smart360.engine.engine import EngineSettings

from .conftest import requires_tesseract, truth_answer_fn

pytestmark = requires_tesseract


def test_full_loop_requires_confirmation_and_selects_correct_answers(harness):
    h = harness()
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    pred = h.engine.prediction
    assert pred is not None and pred.answers == h.sim.displayed_correct()
    # NOTHING clicked before confirmation
    time.sleep(0.5)
    assert h.input.log == [] and h.sim.state.selected == set()
    assert h.engine.sm.state is State.WAITING_FOR_CONFIRMATION
    h.engine.approve(h.engine.question.question_id)
    ev = h.wait_event("execution")
    assert ev.data["ok"], ev.data
    assert h.sim.is_solved_correctly()
    h.wait(lambda: h.history.query()[0].decision is Decision.ACCEPTED, msg="history decision ACCEPTED")


def test_next_question_detected_after_answer(harness):
    h = harness()
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    first = h.engine.question.question_id
    h.engine.approve(first)
    h.wait_state("WAITING_FOR_NEXT_QUESTION")
    h.sim.next()
    h.wait(
        lambda: (
            h.engine.question is not None
            and h.engine.question.question_id != first
            and h.engine.sm.state is State.WAITING_FOR_CONFIRMATION
        ),
        msg="second question",
    )
    assert h.engine.prediction.answers == h.sim.displayed_correct()


def test_shuffled_answers_clicked_by_text(harness):
    h = harness(shuffle=True)
    h.engine.start()
    for _ in range(3):
        h.wait_state("WAITING_FOR_CONFIRMATION")
        h.engine.approve(h.engine.question.question_id)
        h.wait_state("WAITING_FOR_NEXT_QUESTION")
        assert h.sim.is_solved_correctly(), h.sim.state
        h.sim.next()
        if h.sim.question.number_answer is not None:
            h.sim.next()
        h.wait_state("ANALYZING", "WAITING_FOR_CONFIRMATION", "CAPTURING")


def test_confirmation_exactly_when_question_changes_is_not_executed(harness):
    h = harness()
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    old_id = h.engine.question.question_id
    h.sim.next()  # screen changes...
    h.engine.approve(old_id)  # ...while the user presses ENTER for the old question
    time.sleep(1.5)
    # the old approval must never click anything on the new question
    assert h.sim.state.selected == set()
    assert not any(e.kind == "execution" and e.data.get("ok") for e in h.events)


def test_question_changes_between_approval_and_click(harness):
    """The approval is valid, but the screen changes before the executor re-checks it."""
    h = harness()
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    qid = h.engine.question.question_id
    orig = h.engine._extract

    def swapped(frame_rect, profile):
        h.sim.next()  # change right before the executor's fresh capture
        h.engine._extract = orig
        return orig(frame_rect, profile)

    h.engine._extract = swapped
    h.engine.approve(qid)
    h.wait(lambda: any(e.kind == "execution" for e in h.events), msg="execution event")
    ev = next(e for e in h.events if e.kind == "execution")
    assert not ev.data["ok"] and "changed" in ev.data["message"]
    assert h.input.log == []


def test_approve_wrong_id_does_nothing(harness):
    h = harness()
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    h.engine.approve("not-the-question")
    time.sleep(0.5)
    assert h.input.log == []
    assert h.engine.sm.state is State.WAITING_FOR_CONFIRMATION


def test_pause_during_analysis_drops_result(harness):
    h = harness(latency=1.0)
    h.engine.start()
    h.wait_state("ANALYZING")
    h.engine.pause()
    h.wait_state("PAUSED")
    time.sleep(1.5)  # analysis finishes while paused
    assert h.engine.sm.state is State.PAUSED
    h.engine.resume()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    assert h.input.log == []


def test_window_disappears_during_analysis(harness):
    h = harness(latency=0.8)
    h.engine.start()
    h.wait_state("ANALYZING")
    h.sim.visible = False
    h.wait_state("WAITING_FOR_QUESTION")
    time.sleep(1.2)
    assert h.engine.sm.state is State.WAITING_FOR_QUESTION
    h.sim.visible = True
    h.wait_state("WAITING_FOR_CONFIRMATION")


def test_window_disappears_during_click(harness):
    h = harness()
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    real_click = h.input.click

    def vanish(x, y, expected_window=None):
        h.sim.visible = False
        real_click(x, y)

    h.input.click = vanish
    h.engine.approve(h.engine.question.question_id)
    h.wait(lambda: any(e.kind == "execution" for e in h.events), msg="execution")
    ev = next(e for e in h.events if e.kind == "execution")
    assert not ev.data["ok"]
    assert h.engine.sm.state is not State.EXECUTING_CONFIRMED_ACTION


def test_window_moved_and_resized(harness):
    h = harness()
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    h.sim.move(300, 200)
    h.sim.resize(1440, 900)
    time.sleep(0.8)
    h.wait_state("WAITING_FOR_CONFIRMATION")
    h.engine.approve(h.engine.question.question_id)
    h.wait_state("WAITING_FOR_NEXT_QUESTION")
    assert h.sim.is_solved_correctly()


def test_lost_click_is_retried_and_verified(harness):
    h = harness()
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    h.input.fail_next = 1  # first click swallowed
    h.engine.approve(h.engine.question.question_id)
    ev = h.wait_event("execution")
    assert h.sim.is_solved_correctly()
    assert ev.data["ok"] and "2 attempts" in ev.data["message"]


def test_max_three_attempts(harness):
    h = harness()
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    h.input.fail_next = 99
    h.engine.approve(h.engine.question.question_id)
    h.wait(lambda: any(e.kind == "execution" for e in h.events), timeout=30, msg="execution")
    ev = next(e for e in h.events if e.kind == "execution")
    assert not ev.data["ok"] and "3 attempts" in ev.data["message"]
    # at most 3 attempts x number of needed clicks
    assert len([x for x in h.input.log if x[0] == "click"]) <= 3 * len(h.sim.displayed_correct())
    h.wait(lambda: h.history.query()[0].decision is Decision.FAILED, msg="history decision FAILED")


def test_reject(harness):
    h = harness()
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    h.engine.reject(h.engine.question.question_id)
    h.wait_state("WAITING_FOR_NEXT_QUESTION")
    assert h.input.log == []
    h.wait(lambda: h.history.query()[0].decision is Decision.REJECTED, msg="history decision REJECTED")


def test_manual_tick_keeps_prediction_and_exec_fixes_selection(harness):
    """User ticks a wrong box manually; the prediction survives, execution sets the exact selection."""
    h = harness()
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    calls = h.provider.calls
    wrong = next(i for i in (1, 2, 3) if i not in h.sim.displayed_correct())
    h.sim.state.selected.add(wrong)
    h.sim._frame = None
    time.sleep(1.0)
    h.wait_state("WAITING_FOR_CONFIRMATION")
    assert h.provider.calls == calls  # no new AI call
    h.engine.approve(h.engine.question.question_id)
    h.wait_state("WAITING_FOR_NEXT_QUESTION")
    assert h.sim.is_solved_correctly()


def test_cache_hit_on_second_visit(harness):
    h = harness()
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    h.engine.reject(h.engine.question.question_id)
    h.wait_state("WAITING_FOR_NEXT_QUESTION")
    h.sim.next()
    h.wait(
        lambda: (
            h.engine.question
            and h.engine.sm.state is State.WAITING_FOR_CONFIRMATION
            and h.engine.question.text.startswith("Was bedeutet")
        ),
        msg="q2",
    )
    calls = h.provider.calls
    h.sim.goto(0)
    h.wait(
        lambda: (
            h.engine.sm.state is State.WAITING_FOR_CONFIRMATION
            and h.engine.prediction
            and h.engine.prediction.source.value == "cache"
        ),
        msg="cache hit",
    )
    assert h.provider.calls == calls


def test_recheck_bypasses_cache(harness):
    h = harness()
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    calls = h.provider.calls
    h.engine.reanalyze()
    h.wait(lambda: h.provider.calls == calls + 1, msg="fresh AI call")
    h.wait_state("WAITING_FOR_CONFIRMATION")
    assert h.engine.stats.rechecks == 1


def test_ai_offline_then_recovers(harness, tmp_path):
    from .conftest import Harness

    failures = [ProviderError("net", True, "network")] * 4
    h = Harness(tmp_path, provider=MockProvider(None, latency_s=0.01, failures=failures))
    h.provider.answer_fn = truth_answer_fn(h.sim)
    h.solver.breaker.cooldown_s = 1.0  # production default is 30 s
    try:
        h.engine.start()
        h.wait_state("ERROR")
        assert "OFFLINE" in h.engine.status
        h.wait_state("WAITING_FOR_CONFIRMATION", timeout=30)
        assert h.input.log == []
    finally:
        h.close()


def test_invalid_json_from_ai_is_not_executed(harness, tmp_path):
    from .conftest import Harness

    h = Harness(
        tmp_path, provider=MockProvider(lambda req: {"answers": [9], "confidence": 2}, latency_s=0.01)
    )
    try:
        h.engine.start()
        h.wait_state("ERROR")
        h.engine.approve(h.engine.sm.question_id or "x")
        time.sleep(0.5)
        assert h.input.log == []
    finally:
        h.close()


def test_screenshot_failures_are_contained(harness):
    h = harness()
    h.target.fail_next = 3
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    assert any(e.component == "Capture" for e in h.health.errors)


def test_advisory_mode_never_clicks(harness):
    h = harness(settings=EngineSettings(execute_on_confirm=False, settle_s=0.05))
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    h.engine.approve(h.engine.question.question_id)
    h.wait_state("WAITING_FOR_NEXT_QUESTION")
    assert h.input.log == []
    h.wait(lambda: h.history.query()[0].decision is Decision.ACCEPTED, msg="history decision ACCEPTED")


def test_hotkey_spam_executes_once(harness):
    h = harness()
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    qid = h.engine.question.question_id
    for _ in range(25):
        h.engine.approve(qid)
        h.engine.toggle_pause()
        h.engine.toggle_pause()
    time.sleep(3)
    executions = [e for e in h.events if e.kind == "execution" and e.data.get("ok")]
    assert len(executions) <= 1
    assert len([x for x in h.input.log if x[0] == "click"]) <= 3 * len(h.sim.displayed_correct())


def test_engine_survives_internal_exception(harness):
    h = harness()
    original = h.engine._tick
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return original()

    h.engine._tick = flaky
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION", timeout=25)
    assert h.engine.alive


@pytest.mark.parametrize("n", [3])
def test_number_question_is_advisory_by_default(harness, n):
    h = harness()
    h.sim.goto(7)
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    assert h.engine.prediction.number_answer == "40"
    h.engine.approve(h.engine.question.question_id)
    h.wait_state("WAITING_FOR_NEXT_QUESTION")
    assert h.input.log == []
