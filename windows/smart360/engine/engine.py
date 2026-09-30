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
        self._emit(
            "state",
            old=change.old.value,
            new=change.new.value,
            reason=change.reason,
            question_id=change.question_id,
        )

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

    def _resume(self) -> None:
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
        if st is State.PAUSED:
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
        try:
            question, _frame, problem = self._extract(frame_rect, profile)
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
        if question is None:
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

        # Same question re-captured (e.g. user ticked a box manually): keep the prediction.
        if is_same and previous_p is not None and not force:
            self.sm.answer_ready(question.question_id, gen, previous_p.answers or (1,))
            with self._lock:
                self.prediction = previous_p
            self._emit("prediction", prediction=previous_p, question_id=question.question_id)
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
        try:
            self.sm.answer_ready(q.question_id, gen, pred.answers or (1,))
        except TransitionError:
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
        with self._lock:
            self.prediction = pred
        self._history_row = self._add_history(q, pred, Decision.SKIPPED, elapsed_ms)
        self._emit("prediction", prediction=pred, question_id=q.question_id)
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
        self._set_decision(Decision.REJECTED)
        self._emit("stats", **self.stats.as_dict())
        self._set_status("Rejected - waiting for next question")

    def _execute(self, question_id: str, answers: tuple[int, ...] | None) -> None:
        pred = self.prediction
        q = self.question
        try:
            if answers is None and pred is not None and pred.number_answer and not pred.answers:
                answers = (1,)  # placeholder index for number answers; texts carry the real value
            token = self.sm.approve_question(question_id, answers)
        except ApprovalError as e:
            self._emit("execution", ok=False, message=f"Not executed: {e}", question_id=question_id)
            return
        assert q is not None
        self._approved_texts = tuple(
            q.normalized_answers[i - 1] for i in token.answers if 1 <= i <= len(q.answers)
        )
        self.stats.accepted += 1
        t0 = time.perf_counter()
        advisory = (not self.settings.execute_on_confirm) or self.input is None
        if q.question_type is QuestionType.NUMBER_INPUT and not self.settings.number_input:
            advisory = True
        if advisory:
            self.sm.consume_approval(token)
            self.sm.begin_verify(token)
            self.sm.finish_execution(True)
            self._set_decision(Decision.ACCEPTED)
            self._emit(
                "execution",
                ok=True,
                message="Accepted (advisory mode - select it yourself)",
                question_id=question_id,
                advisory=True,
            )
            self._set_status("Accepted")
            return
        ok, message = self._perform(token, q)
        self.health.metrics["exec_ms"].add((time.perf_counter() - t0) * 1000)
        if ok:
            self.health.ok("Input", "last action verified")
            self._set_decision(Decision.ACCEPTED)
        else:
            self.stats.failed += 1
            self.health.failure("Input", message)
            self._set_decision(Decision.FAILED)
        self._emit("execution", ok=ok, message=message, question_id=question_id)
        self._emit("stats", **self.stats.as_dict())
        self._set_status("Done - waiting for next question" if ok else f"Action failed: {message}")

    def _perform(self, token: ApprovalToken, approved_q: Question) -> tuple[bool, str]:
        """Runs in the engine thread. Every step re-validates the token and the screen."""
        assert self.input is not None
        try:
            self.sm.consume_approval(token)
        except ApprovalError as e:
            self._finish(False)
            return False, str(e)
        attempts = 0
        message = "unknown"
        while True:
            attempts += 1
            ok, message, fresh = self._perform_once(token, approved_q)
            if not self.sm.check_token(token):
                # paused / question vanished mid-action: stop immediately
                if self.sm.state in (State.EXECUTING_CONFIRMED_ACTION, State.VERIFYING):
                    self._finish(False)
                return False, "cancelled: question changed or paused"
            self.sm.begin_verify(token)
            if ok:
                verified, message = self._verify(token, approved_q)
                if verified:
                    self._finish(True)
                    if self.settings.auto_advance:
                        self._advance()
                    return True, f"Selected and verified ({attempts} attempt{'s' if attempts > 1 else ''})"
            if fresh is False:  # different question on screen: never retry
                self._finish(False)
                return False, message
            if attempts >= MAX_EXECUTION_ATTEMPTS or not self.sm.retry_execution(token):
                self._finish(False)
                return False, f"{message} (after {attempts} attempts)"
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

    def _perform_once(self, token: ApprovalToken, approved_q: Question) -> tuple[bool, str, bool | None]:
        """One attempt. Returns (clicked_ok, message, same_question?)."""
        try:
            frame_rect = self.target.locate()
        except TargetLost as e:
            return False, f"window lost: {e}", None
        profile = self._profile_for(frame_rect)
        if profile is None:
            return False, "no layout profile", None
        try:
            fresh, frame, _ = self._extract(frame_rect, profile)
        except CaptureError as e:
            return False, f"capture failed: {e}", None
        # 1+2. re-check question id against the visible question
        if fresh is None or not same_question(fresh, approved_q):
            return False, "the visible question changed - nothing was clicked", False
        if not self.sm.check_token(token):
            return False, "approval no longer valid", None
        assert self.input is not None
        # number input (experimental flag)
        if fresh.question_type is QuestionType.NUMBER_INPUT:
            pred = self.prediction
            if not pred or not pred.number_answer:
                return False, "no number to enter", None
            self.input.type_text(pred.number_answer)
            return True, "number entered", True
        assert self.input is not None
        # 3. locate target answers by TEXT in the fresh capture (answer order may differ)
        desired: set[int] = set()
        for text in self._approved_texts:
            match = next((a.index for a in fresh.answers if a.index not in desired and _same(a, text)), None)
            if match is None:
                return False, f"answer not found on screen: {text[:40]}", None
            desired.add(match)
        states = checkbox_states(frame, frame_rect, fresh)
        clicks = []
        for a in fresh.answers:
            want = a.index in desired
            have = states.get(a.index, False) if states else False
            if want != have and (states is not None or want):
                clicks.append(a)
        # 4. click - re-validate the window position right before input
        for a in clicks:
            if not self.sm.check_token(token):
                return False, "approval revoked during action", None
            try:
                if self.target.locate() != frame_rect:
                    return False, "window moved during action", None
            except TargetLost as e:
                return False, f"window lost during action: {e}", None
            assert a.checkbox is not None
            cx, cy = a.checkbox.center
            try:
                self.input.click(cx, cy)
            except Exception as e:
                return False, f"input failed: {e}", None
            time.sleep(0.06)
        time.sleep(self.settings.settle_s)
        return True, "clicked", True

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
            return False, "question changed during verification"
        desired = {a.index for a in fresh.answers if any(_same(a, t) for t in self._approved_texts)}
        states = checkbox_states(frame, frame_rect, fresh)
        if states is None:
            return False, "could not read checkbox state"
        actual = {k for k, v in states.items() if v}
        if actual == desired:
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
