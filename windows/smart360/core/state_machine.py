"""The assistant state machine.

HARD SAFETY RULE
================
No code path may reach ``EXECUTING_CONFIRMED_ACTION`` except
:meth:`AssistantStateMachine.approve_question`, which

* is only valid in ``WAITING_FOR_CONFIRMATION``,
* must name the question id that is *currently* awaiting confirmation,
* must match the current question generation (a newer capture invalidates it),
* mints a single-use :class:`ApprovalToken` that the executor must present.

The generic :meth:`transition` method refuses ``EXECUTING_CONFIRMED_ACTION`` as a
target unconditionally, and the transition table does not list it either, so the
rule holds even if the table is edited carelessly (tests assert both).
"""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum


class State(StrEnum):
    WAITING_FOR_QUESTION = "WAITING_FOR_QUESTION"
    CAPTURING = "CAPTURING"
    ANALYZING = "ANALYZING"
    ANSWER_READY = "ANSWER_READY"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    EXECUTING_CONFIRMED_ACTION = "EXECUTING_CONFIRMED_ACTION"
    VERIFYING = "VERIFYING"
    WAITING_FOR_NEXT_QUESTION = "WAITING_FOR_NEXT_QUESTION"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


S = State

# Every allowed transition except the approval edge. EXECUTING is deliberately absent
# as a target: only approve_question() may enter it.
_TRANSITIONS: dict[State, frozenset[State]] = {
    S.WAITING_FOR_QUESTION: frozenset({S.CAPTURING}),
    S.CAPTURING: frozenset({S.ANALYZING, S.WAITING_FOR_QUESTION}),
    S.ANALYZING: frozenset({S.ANSWER_READY, S.WAITING_FOR_QUESTION, S.CAPTURING}),
    S.ANSWER_READY: frozenset({S.WAITING_FOR_CONFIRMATION, S.CAPTURING}),
    S.WAITING_FOR_CONFIRMATION: frozenset({S.WAITING_FOR_NEXT_QUESTION, S.CAPTURING}),
    S.EXECUTING_CONFIRMED_ACTION: frozenset({S.VERIFYING}),
    S.VERIFYING: frozenset({S.WAITING_FOR_NEXT_QUESTION}),
    S.WAITING_FOR_NEXT_QUESTION: frozenset({S.CAPTURING, S.WAITING_FOR_QUESTION}),
    S.PAUSED: frozenset(),  # only resume() leaves PAUSED
    S.ERROR: frozenset({S.WAITING_FOR_QUESTION}),
}

# States from which pause()/fail() are allowed (all of them).
ALL_STATES = frozenset(State)

MAX_EXECUTION_ATTEMPTS = 3


class TransitionError(RuntimeError):
    """Raised for an illegal transition. Callers treat it as a bug or a lost race."""


class ApprovalError(TransitionError):
    """Approval rejected: wrong state, stale question or mismatching id."""


@dataclass(frozen=True, slots=True)
class ApprovalToken:
    question_id: str
    generation: int
    nonce: str
    answers: tuple[int, ...]
    issued_at: float


@dataclass(frozen=True, slots=True)
class StateChange:
    old: State
    new: State
    reason: str
    question_id: str | None
    at: float = field(default_factory=time.monotonic)


Listener = Callable[[StateChange], None]


