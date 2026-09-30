"""Startup self-test and anonymized diagnostic export."""

from __future__ import annotations

import json
import os
import platform
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from smart360.core.state_machine import ApprovalError, AssistantStateMachine, State, TransitionError
from smart360.platform import win32
from smart360.storage import paths
from smart360.storage.secrets import redact

if TYPE_CHECKING:
    from smart360.services import Services


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    status: str  # ok | warn | fail
    detail: str
    ms: float


def _timed(name: str, fn) -> CheckResult:  # type: ignore[no-untyped-def]
    t0 = time.perf_counter()
    try:
        status, detail = fn()
    except Exception as e:  # a failing check must never crash startup
        status, detail = "fail", f"{type(e).__name__}: {redact(str(e))}"
    return CheckResult(name, status, detail, round((time.perf_counter() - t0) * 1000, 1))


def check_state_machine() -> tuple[str, str]:
    sm = AssistantStateMachine()
    gen = sm.begin_capture()
    sm.question_detected("self-test", gen)
    try:
        sm.transition(State.EXECUTING_CONFIRMED_ACTION)
        return "fail", "ANALYZING -> EXECUTING was allowed"
    except TransitionError:
        pass
    try:
        sm.approve_question("self-test")
        return "fail", "approval without prediction was allowed"
    except ApprovalError:
        pass
    sm.answer_ready("self-test", gen, (1,))
    token = sm.approve_question("self-test")
    sm.consume_approval(token)
    return "ok", "confirmation gate enforced"


def run_self_test(svc: Services) -> list[CheckResult]:
    results: list[CheckResult] = []

    def storage():  # type: ignore[no-untyped-def]
        d = paths.data_dir()
        with tempfile.NamedTemporaryFile(dir=d, delete=True) as f:
            f.write(b"ok")
        return "ok", "writable"

    def config():  # type: ignore[no-untyped-def]
        if svc.store.recovered:
            return "warn", svc.store.problem or "recovered with defaults"
        return "ok", "valid"

    def ai():  # type: ignore[no-untyped-def]
        if svc.config.demo_mode:
            return "ok", "demo provider (offline)"
        from smart360.ai.registry import PROVIDERS

        info = PROVIDERS[svc.config.ai.provider].info
        if not svc.secrets.get(info.key_name):
            return "warn", f"{info.display_name}: API key not set"
        return "ok", f"{info.display_name} configured"

    def capture():  # type: ignore[no-untyped-def]
        if svc.config.demo_mode:
            return "ok", "simulator"
        from smart360.capture.targets import MssGrabber
        from smart360.core.models import Rect

        img = MssGrabber().grab(Rect(0, 0, 8, 8))
        return "ok", f"mss screen capture ({img.width}x{img.height})"

    def vision():  # type: ignore[no-untyped-def]
        if svc.ocr.available():
            return "ok", f"OCR backend: {svc.ocr.name}"
        return "warn", "no OCR backend - vision-only AI fallback"

    def cache():  # type: ignore[no-untyped-def]
        n = len(svc.cache)
        return (
            ("warn", "rebuilt after corruption")
            if svc.cache.recovered_from_corruption
            else ("ok", f"{n} entries")
        )

    def hotkeys():  # type: ignore[no-untyped-def]
        if not win32.IS_WINDOWS:
            return "warn", "global hotkeys only on Windows (in-app shortcuts active)"
        return "ok", "RegisterHotKey available"

    for name, fn in (
        ("Storage", storage),
        ("Config", config),
        ("AI", ai),
        ("Capture", capture),
        ("Vision", vision),
        ("Cache", cache),
        ("State machine", check_state_machine),
        ("Hotkeys", hotkeys),
    ):
        results.append(_timed(name, fn))
    return results


def build_report(svc: Services, self_test: list[CheckResult] | None = None) -> dict:
    """Anonymized technical report. Never contains API keys, question texts or screenshots."""
    cfg = svc.config.model_dump()
    cfg["detection"]["profiles"] = [
        {"name": p.get("name", "?")} for p in cfg["detection"].get("profiles", [])
    ]
    cfg["appearance"]["overlay_pos"] = None
    snap = svc.health.snapshot()
    for e in snap["recent_errors"]:
        e["m"] = redact(e["m"])
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "environment": {**svc.environment(), "os": platform.platform(), "cpu_count": os.cpu_count()},
        "config": cfg,
        "health": snap,
        "session": svc.engine.stats.as_dict() if svc.engine else {},
        "ai_usage": svc.solver.costs.snapshot() if svc.solver else {},
        "cache": {"entries": len(svc.cache), "hit_rate": round(svc.cache.hit_rate, 3)},
        "history_rows": svc.history.count(),
        "self_test": [asdict(r) for r in (self_test or [])],
    }


def export_report(svc: Services, path: Path, self_test: list[CheckResult] | None = None) -> Path:
    report = build_report(svc, self_test)
    text = redact(json.dumps(report, indent=2, default=str, ensure_ascii=False))
    path.write_text(text, encoding="utf-8")
    return path
