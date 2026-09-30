"""Health monitor, metrics and performance watchdog."""

from __future__ import annotations

import logging
import os
import statistics
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

log = logging.getLogger(__name__)


class Health(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


COMPONENTS = ("Capture", "Vision", "AI", "Input", "Cache", "Network", "UI")
_RANK = {Health.HEALTHY: 0, Health.UNKNOWN: 1, Health.RECOVERING: 2, Health.DEGRADED: 3, Health.FAILED: 4}


@dataclass
class ComponentHealth:
    name: str
    state: Health = Health.UNKNOWN
    detail: str = ""
    since: float = field(default_factory=time.time)
    consecutive_failures: int = 0


@dataclass(frozen=True, slots=True)
class ErrorRecord:
    at: float
    component: str
    message: str


class Metric:
    """Rolling window of samples (ms)."""

    def __init__(self, size: int = 200):
        self._d: deque[float] = deque(maxlen=size)
        self._lock = threading.Lock()

    def add(self, v: float) -> None:
        with self._lock:
            self._d.append(v)

    def values(self) -> list[float]:
        with self._lock:
            return list(self._d)

    @property
    def avg(self) -> float:
        v = self.values()
        return statistics.fmean(v) if v else 0.0

    @property
    def p95(self) -> float:
        v = sorted(self.values())
        return v[min(len(v) - 1, int(len(v) * 0.95))] if v else 0.0

    @property
    def last(self) -> float:
        v = self.values()
        return v[-1] if v else 0.0


class HealthMonitor:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.components = {n: ComponentHealth(n) for n in COMPONENTS}
        self.errors: deque[ErrorRecord] = deque(maxlen=200)
        self.metrics: dict[str, Metric] = {
            k: Metric() for k in ("ai_ms", "ocr_ms", "capture_ms", "extract_ms", "ui_lag_ms", "exec_ms")
        }
        self.system: dict[str, float] = {}
        self._listeners: list[Callable[[str, ComponentHealth], None]] = []

    def on_change(self, fn: Callable[[str, ComponentHealth], None]) -> None:
        self._listeners.append(fn)

    def set(self, component: str, state: Health, detail: str = "") -> None:
        with self._lock:
            c = self.components.setdefault(component, ComponentHealth(component))
            changed = c.state != state or c.detail != detail
            if c.state != state:
                c.since = time.time()
            c.state, c.detail = state, detail
            if state is Health.HEALTHY:
                c.consecutive_failures = 0
        if changed:
            for fn in list(self._listeners):
                try:
                    fn(component, c)
                except Exception:
                    log.exception("health listener failed")

    def ok(self, component: str, detail: str = "") -> None:
        self.set(component, Health.HEALTHY, detail)

    def failure(self, component: str, message: str, fatal_after: int = 5) -> Health:
        with self._lock:
            c = self.components.setdefault(component, ComponentHealth(component))
            c.consecutive_failures += 1
            n = c.consecutive_failures
            self.errors.append(ErrorRecord(time.time(), component, message[:300]))
        state = Health.FAILED if n >= fatal_after else (Health.RECOVERING if n > 1 else Health.DEGRADED)
        self.set(component, state, message[:120])
        return state

    def record_error(self, component: str, message: str) -> None:
        with self._lock:
            self.errors.append(ErrorRecord(time.time(), component, message[:300]))

    def overall(self) -> Health:
        with self._lock:
            states = [c.state for n, c in self.components.items() if n != "UI"]
        worst = max(states, key=lambda s: _RANK[s]) if states else Health.UNKNOWN
        return Health.DEGRADED if worst is Health.UNKNOWN and Health.HEALTHY in states else worst

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "overall": self.overall().value,
                "components": {
                    n: {"state": c.state.value, "detail": c.detail} for n, c in self.components.items()
                },
                "metrics": {
                    k: {"avg": round(m.avg, 1), "p95": round(m.p95, 1), "n": len(m.values())}
                    for k, m in self.metrics.items()
                },
                "system": dict(self.system),
                "recent_errors": [
                    {"t": round(e.at), "c": e.component, "m": e.message} for e in list(self.errors)[-25:]
                ],
            }


class PerformanceWatchdog:
    """Samples process CPU/RAM/threads every `interval_s` and detects steady RAM growth."""

    def __init__(
        self, health: HealthMonitor, interval_s: float = 5.0, extra: Callable[[], dict] | None = None
    ):
        self.health = health
        self.interval_s = interval_s
        self.extra = extra
        self.rss_history: deque[tuple[float, float]] = deque(maxlen=720)  # 1h at 5 s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        try:
            import psutil

            self._proc = psutil.Process(os.getpid())
            self._proc.cpu_percent(None)
        except Exception:
            self._proc = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def sample(self) -> dict[str, float]:
        data: dict[str, float] = {"threads": float(threading.active_count())}
        if self._proc is not None:
            try:
                data["cpu_percent"] = round(self._proc.cpu_percent(None), 1)
                data["rss_mb"] = round(self._proc.memory_info().rss / 1e6, 1)
            except Exception:
                pass
        if self.extra:
            try:
                data.update(self.extra())
            except Exception:
                pass
        if "rss_mb" in data:
            self.rss_history.append((time.monotonic(), data["rss_mb"]))
            data["rss_growth_mb_per_h"] = round(self.leak_slope_mb_per_h(), 2)
        self.health.system = data
        return data

    def leak_slope_mb_per_h(self) -> float:
        """Least-squares slope of RSS over the window (MB/hour). Needs >= 10 min of data."""
        pts = list(self.rss_history)
        if len(pts) < 10 or pts[-1][0] - pts[0][0] < 600:
            return 0.0
        t0 = pts[0][0]
        xs = [(t - t0) / 3600 for t, _ in pts]
        ys = [v for _, v in pts]
        mx, my = statistics.fmean(xs), statistics.fmean(ys)
        den = sum((x - mx) ** 2 for x in xs)
        return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / den if den else 0.0

    def _run(self) -> None:
        while not self._stop.wait(self.interval_s):
            data = self.sample()
            if data.get("rss_growth_mb_per_h", 0) > 50:
                self.health.record_error("UI", f"memory growing {data['rss_growth_mb_per_h']} MB/h")