class AssistantStateMachine:
    """Thread-safe state machine. All public methods may be called from any thread."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state = S.WAITING_FOR_QUESTION
        self._generation = 0
        self._question_id: str | None = None
        self._pending_answers: tuple[int, ...] | None = None
        self._token: ApprovalToken | None = None
        self._token_consumed = False
        self._attempts = 0
        self._paused_from: State | None = None
        self._listeners: list[Listener] = []
        self._history: list[StateChange] = []

    # ------------------------------------------------------------------ introspection
    @property
    def state(self) -> State:
        with self._lock:
            return self._state

    @property
    def question_id(self) -> str | None:
        with self._lock:
            return self._question_id

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    @property
    def attempts(self) -> int:
        with self._lock:
            return self._attempts

    @property
    def history(self) -> list[StateChange]:
        with self._lock:
            return list(self._history[-200:])

    def add_listener(self, fn: Listener) -> None:
        with self._lock:
            self._listeners.append(fn)

    @staticmethod
    def allowed_targets(state: State) -> frozenset[State]:
        return _TRANSITIONS[state]

    # ------------------------------------------------------------------ core
    def _set(self, new: State, reason: str) -> StateChange:
        change = StateChange(self._state, new, reason, self._question_id)
        self._state = new
        self._history.append(change)
        if len(self._history) > 1000:
            del self._history[:500]
        return change

    def _emit(self, change: StateChange) -> None:
        for fn in list(self._listeners):
            try:
                fn(change)
            except Exception:  # noqa: S112 - a broken listener must never break the FSM
                continue

    def transition(self, target: State, reason: str = "") -> StateChange:
        """Generic transition. Can NEVER enter EXECUTING_CONFIRMED_ACTION."""
        if target is S.EXECUTING_CONFIRMED_ACTION:
            raise TransitionError("EXECUTING_CONFIRMED_ACTION is only reachable via approve_question()")
        with self._lock:
            if target not in _TRANSITIONS[self._state]:
                raise TransitionError(f"illegal transition {self._state} -> {target} ({reason})")
            if target in (S.CAPTURING, S.WAITING_FOR_QUESTION):
                self._invalidate_approval()
            change = self._set(target, reason)
        self._emit(change)
        return change

    def try_transition(self, target: State, reason: str = "") -> bool:
        try:
            self.transition(target, reason)
            return True
        except TransitionError:
            return False

    def _invalidate_approval(self) -> None:
        self._token = None
        self._token_consumed = False
        self._pending_answers = None
        self._attempts = 0

    # ------------------------------------------------------------------ question lifecycle
    def begin_capture(self, reason: str = "change detected") -> int:
        """Enter CAPTURING for a (potentially) new question. Returns the new generation.
        Any outstanding approval is invalidated by the generation bump."""
        with self._lock:
            if S.CAPTURING not in _TRANSITIONS[self._state]:
                raise TransitionError(f"cannot capture from {self._state}")
            self._generation += 1
            self._invalidate_approval()
            change = self._set(S.CAPTURING, reason)
            gen = self._generation
        self._emit(change)
        return gen

    def question_detected(self, question_id: str, generation: int) -> None:
        with self._lock:
            self._require_generation(generation)
            if self._state is not S.CAPTURING:
                raise TransitionError(f"question_detected in {self._state}")
            self._question_id = question_id
            change = self._set(S.ANALYZING, "question detected")
        self._emit(change)

    def answer_ready(self, question_id: str, generation: int, answers: tuple[int, ...]) -> None:
        """Called when a prediction for `question_id` arrives. Stale results raise."""
        with self._lock:
            self._require_generation(generation)
            if self._question_id != question_id:
                raise TransitionError("prediction for a different question")
            if self._state is not S.ANALYZING:
                raise TransitionError(f"answer_ready in {self._state}")
            self._pending_answers = tuple(answers)
            c1 = self._set(S.ANSWER_READY, "prediction ready")
            c2 = self._set(S.WAITING_FOR_CONFIRMATION, "awaiting user confirmation")
        self._emit(c1)
        self._emit(c2)

    def _require_generation(self, generation: int) -> None:
        if generation != self._generation:
            raise TransitionError(f"stale generation {generation} (current {self._generation})")

    # ------------------------------------------------------------------ the one door
    def approve_question(self, question_id: str, answers: tuple[int, ...] | None = None) -> ApprovalToken:
        """The ONLY way into EXECUTING_CONFIRMED_ACTION.

        `answers` lets the user confirm an edited selection; default is the prediction.
        """
        with self._lock:
            if self._state is not S.WAITING_FOR_CONFIRMATION:
                raise ApprovalError(f"nothing awaiting confirmation (state={self._state})")
            if not question_id or question_id != self._question_id:
                raise ApprovalError("approval does not match the question awaiting confirmation")
            chosen = tuple(answers) if answers is not None else self._pending_answers
            if not chosen:
                raise ApprovalError("no answer selected")
            if len(set(chosen)) != len(chosen) or any(a < 1 for a in chosen):
                raise ApprovalError("invalid answer selection")
            self._token = ApprovalToken(
                question_id=question_id,
                generation=self._generation,
                nonce=secrets.token_hex(8),
                answers=chosen,
                issued_at=time.monotonic(),
            )
            self._token_consumed = False
            self._attempts = 0
            change = self._set(S.EXECUTING_CONFIRMED_ACTION, "approved by user")
            token = self._token
        self._emit(change)
        return token

    def consume_approval(self, token: ApprovalToken) -> None:
        """Executor must call this before its first input event. Single use."""
        with self._lock:
            self._check_token(token)
            if self._token_consumed:
                raise ApprovalError("approval token already used")
            self._token_consumed = True

    def check_token(self, token: ApprovalToken) -> bool:
        with self._lock:
            try:
                self._check_token(token)
                return True
            except ApprovalError:
                return False

    def _check_token(self, token: ApprovalToken) -> None:
        if self._state is not S.EXECUTING_CONFIRMED_ACTION:
            raise ApprovalError(f"not executing (state={self._state})")
        cur = self._token
        if cur is None or token != cur:
            raise ApprovalError("unknown approval token")
        if token.generation != self._generation or token.question_id != self._question_id:
            raise ApprovalError("approval is stale")

    def begin_verify(self, token: ApprovalToken) -> int:
        with self._lock:
            self._check_token(token)
            self._attempts += 1
            change = self._set(S.VERIFYING, f"verifying attempt {self._attempts}")
            attempts = self._attempts
        self._emit(change)
        return attempts

    def retry_execution(self, token: ApprovalToken) -> bool:
        """VERIFYING -> EXECUTING again for the SAME approved question, bounded by
        MAX_EXECUTION_ATTEMPTS. This re-uses the existing approval (same question,
        same generation), it is not a new approval."""
        with self._lock:
            if self._state is not S.VERIFYING:
                raise TransitionError(f"retry in {self._state}")
            if self._token is None or token != self._token or token.generation != self._generation:
                raise ApprovalError("retry with stale token")
            if self._attempts >= MAX_EXECUTION_ATTEMPTS:
                return False
            self._token_consumed = False
            change = self._set(S.EXECUTING_CONFIRMED_ACTION, "retry confirmed action")
        self._emit(change)
        return True

    def finish_execution(self, success: bool) -> None:
        with self._lock:
            if self._state not in (S.VERIFYING, S.EXECUTING_CONFIRMED_ACTION):
                raise TransitionError(f"finish_execution in {self._state}")
            self._token = None
            self._token_consumed = False
            if self._state is S.EXECUTING_CONFIRMED_ACTION:
                self._set(S.VERIFYING, "aborted execution")
            change = self._set(S.WAITING_FOR_NEXT_QUESTION, "done" if success else "execution failed")
        self._emit(change)

    def reject(self, question_id: str) -> None:
        with self._lock:
            if self._state is not S.WAITING_FOR_CONFIRMATION or question_id != self._question_id:
                raise ApprovalError("nothing to reject")
            self._invalidate_approval()
            change = self._set(S.WAITING_FOR_NEXT_QUESTION, "rejected by user")
        self._emit(change)

    # ------------------------------------------------------------------ pause / error
    def pause(self) -> None:
        with self._lock:
            if self._state is S.PAUSED:
                return
            self._paused_from = self._state
            # Pausing voids any approval: resuming never continues an execution.
            self._generation += 1
            self._invalidate_approval()
            change = self._set(S.PAUSED, "paused by user")
        self._emit(change)

    def resume(self) -> None:
        with self._lock:
            if self._state is not S.PAUSED:
                return
            self._paused_from = None
            self._question_id = None
            change = self._set(S.WAITING_FOR_QUESTION, "resumed")
        self._emit(change)

    def fail(self, reason: str) -> None:
        with self._lock:
            if self._state is S.PAUSED:
                return  # stay paused, the error is reported via health instead
            self._generation += 1
            self._invalidate_approval()
            change = self._set(S.ERROR, reason)
        self._emit(change)

    def recover(self) -> None:
        with self._lock:
            if self._state is not S.ERROR:
                return
            self._question_id = None
            change = self._set(S.WAITING_FOR_QUESTION, "recovered")
        self._emit(change)

    def reset_to_waiting(self, reason: str) -> None:
        """Abandon the current question (it vanished / window closed) without executing."""
        with self._lock:
            if self._state in (S.PAUSED, S.WAITING_FOR_QUESTION):
                return
            if self._state in (S.EXECUTING_CONFIRMED_ACTION, S.VERIFYING):
                # executor owns these states; it will notice the invalid token
                self._generation += 1
                self._invalidate_approval()
                if self._state is S.EXECUTING_CONFIRMED_ACTION:
                    self._set(S.VERIFYING, reason)
                change = self._set(S.WAITING_FOR_NEXT_QUESTION, reason)
            elif self._state is S.ERROR:
                change = self._set(S.WAITING_FOR_QUESTION, reason)
            else:
                self._generation += 1
                self._invalidate_approval()
                self._question_id = None
                change = self._set(S.WAITING_FOR_QUESTION, reason)
        self._emit(change)
