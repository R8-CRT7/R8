"""The assistant engine: capture -> detect -> analyse -> await confirmation -> execute -> verify.

Threading model
---------------
* engine thread   - owns the state machine transitions, capture, OCR and execution.
                    Commands from the UI (approve, reject, pause, ...) are queued and
                    processed here, which serialises every decision.
* analysis worker - one thread; cache lookup + AI call. Results are posted back to the
                    engine thread as commands and re-validated (question id + generation)
                    before they may change state. Stale results are dropped.
* UI thread       - never blocks; only enqueues commands and receives events.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from typing import Any

from PIL import Image
from rapidfuzz import fuzz

from smart360.ai.base import ProviderError
from smart360.ai.resilience import ResilientSolver
from smart360.ai.schema import SolveRequest
from smart360.capture.change import ChangeDetector
from smart360.capture.targets import CaptureError, CaptureTarget, TargetLost
from smart360.core.confidence import ConfidenceInputs, composite_confidence
from smart360.core.matching import same_question
from smart360.core.models import (
    Decision,
    HistoryEntry,
    Prediction,
    PredictionSource,
    Question,
    QuestionType,
    Rect,
    normalize_text,
    numeric_tokens,
)
from smart360.core.state_machine import (
    MAX_EXECUTION_ATTEMPTS,
    ApprovalError,
    ApprovalToken,
    AssistantStateMachine,
    State,
    StateChange,
    TransitionError,
)
from smart360.engine.input import InputDriver
from smart360.health.monitor import Health, HealthMonitor
from smart360.storage.cache import QuestionCache
from smart360.storage.history import HistoryStore
from smart360.vision.checkbox import checkbox_states
from smart360.vision.extractor import LayoutProfile, QuestionExtractor, choose_profile

log = logging.getLogger(__name__)


@dataclass
class EngineSettings:
    confidence_threshold: float = 0.75
    execute_on_confirm: bool = True
    cost_saver: bool = True
    png_max_side: int = 1024
    auto_advance: bool = False
    number_input: bool = False
    debug_dir: Any = None  # Path | None - debug screenshots only when set
    settle_s: float = 0.35  # wait after clicks before verifying
    # Conservative mode for the first real-PC tests: no click for uncertain predictions, estimated checkbox
    # positions or a window that moved since the question was read; no click retries.
    safe_mode: bool = False
    dry_run: bool = False  # do everything up to SendInput, report WHERE it would click, click nothing


# blocks after which another attempt cannot help (the same capture gives the same answer)
_NO_RETRY = {"ambiguous", "checkbox_unreadable", "checkbox_not_found", "window_changed", "estop"}


@dataclass
class SessionStats:
    started_at: float = field(default_factory=time.time)
    analyzed: int = 0
    accepted: int = 0
    rejected: int = 0
    rechecks: int = 0
    uncertain: int = 0
    failed: int = 0
    cache_hits: int = 0
    ai_calls: int = 0
    ai_time_ms: float = 0.0
    confidence_sum: float = 0.0

    @property
    def avg_confidence(self) -> float:
        return self.confidence_sum / self.analyzed if self.analyzed else 0.0

    @property
    def avg_ai_ms(self) -> float:
        return self.ai_time_ms / self.ai_calls if self.ai_calls else 0.0

    @property
    def cache_hit_rate(self) -> float:
        return self.cache_hits / self.analyzed if self.analyzed else 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "analyzed": self.analyzed,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "rechecks": self.rechecks,
            "uncertain": self.uncertain,
            "failed": self.failed,
            "cache_hits": self.cache_hits,
            "ai_calls": self.ai_calls,
            "avg_confidence": round(self.avg_confidence, 3),
            "avg_ai_ms": round(self.avg_ai_ms),
            "cache_hit_rate": round(self.cache_hit_rate, 3),
            "session_s": round(time.time() - self.started_at),
        }


@dataclass(frozen=True, slots=True)
class EngineEvent:
    kind: str  # state | question | prediction | status | execution | stats | error
    data: dict[str, Any]


EventSink = Callable[[EngineEvent], None]


class Engine:
    def __init__(
        self,
        target: CaptureTarget,
        extractor: QuestionExtractor,
        solver: ResilientSolver | None,
        cache: QuestionCache,
        history: HistoryStore,
        health: HealthMonitor,
        input_driver: InputDriver | None,
        profiles: list[LayoutProfile],
        settings: EngineSettings | None = None,
        detector: ChangeDetector | None = None,
        sink: EventSink | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.target = target
        self.extractor = extractor
        self.solver = solver
        self.cache = cache
        self.history = history
        self.health = health
        self.input = input_driver
        self.profiles = list(profiles)
        self.forced_profile: str = ""
        self.settings = settings or EngineSettings()
        self.detector = detector or ChangeDetector()
        self.sink = sink
        self.clock = clock
        self.sm = AssistantStateMachine()
        self.sm.add_listener(self._on_state)
        self.stats = SessionStats()

        self._cmds: queue.Queue[tuple[str, tuple]] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = threading.Event()
        self._analysis = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")
        self._lock = threading.RLock()
        # current question context (engine thread only, read under lock by UI snapshot)
        self.question: Question | None = None
        self.prediction: Prediction | None = None
        self._frame_rect: Rect | None = None
        self._history_row: int | None = None
        self._approved_texts: tuple[str, ...] = ()
        self._force_fresh = False
        self._error_backoff = 1.0
        self._error_until = 0.0
        self.last_loop_at = 0.0
        self.status = "Starting"
        self._estop = threading.Event()
        self.tracer: Any = None  # SessionTrace | None - per-question debug trace (diagnostics)
        self.transitions: deque[tuple[float, str, str, str]] = deque(maxlen=100)
        self._t_detect = 0.0
        self._planned: list[dict[str, Any]] = []

    # ================================================================== public API (any thread)
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running.set()
        self._thread = threading.Thread(target=self._run, name="engine", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        self._running.clear()
        self._cmds.put(("stop", ()))
        if self._thread:
            self._thread.join(timeout)
        self._analysis.shutdown(wait=False, cancel_futures=True)
        if self.solver:
            self.solver.shutdown()

    @property
    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def approve(self, question_id: str, answers: tuple[int, ...] | None = None) -> None:
        self._cmds.put(("approve", (question_id, answers)))

    def reject(self, question_id: str) -> None:
        self._cmds.put(("reject", (question_id,)))

    def pause(self) -> None:
        self._cmds.put(("pause", ()))

    def resume(self) -> None:
        self._cmds.put(("resume", ()))

    def emergency_stop(self) -> None:
        """Any thread, takes effect immediately: the approval token is voided under the state-machine lock
        (an execution in progress stops before its next click), nothing is captured, analysed or clicked
        until resume()."""
        self._estop.set()
        try:
            self.sm.pause()
        except Exception:
            log.exception("emergency stop: pause failed")
        self._cmds.put(("estop", ()))

    @property
    def stopped(self) -> bool:
        return self._estop.is_set()

    def toggle_pause(self) -> None:
        self._cmds.put(("toggle_pause", ()))

    def reanalyze(self) -> None:
        self._cmds.put(("reanalyze", ()))

    def replace_solver(self, solver: ResilientSolver | None) -> None:
        self._cmds.put(("solver", (solver,)))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self.sm.state.value,
                "question": self.question,
                "prediction": self.prediction,
                "status": self.status,
                "stats": self.stats.as_dict(),
            }

    # ================================================================== events
    def _emit(self, kind: str, /, **data: Any) -> None:
        if self.sink is None:
            return
        try:
            self.sink(EngineEvent(kind, data))
        except Exception:
            log.exception("event sink failed")

    def _on_state(self, change: StateChange) -> None:
        self.transitions.append((time.time(), change.old.value, change.new.value, change.reason))
        self._emit(
            "state",
            old=change.old.value,
            new=change.new.value,
            reason=change.reason,
            question_id=change.question_id,
        )

    def _trace(self, stage: str, /, **data: Any) -> None:
        if self.tracer is None:
            return
        try:
            self.tracer.record(stage, **data)
        except Exception:
            log.debug("trace failed", exc_info=True)

    def _trace_image(self, question_id: str, stage: str, frame: Image.Image, frame_rect: Rect,
                     profile: LayoutProfile, question: Question | None,
                     marks: list[dict[str, Any]] | None = None) -> str | None:
        if self.tracer is None:
            return None
        try:
            n = self.tracer.number(question_id) or 0
            return self.tracer.image(f"q{n:03d}-{stage}", frame, frame_rect, question, marks,
                                     band=self._band_rect(profile, frame_rect))
        except Exception:
            log.debug("trace image failed", exc_info=True)
            return None

    def _report(self, ok: bool, message: str, question_id: str, /, mode: str = "click",
                blocked: str | None = None, **extra: Any) -> None:
        """One place for every execution outcome: event for the UI + trace line."""
        data = {"ok": ok, "message": message, "question_id": question_id, "mode": mode, "blocked": blocked,
                "dry_run": mode == "dry_run", "clicks": list(self._planned), **extra}
        self._trace("execution", **data)
        self._emit("execution", **data)

    def _set_status(self, text: str) -> None:
        with self._lock:
            changed = text != self.status
            self.status = text
        if changed:
            self._emit("status", text=text)

    # ================================================================== main loop
    def _run(self) -> None:
        interval = 0.2
        while self._running.is_set():
            self.last_loop_at = self.clock()
            try:
                cmd = self._cmds.get(timeout=interval)
            except queue.Empty:
                cmd = None
            try:
                if cmd is not None:
                    if cmd[0] == "stop":
                        break
                    self._handle(cmd)
                    # drain further queued commands before polling again
                    continue
                interval = self._tick()
            except Exception as e:  # the loop must survive anything
                log.exception("engine loop error")
                self.health.failure("Capture", f"engine error: {type(e).__name__}: {e}")
                self._enter_error(f"Internal error: {type(e).__name__}")
                interval = 1.0

    def _handle(self, cmd: tuple[str, tuple]) -> None:
        name, args = cmd
        if name == "approve":
            self._execute(*args)
        elif name == "reject":
            self._reject(*args)
        elif name == "pause":
            self.sm.pause()
            self._set_status("Paused")
        elif name == "resume":
            self._resume()
        elif name == "toggle_pause":
            if self.sm.state is State.PAUSED:
                self._resume()
            else:
                self.sm.pause()
                self._set_status("Paused")
        elif name == "reanalyze":
            self._reanalyze()
        elif name == "analysis_done":
            self._analysis_done(*args)
        elif name == "analysis_failed":
            self._analysis_failed(*args)
        elif name == "solver":
            self.solver = args[0]
        elif name == "estop":
            self._emergency_stopped()

    def _emergency_stopped(self) -> None:
        self._planned = []
        with self._lock:
            self.question, self.prediction = None, None
        self._history_row = None
        self._emit("question", question=None)
        self._trace("estop")
        self._emit("estop")
        self._set_status("STOPPED")

    def _resume(self) -> None:
        self._estop.clear()
        self.sm.resume()
        self.detector.reset()
        self._set_status("Watching for questions")

    def _reanalyze(self) -> None:
        st = self.sm.state
        if st is State.PAUSED:
            return
        if st in (State.EXECUTING_CONFIRMED_ACTION, State.VERIFYING):
            return
        if st is State.ERROR:
            self.sm.recover()
        self.stats.rechecks += 1
        self._force_fresh = True
        self.detector.reset()
        self._error_until = 0.0

    # ------------------------------------------------------------------ polling
    def _tick(self) -> float:
        now = self.clock()
        st = self.sm.state
        if st is State.PAUSED or self._estop.is_set():
            return 0.5
        if st is State.ERROR:
            if now < self._error_until:
                return 0.5
            self.sm.recover()
            self.detector.reset()
            st = self.sm.state

        # 1. where is the learning window?
        try:
            t0 = time.perf_counter()
            frame_rect = self.target.locate()
        except TargetLost as e:
            self.health.set("Capture", Health.DEGRADED, str(e))
            self._abandon_question(f"{e}")
            self._set_status("Looking for the 360° window…")
            return 1.0
        profile = self._profile_for(frame_rect)
        if profile is None:
            self._set_status("Calibration required")
            self.health.set("Vision", Health.DEGRADED, "no layout profile")
            return 1.0

        # 2. cheap change detection on the question + answers band
        try:
            band = self._band_rect(profile, frame_rect)
            band_img = self.target.grab(band)
            self.health.metrics["capture_ms"].add((time.perf_counter() - t0) * 1000)
            self.health.ok("Capture", self.target.describe())
        except CaptureError as e:
            state = self.health.failure("Capture", str(e))
            if state is Health.FAILED:
                self._enter_error("Screen capture failing")
            return 1.0

        changed = self.detector.observe(band_img, now) or self._force_fresh
        if changed and st in (
            State.WAITING_FOR_QUESTION,
            State.WAITING_FOR_NEXT_QUESTION,
            State.WAITING_FOR_CONFIRMATION,
            State.ANALYZING,
            State.ANSWER_READY,
        ):
            self._capture_and_analyze(frame_rect, profile, band_img)
        elif st is State.WAITING_FOR_QUESTION:
            self._set_status("Watching for questions")
        return self.detector.next_interval(now)

    def _band_rect(self, profile: LayoutProfile, frame_rect: Rect) -> Rect:
        q = profile.question.to_abs(frame_rect)
        a = profile.answers.to_abs(frame_rect)
        x0, y0 = min(q.x, a.x), min(q.y, a.y)
        x1, y1 = max(q.x + q.w, a.x + a.w), max(q.y + q.h, a.y + a.h)
        return Rect(x0, y0, x1 - x0, y1 - y0)

    def _profile_for(self, frame_rect: Rect) -> LayoutProfile | None:
        if self.forced_profile:
            for p in self.profiles:
                if p.name == self.forced_profile:
                    return p
        return choose_profile(self.profiles, frame_rect.w, frame_rect.h)

    # ------------------------------------------------------------------ capture + extract
    def _extract(
        self, frame_rect: Rect, profile: LayoutProfile
    ) -> tuple[Question | None, Image.Image, str | None]:
        t0 = time.perf_counter()
        frame = self.target.grab(frame_rect)
        res = self.extractor.extract(frame, frame_rect, profile)
        self.health.metrics["extract_ms"].add((time.perf_counter() - t0) * 1000)
        if "ocr" in res.timings_ms:
            self.health.metrics["ocr_ms"].add(res.timings_ms["ocr"])
        if self.settings.debug_dir is not None:
            self._save_debug(frame)
        return res.question, frame, res.problem

    def _capture_and_analyze(self, frame_rect: Rect, profile: LayoutProfile, band_img: Image.Image) -> None:
        force = self._force_fresh
        self._force_fresh = False
        previous_q, previous_p = self.question, self.prediction
        previous_state = self.sm.state
        gen = self.sm.begin_capture("screen changed" if not force else "recheck requested")
        self._set_status("Reading question…")
        self._t_detect = time.perf_counter()
        try:
            question, frame, problem = self._extract(frame_rect, profile)
        except CaptureError as e:
            self.health.failure("Capture", str(e))
            self.sm.transition(State.WAITING_FOR_QUESTION, "capture failed")
            self.detector.reset()
            return
        except Exception as e:
            self.health.failure("Vision", f"{type(e).__name__}: {e}")
            self.sm.transition(State.WAITING_FOR_QUESTION, "extraction failed")
            return
        self.detector.mark_processed(band_img)
        if self._estop.is_set():
            return
        if question is None:
            self._trace("no_question", problem=problem or "no question visible", window=_r(frame_rect),
                        profile=profile.name, ocr_engine=self.extractor.ocr.name)
            self.health.set(
                "Vision",
                Health.HEALTHY if self.extractor.ocr.available() else Health.DEGRADED,
                problem or "no question",
            )
            self._record_skip(previous_q, previous_p, previous_state)
            with self._lock:
                self.question, self.prediction = None, None
            self.sm.transition(State.WAITING_FOR_QUESTION, problem or "no question visible")
            self._emit("question", question=None)
            self._set_status("Watching for questions")
            return
        self.health.ok("Vision", f"OCR {question.ocr_confidence:.0%}")

        is_same = previous_q is not None and same_question(previous_q, question)
        if is_same:
            assert previous_q is not None
            kept = _with_identity(question, previous_q)
            if kept is None:
                is_same = False  # same question, different answer order -> analyse again (cache remaps)
            else:
                question = kept
        if not is_same:
            self._record_skip(previous_q, previous_p, previous_state)
        with self._lock:
            self.question = question
            if not is_same:
                self.prediction = None
        self._frame_rect = frame_rect
        self.sm.question_detected(question.question_id, gen)
        self._emit("question", question=question)
        self._trace(
            "ocr",
            question_id=question.question_id,
            same_as_before=is_same,
            window=_r(frame_rect),
            profile=profile.name,
            ocr_engine=self.extractor.ocr.name,
            extract_ms=round((time.perf_counter() - self._t_detect) * 1000, 1),
            image=self._trace_image(question.question_id, "detect", frame, frame_rect, profile, question),
            **_question_dict(question),
        )

        # Same question re-captured (e.g. user ticked a box manually): keep the prediction.
        if is_same and previous_p is not None and not force:
            with self._lock:
                self.prediction = previous_p
            self._emit("prediction", prediction=previous_p, question_id=question.question_id)
            self.sm.answer_ready(question.question_id, gen, previous_p.answers or (1,))
            self._set_status("Awaiting your confirmation")
            return
        self._set_status("Analyzing…")
        self._analysis.submit(self._analyze_worker, question, gen, force)

    def _save_debug(self, frame: Image.Image) -> None:
        try:
            d = self.settings.debug_dir
            files = sorted(d.glob("frame-*.png"))
            for old in files[:-49]:
                old.unlink(missing_ok=True)
            frame.save(d / f"frame-{int(time.time() * 1000)}.png")
        except Exception:
            log.debug("debug screenshot failed", exc_info=True)

    # ------------------------------------------------------------------ analysis (worker thread)
    def _analyze_worker(self, q: Question, gen: int, force: bool) -> None:
        t0 = time.perf_counter()
        try:
            pred = None
            if not force:
                pred = self._from_cache(q)
            if pred is None:
                pred = self._from_ai(q)
            self._cmds.put(("analysis_done", (q, gen, pred, (time.perf_counter() - t0) * 1000)))
        except ProviderError as e:
            self._cmds.put(("analysis_failed", (q, gen, e)))
        except Exception as e:
            log.exception("analysis crashed")
            self._cmds.put(
                ("analysis_failed", (q, gen, ProviderError(f"{type(e).__name__}: {e}", True, "server")))
            )

    def _from_cache(self, q: Question) -> Prediction | None:
        try:
            hit = self.cache.lookup(q)
            self.health.ok("Cache", f"{len(self.cache)} entries")
        except Exception as e:
            self.health.failure("Cache", f"lookup failed: {e}")
            return None
        if hit is None:
            return None
        conf = composite_confidence(
            ConfidenceInputs(
                model=hit.confidence,
                ocr=q.ocr_confidence,
                layout=q.layout_confidence,
                image_clarity=q.image_clarity,
                cache_similarity=hit.similarity,
                has_image=q.has_image,
            ),
            self.settings.confidence_threshold,
        )
        return Prediction(
            question_id=q.question_id,
            answers=hit.answers,
            model_confidence=hit.confidence,
            confidence=conf.value,
            reason=hit.reason,
            uncertain=conf.below(self.settings.confidence_threshold),
            source=PredictionSource.CACHE,
            model=hit.model,
            topic=hit.topic,
            number_answer=hit.number_answer,
            confidence_breakdown=tuple(conf.breakdown.items()),
        )

    def _from_ai(self, q: Question) -> Prediction:
        solver = self.solver
        if solver is None:
            raise ProviderError("No AI provider configured", False, "config")
        send_image = q.image_png
        send_q_png = q.question_png
        send_a_png = q.answers_png
        if self.settings.cost_saver and q.ocr_confidence >= 0.85 and q.layout_confidence >= 0.75:
            # OCR text is reliable: send only the situation image (if any), not the text crops
            send_q_png = send_a_png = None
        req = SolveRequest(
            question_text=q.text,
            answers=tuple(a.text for a in q.answers),
            number_question=q.question_type is QuestionType.NUMBER_INPUT,
            question_png=send_q_png,
            answers_png=send_a_png,
            image_png=send_image,
            ocr_confidence=q.ocr_confidence,
        )
        result = solver.solve(req)
        self.health.metrics["ai_ms"].add(result.latency_ms)
        self.health.ok("AI", f"{result.provider} · {result.model}")
        self.health.ok("Network")
        r = result.response
        conf = composite_confidence(
            ConfidenceInputs(
                model=r.confidence,
                ocr=q.ocr_confidence,
                layout=q.layout_confidence,
                image_clarity=q.image_clarity,
                model_uncertain=r.uncertain,
                has_image=q.has_image,
            ),
            self.settings.confidence_threshold,
        )
        pred = Prediction(
            question_id=q.question_id,
            answers=tuple(r.answers),
            model_confidence=r.confidence,
            confidence=conf.value,
            reason=r.reason,
            uncertain=r.uncertain or conf.below(self.settings.confidence_threshold),
            source=PredictionSource.AI if result.provider != "mock" else PredictionSource.MOCK,
            model=result.model,
            topic=r.topic,
            number_answer=r.number_answer,
            latency_ms=result.latency_ms,
            confidence_breakdown=tuple(conf.breakdown.items()),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
        if not pred.uncertain and (pred.answers or pred.number_answer):
            try:
                self.cache.store(
                    q, pred.answers, r.confidence, r.reason, result.model, r.topic, r.number_answer
                )
            except Exception as e:
                self.health.failure("Cache", f"store failed: {e}")
        return pred

    # ------------------------------------------------------------------ analysis results (engine thread)
    def _analysis_done(self, q: Question, gen: int, pred: Prediction, elapsed_ms: float) -> None:
        # Stale check first. All state-machine mutations happen on this (engine) thread, so the check
        # stays valid until answer_ready() below.
        if (
            gen != self.sm.generation
            or self.sm.question_id != q.question_id
            or self.sm.state is not State.ANALYZING
        ):
            log.info("dropping stale prediction for %s", q.question_id)
            return
        # Publish the prediction BEFORE the state change: anyone reacting to WAITING_FOR_CONFIRMATION
        # (overlay, hotkey registration) must already see the matching prediction.
        if self._estop.is_set():
            return
        with self._lock:
            self.prediction = pred
        self._emit("prediction", prediction=pred, question_id=q.question_id)
        self._trace(
            "prediction",
            question_id=q.question_id,
            source=pred.source.value,
            model=pred.model,
            answers=list(pred.answers),
            answer_texts=[a.text for i in pred.answers if (a := q.answer_by_index(i))],
            number_answer=pred.number_answer,
            confidence=round(pred.confidence, 4),
            model_confidence=round(pred.model_confidence, 4),
            confidence_breakdown=dict(pred.confidence_breakdown),
            uncertain=pred.uncertain,
            threshold=self.settings.confidence_threshold,
            reason=pred.reason,
            ai_ms=round(pred.latency_ms, 1),
            latency_ms=round((time.perf_counter() - self._t_detect) * 1000, 1) if self._t_detect else None,
        )
        try:
            self.sm.answer_ready(q.question_id, gen, pred.answers or (1,))
        except TransitionError:
            with self._lock:
                self.prediction = None
            log.info("dropping stale prediction for %s", q.question_id)
            return
        self._error_backoff = 1.0
        self.stats.analyzed += 1
        self.stats.confidence_sum += pred.confidence
        if pred.source is PredictionSource.CACHE:
            self.stats.cache_hits += 1
        else:
            self.stats.ai_calls += 1
            self.stats.ai_time_ms += pred.latency_ms
        if pred.uncertain:
            self.stats.uncertain += 1
        self._history_row = self._add_history(q, pred, Decision.SKIPPED, elapsed_ms)
        self._emit("stats", **self.stats.as_dict())
        self._set_status("Manual check recommended" if pred.uncertain else "Awaiting your confirmation")

    def _analysis_failed(self, q: Question, gen: int, err: ProviderError) -> None:
        if gen != self.sm.generation or self.sm.question_id != q.question_id:
            return  # stale failure, ignore
        kind = err.kind
        comp = "Network" if kind in ("network", "timeout") else "AI"
        self.health.failure(comp, str(err))
        if kind in ("network", "timeout", "unavailable"):
            self.health.set("AI", Health.DEGRADED, "AI offline")
        self._emit("error", message=str(err), kind=kind)
        self._trace("ai_error", question_id=q.question_id, kind=kind, message=str(err))
        self._enter_error(
            "AI OFFLINE" if kind in ("network", "timeout", "unavailable") else f"AI error: {err}"
        )

    def _enter_error(self, message: str) -> None:
        self.sm.fail(message)
        self._error_until = self.clock() + self._error_backoff
        self._error_backoff = min(30.0, self._error_backoff * 2)
        self._set_status(message)

    # ------------------------------------------------------------------ history helpers
    def _add_history(self, q: Question, p: Prediction, decision: Decision, elapsed_ms: float) -> int | None:
        try:
            return self.history.add(
                HistoryEntry(
                    question_id=q.question_id,
                    question_text=q.text,
                    answers=tuple(a.text for a in q.answers),
                    recommended=p.answers,
                    confidence=p.confidence,
                    decision=decision,
                    topic=p.topic,
                    source=p.source.value,
                    processing_ms=elapsed_ms,
                    timestamp=time.time(),
                    uncertain=p.uncertain,
                    ocr_confidence=q.ocr_confidence,
                    model=p.model,
                )
            )
        except Exception as e:
            log.warning("history write failed: %s", e)
            return None

    def _set_decision(self, decision: Decision) -> None:
        if self._history_row is not None:
            try:
                self.history.update_decision(self._history_row, decision)
            except Exception as e:
                log.warning("history update failed: %s", e)
        self._history_row = None

    def _record_skip(self, q: Question | None, p: Prediction | None, state: State) -> None:
        # a prediction shown but never decided stays "skipped" (already the default)
        self._history_row = None

    def _abandon_question(self, reason: str) -> None:
        if self.sm.state in (State.WAITING_FOR_QUESTION, State.PAUSED, State.ERROR):
            return
        self.sm.reset_to_waiting(reason)
        with self._lock:
            self.question, self.prediction = None, None
        self.detector.reset()
        self._emit("question", question=None)

    # ------------------------------------------------------------------ decisions
    def _reject(self, question_id: str) -> None:
        try:
            self.sm.reject(question_id)
        except ApprovalError as e:
            self._emit("error", message=f"Reject ignored: {e}", kind="stale")
            return
        self.stats.rejected += 1
        self._trace("decision", question_id=question_id, decision="rejected")
        self._set_decision(Decision.REJECTED)
        self._emit("stats", **self.stats.as_dict())
        self._set_status("Rejected - waiting for next question")

    def _execute(self, question_id: str, answers: tuple[int, ...] | None) -> None:
        self._planned = []
        if self._estop.is_set():
            self._report(False, "Emergency stop is active - nothing was clicked", question_id,
                         mode="blocked", blocked="estop")
            return
        pred = self.prediction
        q = self.question
        try:
            if answers is None and pred is not None and pred.number_answer and not pred.answers:
                answers = (1,)  # placeholder index for number answers; texts carry the real value
            token = self.sm.approve_question(question_id, answers)
        except ApprovalError as e:
            self._report(False, f"Not executed: {e}", question_id, mode="blocked", blocked="stale")
            return
        assert q is not None
        self._trace("decision", question_id=question_id, decision="approved", answers=list(token.answers))
        self._approved_texts = tuple(
            q.normalized_answers[i - 1] for i in token.answers if 1 <= i <= len(q.answers)
        )
        self.stats.accepted += 1
        t0 = time.perf_counter()
        advisory = (not self.settings.execute_on_confirm) or self.input is None
        if q.question_type is QuestionType.NUMBER_INPUT and not self.settings.number_input:
            advisory = True
        low_conf = (
            not advisory and self.settings.safe_mode and pred is not None and pred.uncertain
        )
        if advisory or low_conf:
            self.sm.consume_approval(token)
            self.sm.begin_verify(token)
            self.sm.finish_execution(True)
            self._set_decision(Decision.ACCEPTED)
            if advisory:
                self._report(True, "Accepted (advisory mode - select it yourself)", question_id,
                             mode="advisory", advisory=True)
                self._set_status("Accepted")
            else:
                assert pred is not None
                self._report(
                    False,
                    f"Not clicked: confidence {pred.confidence:.0%} is below the safety threshold "
                    "(safe mode) - select it yourself if you agree",
                    question_id, mode="blocked", blocked="low_confidence",
                )
                self._set_status("Not clicked (low confidence)")
            return
        ok, message, block = self._perform(token, q)
        self.health.metrics["exec_ms"].add((time.perf_counter() - t0) * 1000)
        dry = self.settings.dry_run
        if ok:
            self.health.ok("Input", "dry run (nothing clicked)" if dry else "last action verified")
            self._set_decision(Decision.DRY_RUN if dry else Decision.ACCEPTED)
        else:
            self.stats.failed += 1
            if block not in ("estop",):
                self.health.failure("Input", message)
            self._set_decision(Decision.FAILED)
        mode = "dry_run" if dry and ok else ("click" if ok else ("blocked" if block else "failed"))
        self._report(ok, message, question_id, mode=mode, blocked=block)
        self._emit("stats", **self.stats.as_dict())
        if self._estop.is_set():
            self._set_status("STOPPED")
        elif dry and ok:
            self._set_status("Dry run - nothing clicked")
        else:
            self._set_status("Done - waiting for next question" if ok else f"Action failed: {message}")

    def _perform(self, token: ApprovalToken, approved_q: Question) -> tuple[bool, str, str | None]:
        """Runs in the engine thread. Every step re-validates the token and the screen.
        Returns (ok, message, block category or None)."""
        assert self.input is not None
        try:
            self.sm.consume_approval(token)
        except ApprovalError as e:
            self._finish(False)
            return False, str(e), "stale"
        max_attempts = 1 if self.settings.safe_mode else MAX_EXECUTION_ATTEMPTS
        attempts = 0
        message = "unknown"
        while True:
            attempts += 1
            ok, message, fresh, block = self._perform_once(token, approved_q)
            if self._estop.is_set():
                if self.sm.state in (State.EXECUTING_CONFIRMED_ACTION, State.VERIFYING):
                    self._finish(False)
                return False, "EMERGENCY STOP - remaining clicks were dropped", "estop"
            if not self.sm.check_token(token):
                # paused / question vanished mid-action: stop immediately
                if self.sm.state in (State.EXECUTING_CONFIRMED_ACTION, State.VERIFYING):
                    self._finish(False)
                return False, "cancelled: question changed or paused", "question_changed"
            if self.settings.dry_run:
                self._finish(ok)
                return ok, message, block
            self.sm.begin_verify(token)
            if ok:
                verified, message = self._verify(token, approved_q)
                if verified:
                    self._finish(True)
                    if self.settings.auto_advance:
                        self._advance()
                    plural = "s" if attempts > 1 else ""
                    return True, f"Selected and verified ({attempts} attempt{plural})", None
                block = "verification_failed"
            if fresh is False:  # different question on screen: never retry
                self._finish(False)
                return False, message, block or "question_changed"
            if block in _NO_RETRY:
                self._finish(False)
                return False, message, block
            if attempts >= max_attempts or not self.sm.retry_execution(token):
                self._finish(False)
                if self.settings.safe_mode:
                    return False, f"{message} - not retried (safe mode)", block
                return False, f"{message} (after {attempts} attempts)", block
            time.sleep(0.25)

    def _finish(self, success: bool) -> None:
        try:
            self.sm.finish_execution(success)
        except TransitionError:
            pass
        # our own clicks changed the screen: take the current band as the new baseline
        try:
            frame_rect = self.target.locate()
            profile = self._profile_for(frame_rect)
            if profile is not None:
                self.detector.mark_processed(self.target.grab(self._band_rect(profile, frame_rect)))
        except (TargetLost, CaptureError):
            self.detector.reset()

    def _perform_once(
        self, token: ApprovalToken, approved_q: Question
    ) -> tuple[bool, str, bool | None, str | None]:
        """One attempt. Returns (clicked_ok, message, same_question?, block category)."""
        self._planned = []
        try:
            frame_rect = self.target.locate()
        except TargetLost as e:
            return False, f"window lost: {e}", None, "window_lost"
        if self.settings.safe_mode and self._frame_rect is not None and frame_rect != self._frame_rect:
            return (False, "window moved or resized since the question was read - nothing was clicked "
                    "(press F9 to re-check)", None, "window_changed")
        profile = self._profile_for(frame_rect)
        if profile is None:
            return False, "no layout profile", None, "no_profile"
        try:
            fresh, frame, _ = self._extract(frame_rect, profile)
        except CaptureError as e:
            return False, f"capture failed: {e}", None, "capture_failed"
        # 1+2. re-check question id against the visible question
        if fresh is None or not same_question(fresh, approved_q):
            self._trace("execute_capture", question_id=approved_q.question_id, same_question=False,
                        **(_question_dict(fresh) if fresh else {"question": None}))
            return False, "the visible question changed - nothing was clicked", False, "question_changed"
        if not self.sm.check_token(token):
            return False, "approval no longer valid", None, "stale"
        assert self.input is not None
        # number input (experimental flag)
        if fresh.question_type is QuestionType.NUMBER_INPUT:
            pred = self.prediction
            if not pred or not pred.number_answer:
                return False, "no number to enter", None, "no_number"
            if self.settings.dry_run:
                return True, f"DRY RUN - would type {pred.number_answer!r}", True, None
            self.input.type_text(pred.number_answer)
            return True, "number entered", True, None
        # 3. locate target answers by TEXT in the fresh capture (answer order may differ); every approved
        #    text must match exactly ONE answer on screen
        desired: set[int] = set()
        for text in self._approved_texts:
            matches = [a.index for a in fresh.answers if _same(a, text)]
            if not matches:
                return False, f"answer not found on screen: {text[:40]}", None, "answer_not_found"
            if len(matches) > 1 or matches[0] in desired:
                msg = f"ambiguous target: '{text[:40]}' matches answers {matches} - nothing was clicked"
                return False, msg, None, "ambiguous"
            desired.add(matches[0])
        states = checkbox_states(frame, frame_rect, fresh)
        if states is None:
            # without a readable state a click cannot be verified, and a retry would toggle the box back
            return False, "checkbox state unreadable - nothing was clicked", None, "checkbox_unreadable"
        clicks = [a for a in fresh.answers if (a.index in desired) != states.get(a.index, False)]
        if self.settings.safe_mode and any(not a.checkbox_found for a in clicks):
            return (False, "checkbox position only estimated (no box found) - nothing was clicked", None,
                    "checkbox_not_found")
        hwnd = getattr(self.target, "hwnd", None)
        for a in clicks:
            assert a.checkbox is not None
            cx, cy = a.checkbox.center
            self._planned.append({"answer": a.index, "x": cx, "y": cy, "text": a.text[:60],
                                  "blocked": self.input.blocked_reason(cx, cy, hwnd) if self.settings.dry_run
                                  else None})
        self._trace(
            "execute_capture",
            question_id=approved_q.question_id,
            same_question=True,
            window=_r(frame_rect),
            checkbox_states={str(k): v for k, v in states.items()},
            planned_clicks=list(self._planned),
            dry_run=self.settings.dry_run,
            image=self._trace_image(approved_q.question_id, "dryrun" if self.settings.dry_run else "execute",
                                    frame, frame_rect, profile, fresh, self._planned),
        )
        if self.settings.dry_run:
            if not clicks:
                return True, "DRY RUN - the approved answers are already selected (no click)", True, None
            where = "; ".join(
                f"answer {c['answer']} at ({c['x']}, {c['y']})"
                + (f" - BLOCKED: {c['blocked']}" if c["blocked"] else "")
                for c in self._planned
            )
            return True, f"DRY RUN - would click {where}", True, None
        # 4. click - re-validate the window position right before input
        for plan in self._planned:
            if self._estop.is_set():
                return False, "EMERGENCY STOP - remaining clicks were dropped", None, "estop"
            if not self.sm.check_token(token):
                return False, "approval revoked during action", None, "stale"
            try:
                if self.target.locate() != frame_rect:
                    return False, "window moved during action", None, "window_moved"
            except TargetLost as e:
                return False, f"window lost during action: {e}", None, "window_lost"
            if self._estop.is_set():  # last check, immediately before SendInput
                return False, "EMERGENCY STOP - remaining clicks were dropped", None, "estop"
            try:
                # WindowTarget knows the learning window: refuse to click if anything covers the answer
                self.input.click(plan["x"], plan["y"], expected_window=hwnd)
                plan["sent"] = True
            except Exception as e:
                blocked = "covered" if "cover" in str(e) else "input_error"
                return False, f"not clicked: {e}", None, blocked
            time.sleep(0.06)
        time.sleep(self.settings.settle_s)
        return True, "clicked", True, None

    def _verify(self, token: ApprovalToken, approved_q: Question) -> tuple[bool, str]:
        """5+6. visual verification: same question, checkbox states match the approval."""
        try:
            frame_rect = self.target.locate()
            profile = self._profile_for(frame_rect)
            if profile is None:
                return False, "no profile"
            fresh, frame, _ = self._extract(frame_rect, profile)
        except (TargetLost, CaptureError) as e:
            return False, f"verification capture failed: {e}"
        if fresh is None or not same_question(fresh, approved_q):
            self._trace("verification", question_id=approved_q.question_id, ok=False, same_question=False)
            return False, "question changed during verification"
        desired = {a.index for a in fresh.answers if any(_same(a, t) for t in self._approved_texts)}
        states = checkbox_states(frame, frame_rect, fresh)
        if states is None:
            self._trace("verification", question_id=approved_q.question_id, ok=False,
                        reason="state unreadable")
            return False, "could not read checkbox state"
        actual = {k for k, v in states.items() if v}
        ok = actual == desired
        self._trace(
            "verification",
            question_id=approved_q.question_id,
            ok=ok,
            expected=sorted(desired),
            seen=sorted(actual),
            image=self._trace_image(approved_q.question_id, "verify", frame, frame_rect, profile, fresh,
                                    self._planned),
        )
        if ok:
            return True, "verified"
        return False, f"selection mismatch (expected {sorted(desired)}, saw {sorted(actual)})"

    def _advance(self) -> None:
        try:
            frame_rect = self.target.locate()
            profile = self._profile_for(frame_rect)
            if profile is not None and profile.action is not None and self.input is not None:
                self.input.click(*profile.action.to_abs(frame_rect).center)
        except Exception as e:
            log.warning("auto-advance failed: %s", e)


def _with_identity(q: Question, previous: Question) -> Question | None:
    """Same visible question re-captured (resize, re-render, manual tick): keep the previous
    identity (texts -> fingerprint/question_id) with the FRESH coordinates. Returns None if the
    answer order changed, because then the previous prediction's indices would be wrong."""
    if len(q.answers) != len(previous.answers):
        return None
    answers = []
    for fresh, prev in zip(q.answers, previous.answers, strict=True):
        if not _same(fresh, normalize_text(prev.text)):
            return None
        answers.append(replace(fresh, text=prev.text))
    return replace(q, text=previous.text, answers=tuple(answers), image_hash=previous.image_hash)


def _same(option, normalized_text: str) -> bool:  # type: ignore[no-untyped-def]
    t = normalize_text(option.text)
    return numeric_tokens(t) == numeric_tokens(normalized_text) and fuzz.ratio(t, normalized_text) >= 92


def _r(r: Rect | None) -> list[int] | None:
    return [r.x, r.y, r.w, r.h] if r is not None else None


def _question_dict(q: Question) -> dict[str, Any]:
    """Trace view of a question: texts, OCR quality and the click targets in screen pixels."""
    return {
        "question": q.text,
        "question_type": q.question_type.value,
        "ocr_confidence": round(q.ocr_confidence, 3),
        "layout_confidence": round(q.layout_confidence, 3),
        "has_image": q.has_image,
        "answers": [
            {
                "index": a.index,
                "text": a.text,
                "ocr_confidence": round(a.ocr_confidence, 3),
                "checkbox": _r(a.checkbox),
                "checkbox_found": a.checkbox_found,
            }
            for a in q.answers
        ],
    }
