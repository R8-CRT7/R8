"""Service container: builds and rewires all non-UI components from the config."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from smart360 import BUILD, __version__
from smart360.ai.base import AIProvider
from smart360.ai.mock_provider import MockProvider
from smart360.ai.registry import PROVIDERS, create_provider
from smart360.ai.resilience import CircuitBreaker, ResilientSolver
from smart360.capture.change import ChangeDetector
from smart360.capture.simulator import PracticeSimulator, simulator_profile
from smart360.capture.targets import CaptureTarget, SimulatorTarget, WindowTarget
from smart360.core.models import normalize_text
from smart360.engine.engine import Engine, EngineSettings, EventSink
from smart360.engine.input import InputDriver, SimulatorInputDriver, Win32InputDriver
from smart360.engine.trace import SessionTrace
from smart360.health.monitor import Health, HealthMonitor, PerformanceWatchdog
from smart360.platform import win32
from smart360.storage import paths
from smart360.storage.cache import QuestionCache
from smart360.storage.config import AppConfig, ConfigStore
from smart360.storage.history import HistoryStore
from smart360.storage.secrets import SecretStore
from smart360.vision.extractor import LayoutProfile, QuestionExtractor
from smart360.vision.ocr import OcrBackend, select_backend

log = logging.getLogger(__name__)


def demo_answer_fn(sim: PracticeSimulator):  # type: ignore[no-untyped-def]
    """Demo 'AI': answers the practice simulator from its ground truth (offline, free)."""

    def fn(req):  # type: ignore[no-untyped-def]
        q = sim.question
        if q.number_answer is not None:
            return {
                "answers": [],
                "number_answer": q.number_answer,
                "confidence": 0.93,
                "reason": q.reason,
                "uncertain": False,
                "topic": q.topic,
            }
        correct = {normalize_text(q.answers[i - 1]) for i in q.correct}
        idx = [i for i, a in enumerate(req.answers, start=1) if normalize_text(a) in correct]
        return {
            "answers": idx or [1],
            "number_answer": None,
            "confidence": 0.94 if idx else 0.4,
            "reason": q.reason,
            "uncertain": not idx,
            "topic": q.topic,
        }

    return fn


@dataclass
class Services:
    store: ConfigStore
    secrets: SecretStore
    health: HealthMonitor
    cache: QuestionCache
    history: HistoryStore
    ocr: OcrBackend
    watchdog: PerformanceWatchdog
    simulator: PracticeSimulator | None = None
    engine: Engine | None = None
    provider: AIProvider | None = None
    solver: ResilientSolver | None = None
    notes: list[str] = field(default_factory=list)
    tracer: SessionTrace | None = None

    @property
    def config(self) -> AppConfig:
        return self.store.config

    # ------------------------------------------------------------------ construction
    @classmethod
    def create(cls, data_dir: Path | None = None, demo: bool | None = None) -> Services:
        if data_dir is not None:
            import os

            os.environ["SMART360_HOME"] = str(data_dir)
        store = ConfigStore(paths.config_path())
        if demo is not None:
            store.config.demo_mode = demo
        health = HealthMonitor()
        if store.recovered:
            health.record_error("UI", store.problem or "config recovered")
        secrets = SecretStore(dotenv=Path.cwd() / ".env")
        cache = QuestionCache(paths.cache_path())
        if cache.recovered_from_corruption:
            health.set("Cache", Health.RECOVERING, "cache rebuilt after corruption")
        history = HistoryStore(paths.history_path(), store_text=store.config.privacy.store_question_text)
        history.purge_older_than(store.config.privacy.history_retention_days)
        ocr = select_backend(store.config.detection.ocr_backend)
        health.set("Vision", Health.HEALTHY if ocr.available() else Health.DEGRADED, f"OCR: {ocr.name}")
        svc = cls(store, secrets, health, cache, history, ocr, PerformanceWatchdog(health))
        svc.watchdog.extra = lambda: {"cache_entries": float(len(svc.cache))}
        return svc

    def profiles(self) -> list[LayoutProfile]:
        out: list[LayoutProfile] = []
        for d in self.config.detection.profiles:
            try:
                out.append(LayoutProfile.from_dict(d))
            except (KeyError, ValueError, TypeError) as e:
                self.health.record_error("Vision", f"invalid profile skipped: {e}")
        if self.config.demo_mode:
            out.append(LayoutProfile.from_dict(simulator_profile()))
        return out

    def build_provider(self) -> AIProvider | None:
        ai = self.config.ai
        if self.config.demo_mode:
            sim = self.simulator
            return MockProvider(demo_answer_fn(sim) if sim else None, latency_s=0.9)
        cls = PROVIDERS[ai.provider]
        key = self.secrets.get(cls.info.key_name) if cls.info.key_name else "n/a"
        if not key and ai.provider != "mock":
            self.health.set("AI", Health.DEGRADED, "API key missing")
            return None
        provider = create_provider(ai.provider, key, ai.model or None, ai.timeout_s)
        if hasattr(provider, "effort"):
            provider.effort = ai.effort  # type: ignore[attr-defined]
        self.health.set("AI", Health.HEALTHY, f"{provider.info.display_name} · {provider.model}")
        return provider

    def build_solver(self) -> ResilientSolver | None:
        self.provider = self.build_provider()
        if self.provider is None:
            return None
        ai = self.config.ai
        return ResilientSolver(
            self.provider,
            timeout_s=ai.timeout_s,
            max_retries=ai.retries,
            breaker=CircuitBreaker(failure_threshold=4, cooldown_s=30),
        )

    def engine_settings(self) -> EngineSettings:
        c = self.config
        return EngineSettings(
            confidence_threshold=c.ai.confidence_threshold,
            execute_on_confirm=c.controls.execute_on_confirm,
            cost_saver=c.ai.cost_saver,
            png_max_side=c.ai.png_max_side,
            auto_advance=c.flags.auto_advance,
            number_input=c.flags.number_input,
            debug_dir=paths.debug_dir() if c.privacy.debug_screenshots else None,
            safe_mode=c.safety.safe_mode,
            dry_run=c.safety.dry_run,
        )

    def session_tracer(self) -> SessionTrace | None:
        """One trace file per app run (kept across engine rebuilds); None when switched off."""
        pv = self.config.privacy
        if not pv.session_trace:
            return None
        if self.tracer is None:
            try:
                self.tracer = SessionTrace(paths.trace_dir(), images=pv.trace_images)
            except OSError as e:
                self.health.record_error("UI", f"session trace unavailable: {e}")
                return None
        self.tracer.images = pv.trace_images
        return self.tracer

    def build_engine(self, sink: EventSink | None) -> Engine:
        target: CaptureTarget
        driver: InputDriver | None
        if self.config.demo_mode:
            self.simulator = self.simulator or PracticeSimulator(shuffle=True)
            target = SimulatorTarget(self.simulator)
            driver = SimulatorInputDriver(self.simulator)
        else:
            target = WindowTarget(tuple(self.config.detection.title_patterns))
            driver = Win32InputDriver() if win32.IS_WINDOWS else None
        self.solver = self.build_solver()
        self.engine = Engine(
            target=target,
            extractor=QuestionExtractor(self.ocr, png_max_side=self.config.ai.png_max_side),
            solver=self.solver,
            cache=self.cache,
            history=self.history,
            health=self.health,
            input_driver=driver,
            profiles=self.profiles(),
            settings=self.engine_settings(),
            detector=ChangeDetector(threshold=self.config.detection.change_threshold),
            sink=sink,
        )
        self.engine.forced_profile = self.config.detection.active_profile
        self.engine.tracer = self.session_tracer()
        self.health.set(
            "Input",
            Health.HEALTHY if driver else Health.DEGRADED,
            driver.name if driver else "advisory only (no input driver on this platform)",
        )
        return self.engine

    def apply_config(self) -> None:
        """Push changed settings into the running engine without restarting it."""
        if self.engine is None:
            return
        self.engine.settings = self.engine_settings()
        self.engine.profiles = self.profiles()
        self.engine.forced_profile = self.config.detection.active_profile
        self.engine.detector.threshold = self.config.detection.change_threshold
        self.engine.tracer = self.session_tracer()
        self.history.store_text = self.config.privacy.store_question_text
        self.solver = self.build_solver()
        self.engine.replace_solver(self.solver)

    def shutdown(self) -> None:
        self.watchdog.stop()
        if self.engine:
            self.engine.stop()
        self.cache.close()
        self.history.close()

    def environment(self) -> dict[str, str]:
        try:
            from PySide6 import __version__ as qt_version
        except ImportError:
            qt_version = "n/a"
        return {
            "app": __version__,
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "qt": qt_version,
            "build": BUILD,
            "ocr": self.ocr.name,
            "secret_store": self.secrets.backend,
        }
