"""Deterministic offline provider for demo mode, tests and chaos testing."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from smart360.ai.base import AIProvider, ProviderError, ProviderInfo
from smart360.ai.schema import SolveRequest, SolveResponse, SolveResult, parse_solve_response

AnswerFn = Callable[[SolveRequest], dict]


class MockProvider(AIProvider):
    info = ProviderInfo(
        id="mock",
        display_name="Demo (offline)",
        default_model="demo-1",
        models=("demo-1",),
        key_name="",
        pricing={"demo-1": (0.0, 0.0)},
    )

    def __init__(self, answer_fn: AnswerFn | None = None, latency_s: float = 0.6,
                 failures: list[ProviderError] | None = None, **_: object):
        super().__init__("demo", "demo-1", 30.0)
        self.answer_fn = answer_fn
        self.latency_s = latency_s
        self.failures = list(failures or [])
        self.calls = 0
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return True

    def solve_question(self, req: SolveRequest) -> SolveResult:
        with self._lock:
            self.calls += 1
            failure = self.failures.pop(0) if self.failures else None
        t0 = time.perf_counter()
        if self.latency_s:
            time.sleep(self.latency_s)
        if failure is not None:
            raise failure
        if self.answer_fn is not None:
            data = self.answer_fn(req)
            resp = parse_solve_response(data, len(req.answers), req.number_question)
        else:
            resp = SolveResponse(answers=[1], number_answer=None, confidence=0.9,
                                 reason="Demo-Antwort (offline).", uncertain=False, topic="Sonstiges")
        return SolveResult(resp, "demo-1", "mock", (time.perf_counter() - t0) * 1000, 800, 60)
