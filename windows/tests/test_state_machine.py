"""State machine tests. The HARD SAFETY RULE is tested three ways:
1. the static transition table,
2. explicit attempts through every public method,
3. a property-based random walk (hypothesis) over all public operations."""

import threading

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from smart360.core.state_machine import (
    _TRANSITIONS,
    MAX_EXECUTION_ATTEMPTS,
    ApprovalError,
    AssistantStateMachine,
    State,
    TransitionError,
)

S = State


def to_confirmation(sm: AssistantStateMachine, qid: str = "q1", answers=(1, 3)) -> int:
    gen = sm.begin_capture()
    sm.question_detected(qid, gen)
    sm.answer_ready(qid, gen, answers)
    assert sm.state is S.WAITING_FOR_CONFIRMATION
    return gen


# ----------------------------------------------------------------------------- static table


def test_table_has_no_edge_into_executing():
    for src, targets in _TRANSITIONS.items():
        assert S.EXECUTING_CONFIRMED_ACTION not in targets, src


def test_every_state_has_table_entry():
    assert set(_TRANSITIONS) == set(State)


# ----------------------------------------------------------------------------- the hard rule


def test_analyzing_cannot_transition_to_executing():
    sm = AssistantStateMachine()
    gen = sm.begin_capture()
    sm.question_detected("q1", gen)
    assert sm.state is S.ANALYZING
    with pytest.raises(TransitionError):
        sm.transition(S.EXECUTING_CONFIRMED_ACTION)
    with pytest.raises(ApprovalError):
        sm.approve_question("q1")
    assert sm.state is S.ANALYZING


@pytest.mark.parametrize("state", list(State))
def test_generic_transition_never_enters_executing(state):
    sm = AssistantStateMachine()
    sm._state = state  # white-box: try from every state
    with pytest.raises(TransitionError):
        sm.transition(S.EXECUTING_CONFIRMED_ACTION)


def test_approve_is_the_only_door():
    sm = AssistantStateMachine()
    to_confirmation(sm)
    token = sm.approve_question("q1")
    assert sm.state is S.EXECUTING_CONFIRMED_ACTION
    assert token.answers == (1, 3)
    sm.consume_approval(token)
    with pytest.raises(ApprovalError):
        sm.consume_approval(token)  # single use


def test_approve_wrong_question_id_rejected():
    sm = AssistantStateMachine()
    to_confirmation(sm, "q1")
    with pytest.raises(ApprovalError):
        sm.approve_question("q2")
    with pytest.raises(ApprovalError):
        sm.approve_question("")
    assert sm.state is S.WAITING_FOR_CONFIRMATION


def test_approval_while_question_changes_is_rejected():
    """Race: user presses ENTER exactly when the next question appears."""
    sm = AssistantStateMachine()
    to_confirmation(sm, "q1")
    sm.begin_capture("question changed")  # engine noticed a change first
    with pytest.raises(ApprovalError):
        sm.approve_question("q1")
    assert sm.state is S.CAPTURING


def test_token_invalid_after_new_capture():
    sm = AssistantStateMachine()
    to_confirmation(sm, "q1")
    token = sm.approve_question("q1")
    sm.reset_to_waiting("window closed")
    assert not sm.check_token(token)
    with pytest.raises(ApprovalError):
        sm.consume_approval(token)


def test_stale_prediction_dropped():
    sm = AssistantStateMachine()
    gen1 = sm.begin_capture()
    sm.question_detected("q1", gen1)
    sm.transition(S.CAPTURING, "question changed during analysis")
    # transition() does not bump generation; begin_capture does - emulate engine behaviour
    sm.reset_to_waiting("x")
    gen2 = sm.begin_capture()
    sm.question_detected("q2", gen2)
    with pytest.raises(TransitionError):
        sm.answer_ready("q1", gen1, (1,))
    with pytest.raises(TransitionError):
        sm.answer_ready("q1", gen2, (1,))  # right generation, wrong question
    sm.answer_ready("q2", gen2, (2,))
    assert sm.state is S.WAITING_FOR_CONFIRMATION


def test_two_ai_responses_only_first_counts():
    sm = AssistantStateMachine()
    gen = sm.begin_capture()
    sm.question_detected("q1", gen)
    sm.answer_ready("q1", gen, (1,))
    with pytest.raises(TransitionError):
        sm.answer_ready("q1", gen, (2,))
    token = sm.approve_question("q1")
    assert token.answers == (1,)


def test_pause_during_analysis_voids_everything():
    sm = AssistantStateMachine()
    gen = sm.begin_capture()
    sm.question_detected("q1", gen)
    sm.pause()
    assert sm.state is S.PAUSED
    with pytest.raises(TransitionError):
        sm.answer_ready("q1", gen, (1,))
    sm.resume()
    assert sm.state is S.WAITING_FOR_QUESTION
    with pytest.raises(ApprovalError):
        sm.approve_question("q1")


def test_pause_during_execution_invalidates_token():
    sm = AssistantStateMachine()
    to_confirmation(sm)
    token = sm.approve_question("q1")
    sm.pause()
    assert not sm.check_token(token)
    sm.resume()
    assert sm.state is S.WAITING_FOR_QUESTION


def test_reject_path():
    sm = AssistantStateMachine()
    to_confirmation(sm)
    sm.reject("q1")
    assert sm.state is S.WAITING_FOR_NEXT_QUESTION
    with pytest.raises(ApprovalError):
        sm.approve_question("q1")


