"""Soak / memory-leak test: runs the full engine loop against the simulator for N minutes.

Every cycle: new question appears -> change detection -> real OCR -> (mock) AI -> approval ->
execution -> verification -> next question. RSS, threads and cache/history sizes are sampled
every 10 s and a least-squares RSS slope is reported.

    python tools/soak.py --minutes 30 --out artifacts/soak
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psutil

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
from smart360.vision.ocr import select_backend


def slope_mb_per_h(samples: list[tuple[float, float]]) -> float:
    xs = [t / 3600 for t, _ in samples]
    ys = [v for _, v in samples]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / den if den else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--out", type=Path, default=Path("artifacts/soak"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    sim = PracticeSimulator(shuffle=True)

    def answer(req):  # type: ignore[no-untyped-def]
        q = sim.question
        if q.number_answer is not None:
            return {"answers": [], "number_answer": q.number_answer, "confidence": 0.9, "reason": q.reason,
                    "uncertain": False, "topic": q.topic}
        correct = {normalize_text(q.answers[i - 1]) for i in q.correct}
        idx = [i for i, a in enumerate(req.answers, 1) if normalize_text(a) in correct]
        return {"answers": idx or [1], "number_answer": None, "confidence": 0.93, "reason": q.reason,
                "uncertain": not idx, "topic": q.topic}

    tmp = Path(tempfile.mkdtemp())
    events: list = []
    lock = threading.Lock()

    def sink(ev):  # type: ignore[no-untyped-def]
        with lock:
            events.append(ev)
            if len(events) > 500:
                del events[:250]

    health = HealthMonitor()
    engine = Engine(
        target=SimulatorTarget(sim),
        extractor=QuestionExtractor(select_backend()),
        solver=ResilientSolver(MockProvider(answer, latency_s=0.05), timeout_s=10),
        cache=QuestionCache(tmp / "c.db"),
        history=HistoryStore(tmp / "h.db"),
        health=health,
        input_driver=SimulatorInputDriver(sim),
        profiles=[LayoutProfile.from_dict(simulator_profile())],
        settings=EngineSettings(settle_s=0.05),
        detector=ChangeDetector(policy=PollingPolicy(fast_s=0.05, normal_s=0.1, idle_s=0.3)),
        sink=sink,
    )
    proc = psutil.Process(os.getpid())
    engine.start()
    start = time.monotonic()
    end = start + args.minutes * 60
    samples: list[tuple[float, float]] = []
    rows = []
    cycles = ok = wrong = 0
    next_sample = start
    last_state_change = time.monotonic()
    last_state = ""
    stuck = 0
    advanced = False
    while time.monotonic() < end:
        st = engine.sm.state.value
        if st != last_state:
            last_state, last_state_change = st, time.monotonic()
            if st != "WAITING_FOR_NEXT_QUESTION":
                advanced = False
        if st == "WAITING_FOR_CONFIRMATION" and engine.question is not None:
            engine.approve(engine.question.question_id)
            time.sleep(0.05)
        elif st == "WAITING_FOR_NEXT_QUESTION" and not advanced:
            # exactly ONE page turn per answered question, then wait until the engine has
            # picked up the new screen (the engine only reacts to *settled* changes)
            cycles += 1
            if sim.is_solved_correctly():
                ok += 1
            elif sim.question.number_answer is None:
                wrong += 1
            sim.next()
            advanced = True
            time.sleep(0.05)
        elif time.monotonic() - last_state_change > 20:
            stuck += 1
            print(f"[stuck] state={st} status={engine.status!r} q={sim.state.index} "
                  f"number={sim.question.number_answer is not None} advanced={advanced}", flush=True)
            engine.reanalyze()
            last_state_change = time.monotonic()
        now = time.monotonic()
        if now >= next_sample:
            rss = proc.memory_info().rss / 1e6
            samples.append((now - start, rss))
            rows.append({"t_s": round(now - start), "rss_mb": round(rss, 1), "threads": threading.active_count(),
                         "cycles": cycles, "cache": len(engine.cache), "history": engine.history.count(),
                         "state": st})
            next_sample = now + 10
        time.sleep(0.02)
    engine.stop()

    warm = [s for s in samples if s[0] >= 120] or samples  # ignore the first 2 min (imports, caches, OCR warm-up)
    report = {
        "minutes": args.minutes,
        "cycles": cycles,
        "correct_selections": ok,
        "wrong_selections": wrong,
        "stuck_recoveries": stuck,
        "rss_start_mb": round(samples[0][1], 1),
        "rss_end_mb": round(samples[-1][1], 1),
        "rss_max_mb": round(max(v for _, v in samples), 1),
        "rss_slope_after_warmup_mb_per_h": round(slope_mb_per_h(warm), 2),
        "threads_end": threading.active_count(),
        "avg_ocr_ms": round(health.metrics["ocr_ms"].avg, 1),
        "avg_exec_ms": round(health.metrics["exec_ms"].avg, 1),
        "errors": len(health.errors),
    }
    with open(args.out / "soak.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (args.out / "soak.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
