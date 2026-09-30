"""Retry, timeout, circuit breaker, request de-duplication and cost tracking
around any AIProvider."""

from __future__ import annotations

import random
import threading
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from enum import StrEnum

from smart360.ai.base import AIProvider, ProviderError
from smart360.ai.schema import SolveRequest, SolveResult


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 4, cooldown_s: float = 30.0,
                 clock: Callable[[], float] = time.monotonic):
        self.failure_threshold = failure_threshold
        self.cooldown_s = cooldown_s
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()
        self._half_open_inflight = False

    @property
    def state(self) -> BreakerState:
        with self._lock:
            return self._state_unlocked()

    def _state_unlocked(self) -> BreakerState:
        if self._opened_at is None:
            return BreakerState.CLOSED
        if self._clock() - self._opened_at >= self.cooldown_s:
            return BreakerState.HALF_OPEN
        return BreakerState.OPEN

    def allow(self) -> bool:
        with self._lock:
            st = self._state_unlocked()
            if st is BreakerState.CLOSED:
                return True
            if st is BreakerState.HALF_OPEN and not self._half_open_inflight:
                self._half_open_inflight = True  # exactly one probe
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None
            self._half_open_inflight = False

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            self._half_open_inflight = False
            if self._failures >= self.failure_threshold or self._opened_at is not None:
                self._opened_at = self._clock()

    def reset(self) -> None:
        self.record_success()


@dataclass
class CostTracker:
    requests: int = 0
    failures: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_usd: float = 0.0
    latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=200))
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, result: SolveResult, usd: float) -> None:
        with self._lock:
            self.requests += 1
            self.input_tokens += result.input_tokens
            self.output_tokens += result.output_tokens
            self.estimated_usd += usd
            self.latencies_ms.append(result.latency_ms)

    def fail(self) -> None:
        with self._lock:
            self.failures += 1

    @property
    def avg_latency_ms(self) -> float:
        with self._lock:
            return sum(self.latencies_ms) / len(self.latencies_ms) if self.latencies_ms else 0.0

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return {
                "requests": self.requests,
                "failures": self.failures,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "estimated_usd": round(self.estimated_usd, 4),
            }


class AIUnavailable(ProviderError):
    def __init__(self, message: str = "AI offline (circuit open)"):
        super().__init__(message, retryable=False, kind="unavailable")


class ResilientSolver:
    """Thread-safe wrapper. solve() blocks the *calling worker* thread only."""

    def __init__(
        self,
        provider: AIProvider,
        timeout_s: float = 30.0,
        max_retries: int = 2,
        base_backoff_s: float = 0.8,
        breaker: CircuitBreaker | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_workers: int = 3,
    ):
        self.provider = provider
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.base_backoff_s = base_backoff_s
        self.breaker = breaker or CircuitBreaker()
        self.costs = CostTracker()
        self._sleep = sleep
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ai-call")
        self._inflight: dict[str, Future[SolveResult]] = {}
        self._lock = threading.Lock()
        self.last_error: ProviderError | None = None

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def solve(self, req: SolveRequest) -> SolveResult:
        """De-duplicates identical concurrent requests: the second caller waits for the first."""
        key = req.dedup_key
        with self._lock:
            existing = self._inflight.get(key)
            if existing is None:
                fut: Future[SolveResult] = Future()
                self._inflight[key] = fut
                owner = True
            else:
                fut, owner = existing, False
        if not owner:
            return fut.result(timeout=self.timeout_s * (self.max_retries + 2))
        try:
            result = self._solve_with_retries(req)
            fut.set_result(result)
            return result
        except BaseException as e:
            fut.set_exception(e)
            raise
        finally:
            with self._lock:
                self._inflight.pop(key, None)

    def _solve_with_retries(self, req: SolveRequest) -> SolveResult:
        attempt = 0
        while True:
            if not self.breaker.allow():
                raise AIUnavailable()
            try:
                result = self._call_with_timeout(req)
            except ProviderError as e:
                self.last_error = e
                self.costs.fail()
                if e.kind in ("auth", "config"):
                    # not the network's fault - do not open the breaker, surface immediately
                    raise
                self.breaker.record_failure()
                if not e.retryable or attempt >= self.max_retries:
                    raise
                delay = e.retry_after if e.retry_after else self.base_backoff_s * (2**attempt)
                delay = min(delay, 20.0) * (0.8 + 0.4 * random.random())
                attempt += 1
                self._sleep(delay)
                continue
            self.breaker.record_success()
            self.last_error = None
            self.costs.add(result, self.provider.estimate_cost(result.input_tokens, result.output_tokens))
            return result

    def _call_with_timeout(self, req: SolveRequest) -> SolveResult:
        fut = self._pool.submit(self.provider.solve_question, req)
        try:
            return fut.result(timeout=self.timeout_s)
        except FutureTimeout as e:
            fut.cancel()
            raise ProviderError(f"AI timeout after {self.timeout_s:.0f}s", retryable=True, kind="timeout") from e
        except ProviderError:
            raise
        except Exception as e:  # unexpected provider bug -> treat as retryable server error
            raise ProviderError(f"provider crashed: {type(e).__name__}: {e}", retryable=True, kind="server") from e