def test_edited_selection():
    sm = AssistantStateMachine()
    to_confirmation(sm, answers=(1,))
    token = sm.approve_question("q1", answers=(2, 3))
    assert token.answers == (2, 3)


@pytest.mark.parametrize("bad", [(), (0,), (1, 1), (-2,)])
def test_invalid_selection(bad):
    sm = AssistantStateMachine()
    to_confirmation(sm)
    with pytest.raises(ApprovalError):
        sm.approve_question("q1", answers=bad)


def test_retry_bounded_by_max_attempts():
    sm = AssistantStateMachine()
    to_confirmation(sm)
    token = sm.approve_question("q1")
    for i in range(MAX_EXECUTION_ATTEMPTS):
        sm.consume_approval(token)
        assert sm.begin_verify(token) == i + 1
        allowed = sm.retry_execution(token)
        assert allowed == (i + 1 < MAX_EXECUTION_ATTEMPTS)
    assert sm.state is S.VERIFYING
    sm.finish_execution(False)
    assert sm.state is S.WAITING_FOR_NEXT_QUESTION


def test_error_and_recover():
    sm = AssistantStateMachine()
    to_confirmation(sm)
    sm.fail("screenshot failed")
    assert sm.state is S.ERROR
    with pytest.raises(ApprovalError):
        sm.approve_question("q1")
    sm.recover()
    assert sm.state is S.WAITING_FOR_QUESTION


def test_listener_exceptions_do_not_break_fsm():
    sm = AssistantStateMachine()
    sm.add_listener(lambda c: 1 / 0)
    to_confirmation(sm)
    assert sm.state is S.WAITING_FOR_CONFIRMATION


def test_concurrent_approvals_only_one_wins():
    sm = AssistantStateMachine()
    to_confirmation(sm)
    wins, errors = [], []
    barrier = threading.Barrier(16)

    def go():
        barrier.wait()
        try:
            wins.append(sm.approve_question("q1"))
        except ApprovalError as e:
            errors.append(e)

    threads = [threading.Thread(target=go) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(wins) == 1 and len(errors) == 15


def test_approve_vs_capture_race_never_executes_stale():
    """Hammer approve and begin_capture concurrently; whenever we end up executing,
    the token must be for the question that is current at that moment."""
    for _ in range(200):
        sm = AssistantStateMachine()
        to_confirmation(sm, "q1")
        result = {}

        def approve():
            try:
                result["token"] = sm.approve_question("q1")
            except ApprovalError:
                pass

        def capture():
            try:
                sm.begin_capture("new question")
            except TransitionError:
                pass

        a, b = threading.Thread(target=approve), threading.Thread(target=capture)
        a.start(), b.start()
        a.join(), b.join()
        if sm.state is S.EXECUTING_CONFIRMED_ACTION:
            assert sm.check_token(result["token"])
        if "token" in result and sm.state is S.CAPTURING:
            assert not sm.check_token(result["token"])


# ----------------------------------------------------------------------------- property based

OPS = st.sampled_from(
    [
        "capture", "detect", "ready", "approve", "approve_wrong", "reject", "verify", "retry",
        "finish_ok", "finish_fail", "pause", "resume", "fail", "recover", "reset", "consume",
        "generic_exec", "generic_random",
    ]
)


@settings(max_examples=400, deadline=None)
@given(st.lists(OPS, min_size=1, max_size=60), st.lists(st.sampled_from(list(State)), min_size=60, max_size=60))
def test_random_walk_never_executes_without_approval(ops, randoms):
    sm = AssistantStateMachine()
    gen = 0
    token = None
    approved_generations: set[int] = set()
    for i, op in enumerate(ops):
        prev = sm.state
        try:
            if op == "capture":
                gen = sm.begin_capture()
            elif op == "detect":
                sm.question_detected(f"q{gen}", gen)
            elif op == "ready":
                sm.answer_ready(f"q{gen}", gen, (1,))
            elif op == "approve":
                token = sm.approve_question(f"q{gen}")
                approved_generations.add(sm.generation)
            elif op == "approve_wrong":
                sm.approve_question("nope")
            elif op == "reject":
                sm.reject(f"q{gen}")
            elif op == "verify" and token:
                sm.begin_verify(token)
            elif op == "retry" and token:
                sm.retry_execution(token)
            elif op == "finish_ok":
                sm.finish_execution(True)
            elif op == "finish_fail":
                sm.finish_execution(False)
            elif op == "pause":
                sm.pause()
            elif op == "resume":
                sm.resume()
            elif op == "fail":
                sm.fail("x")
            elif op == "recover":
                sm.recover()
            elif op == "reset":
                sm.reset_to_waiting("x")
            elif op == "consume" and token:
                sm.consume_approval(token)
            elif op == "generic_exec":
                sm.transition(S.EXECUTING_CONFIRMED_ACTION)
            elif op == "generic_random":
                sm.transition(randoms[i])
        except TransitionError:
            pass
        now = sm.state
        if now is S.EXECUTING_CONFIRMED_ACTION and prev is not S.EXECUTING_CONFIRMED_ACTION:
            # entered executing: must be via approve (from confirmation) or bounded retry (from verifying)
            assert (op == "approve" and prev is S.WAITING_FOR_CONFIRMATION) or (
                op == "retry" and prev is S.VERIFYING
            ), (op, prev)
            assert sm.generation in approved_generations
        if now is S.EXECUTING_CONFIRMED_ACTION:
            assert sm.attempts < MAX_EXECUTION_ATTEMPTS
