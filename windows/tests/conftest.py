import os
import shutil
import time

import pytest
from rapidfuzz import fuzz

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from smart360.ai.mock_provider import MockProvider
from smart360.ai.resilience import ResilientSolver
from smart360.capture.change import ChangeDetector, PollingPolicy
from smart360.capture.simulator import PracticeSimulator, simulator_profile
from smart360.capture.targets import SimulatorTarget
from smart360.core.models import normalize_text
from smart360.engine.engine import Engine, EngineSettings
from smart360.engine.input import SimulatorInputDriver
from smart360.health.monitor import HealthMonitor
from smart360.storage.cache import QuestionCache
from smart360.storage.history import HistoryStore
from smart360.vision.extractor import LayoutProfile, QuestionExtractor
from smart360.vision.ocr import TesseractOcr

HAS_TESSERACT = shutil.which("tesseract") is not None
requires_tesseract = pytest.mark.skipif(not HAS_TESSERACT, reason="tesseract binary not installed")


def truth_answer_fn(sim):
    """Mock 'AI' that answers from the simulator's ground truth, mapped by answer text."""

    def fn(req):
        q = sim.question
        if q.number_answer is not None:
            return {
                "answers": [],
                "number_answer": q.number_answer,
                "confidence": 0.95,
                "reason": q.reason,
                "uncertain": False,
                "topic": q.topic,
            }
        # Map each OCR'd answer to the closest ground-truth answer (tolerates OCR noise the way a real
        # model does; exact matching failed on Windows OCR, which read one answer slightly differently).
        truth = [normalize_text(a) for a in q.answers]
        idx = []
        for i, a in enumerate(req.answers, start=1):
            scores = [fuzz.ratio(normalize_text(a), t) for t in truth]
            best = max(range(len(truth)), key=scores.__getitem__)
            if scores[best] >= 70 and best + 1 in q.correct:
                idx.append(i)
        return {
            "answers": idx or [1],
            "number_answer": None,
            "confidence": 0.95,
            "reason": q.reason,
            "uncertain": not idx,
            "topic": q.topic,
        }

    return fn


class Harness:
    def __init__(self, tmp_path, shuffle=False, latency=0.05, settings=None, provider=None):
        self.sim = PracticeSimulator(shuffle=shuffle)
        self.target = SimulatorTarget(self.sim)
        self.input = SimulatorInputDriver(self.sim)
        self.provider = provider or MockProvider(truth_answer_fn(self.sim), latency_s=latency)
        self.solver = ResilientSolver(self.provider, timeout_s=5, max_retries=1, base_backoff_s=0.01)
        self.events = []
        self.health = HealthMonitor()
        self.cache = QuestionCache(tmp_path / "cache.db")
        self.history = HistoryStore(tmp_path / "history.db")
        self.engine = Engine(
            target=self.target,
            extractor=QuestionExtractor(TesseractOcr()),
            solver=self.solver,
            cache=self.cache,
            history=self.history,
            health=self.health,
            input_driver=self.input,
            profiles=[LayoutProfile.from_dict(simulator_profile())],
            settings=settings or EngineSettings(settle_s=0.05),
            detector=ChangeDetector(policy=PollingPolicy(fast_s=0.05, normal_s=0.08, idle_s=0.2)),
            sink=self.events.append,
        )

    def wait_state(self, *states, timeout=20.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.engine.sm.state.value in states:
                return True
            time.sleep(0.02)
        raise AssertionError(
            f"timeout waiting for {states}, state={self.engine.sm.state}, status={self.engine.status}"
        )

    def wait_event(self, kind, timeout=20.0):
        self.wait(lambda: any(e.kind == kind for e in self.events), timeout, f"event {kind}")
        return next(e for e in self.events if e.kind == kind)

    def wait(self, pred, timeout=20.0, msg="condition"):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if pred():
                return
            time.sleep(0.02)
        raise AssertionError(
            f"timeout waiting for {msg}; state={self.engine.sm.state} status={self.engine.status}"
        )

    def close(self):
        self.engine.stop()
        self.cache.close()
        self.history.close()


@pytest.fixture
def harness(tmp_path):
    hs = []

    def make(**kw):
        h = Harness(tmp_path, **kw)
        hs.append(h)
        return h

    yield make
    for h in hs:
        h.close()
