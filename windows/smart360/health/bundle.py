"""'Create diagnosis': one ZIP with everything needed to debug a real-PC session remotely.

Contents: versions/build, Windows + monitors + DPI, the detected learning window, OCR engine, the
current question/prediction/click targets, last state changes, health + errors, self-test, logs, the
per-question session traces (+ question/answer-area images) and the test protocol with metrics.

Never contained: API keys, passwords, tokens or other credentials. Every text file passes through
`redact` (key/token patterns) AND every secret actually stored on this PC is removed verbatim.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from smart360 import BUILD, __version__
from smart360.engine.trace import latest_trace, read_trace
from smart360.health.diagnostics import CheckResult, build_report, run_self_test
from smart360.health.protocol import build_rows, compute_metrics, metrics_text, write_csv
from smart360.platform import win32
from smart360.storage import paths
from smart360.storage.secrets import redact

if TYPE_CHECKING:
    from smart360.services import Services

MAX_TRACE_FILES = 5
MAX_IMAGES = 300
MAX_LOG_BYTES = 3_000_000

README = """360 SMART - diagnosis package
================================
Created: {created}   App: {version} ({build})

Send this ZIP file to the developer as it is. It contains:
  report.json      app/Windows/monitor/DPI info, learning window, OCR engine, current question,
                   confidence values, click targets, last state changes, health, errors, settings
  self_test.txt    result of the built-in self-test
  logs/            the app log files
  trace/           one line per step for every question (capture -> OCR -> AI -> confirmation ->
                   click / no click + reason) and pictures of the question/answer area
  protocol.csv     one row per question (open with Excel) + metrics.txt / metrics.json

NOT contained: API keys, passwords, tokens or other credentials. Pictures show only the question/answer
area of the 360 window, not your whole screen.
"""


def default_output_dir() -> Path:
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    for d in (home / "Desktop", home / "OneDrive" / "Desktop", home / "OneDrive" / "Schreibtisch",
              home / "Schreibtisch"):
        if d.is_dir():
            return d
    out = paths.data_dir() / "diagnostics"
    out.mkdir(exist_ok=True)
    return out


def _secret_values(svc: Services) -> list[str]:
    from smart360.ai.registry import PROVIDERS

    vals = []
    for cls in PROVIDERS.values():
        name = cls.info.key_name
        if not name:
            continue
        try:
            v = svc.secrets.get(name)
        except Exception:
            v = None
        if v and len(v) >= 6:
            vals.append(v)
    return vals


def _scrub(text: str, secrets: list[str]) -> str:
    for v in secrets:
        text = text.replace(v, "[REDACTED]")
    return redact(text)


def system_info(svc: Services) -> dict[str, Any]:
    info: dict[str, Any] = {
        "app_version": __version__,
        "build": BUILD,
        "frozen_exe": bool(getattr(sys, "frozen", False)),
        "windows": win32.windows_version(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(),
        "dpi_awareness": win32.DPI_MODE,
        "monitors": win32.display_info(),
    }
    info["monitor_count"] = len(info["monitors"])
    try:  # Qt view of the screens (logical size + device pixel ratio), when the UI is running
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            info["qt_screens"] = [
                {"name": s.name(), "geometry": [s.geometry().x(), s.geometry().y(), s.geometry().width(),
                                                s.geometry().height()],
                 "device_pixel_ratio": s.devicePixelRatio(), "logical_dpi": s.logicalDotsPerInch()}
                for s in app.screens()  # type: ignore[attr-defined]
            ]
            info["monitor_count"] = max(info["monitor_count"], len(info["qt_screens"]))
    except Exception as e:
        info["qt_screens_error"] = str(e)
    return info


def engine_info(svc: Services) -> dict[str, Any]:
    eng = svc.engine
    if eng is None:
        return {"running": False, "window_probe": _probe_window(svc)}
    out: dict[str, Any] = {
        "running": eng.alive,
        "state": eng.sm.state.value,
        "status": eng.status,
        "emergency_stopped": eng.stopped,
        "safe_mode": eng.settings.safe_mode,
        "dry_run": eng.settings.dry_run,
        "confidence_threshold": eng.settings.confidence_threshold,
        "execute_on_confirm": eng.settings.execute_on_confirm,
        "ocr_engine": eng.extractor.ocr.name,
        "ocr_available": eng.extractor.ocr.available(),
        "input_driver": eng.input.name if eng.input else None,
        "target": {"kind": eng.target.name, "description": eng.target.describe()},
        "profiles": [p.name for p in eng.profiles],
        "forced_profile": eng.forced_profile,
        "last_state_changes": [
            {"t": time.strftime("%H:%M:%S", time.localtime(t)), "from": a, "to": b, "reason": r}
            for t, a, b, r in list(eng.transitions)[-40:]
        ],
        "last_click_targets": list(eng._planned),
    }
    try:
        rect = eng.target.locate()
        out["target"]["window_rect"] = [rect.x, rect.y, rect.w, rect.h]
        prof = eng._profile_for(rect)
        out["target"]["profile_used"] = prof.name if prof else None
        if prof is not None:
            out["target"]["capture_regions"] = {
                k: [r.x, r.y, r.w, r.h]
                for k, n in (("question", prof.question), ("answers", prof.answers), ("image", prof.image))
                if n is not None and (r := n.to_abs(rect))
            }
    except Exception as e:
        out["target"]["window_rect"] = None
        out["target"]["locate_error"] = str(e)
    hwnd = getattr(eng.target, "hwnd", None)
    if hwnd:
        out["target"]["is_foreground"] = win32.foreground_hwnd() == hwnd
    q, p = eng.question, eng.prediction
    if q is not None:
        from smart360.engine.engine import _question_dict

        out["question"] = _question_dict(q)
    if p is not None:
        out["prediction"] = {
            "answers": list(p.answers), "number_answer": p.number_answer, "confidence": p.confidence,
            "model_confidence": p.model_confidence, "uncertain": p.uncertain, "source": p.source.value,
            "model": p.model, "breakdown": dict(p.confidence_breakdown), "reason": p.reason,
        }
    return out


def _probe_window(svc: Services) -> dict[str, Any]:
    """Without a running engine (CLI --diagnose): can the learning window be found right now?"""
    if not win32.IS_WINDOWS:
        return {"available": False, "reason": "not Windows"}
    patterns = tuple(svc.config.detection.title_patterns)
    try:
        candidates = [
            {"title": w.title, "process": w.process, "score": round(win32.score_window(w, patterns), 2)}
            for w in win32.list_windows()
            if win32.score_window(w, patterns) > 0
        ]
        found = win32.find_learning_window(patterns)
        rect = win32.client_rect(found.hwnd) if found else None
        return {
            "title_patterns": list(patterns),
            "candidates": candidates[:10],
            "selected": found.title if found else None,
            "client_rect": [rect.x, rect.y, rect.w, rect.h] if rect else None,
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def create_bundle(
    svc: Services, out_dir: Path | None = None, self_test: list[CheckResult] | None = None
) -> Path:
    out_dir = Path(out_dir) if out_dir else default_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"360SMART-Diagnose-{stamp}.zip"
    secrets = _secret_values(svc)
    results = self_test if self_test is not None else run_self_test(svc)

    def put_text(z: zipfile.ZipFile, name: str, text: str) -> None:
        z.writestr(name, _scrub(text, secrets))

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as z:
        put_text(z, "README.txt", README.format(created=stamp, version=__version__, build=BUILD))
        report = build_report(svc, results)
        report["system"] = system_info(svc)
        report["engine"] = engine_info(svc)
        put_text(z, "report.json", json.dumps(report, indent=2, ensure_ascii=False, default=str))
        put_text(z, "self_test.txt",
                 "\n".join(f"{r.status.upper():5} {r.name:<14} {r.detail} ({r.ms} ms)" for r in results))
        # logs (newest last; size-capped)
        budget = MAX_LOG_BYTES
        for log_file in sorted(paths.log_dir().glob("*.log*"), key=lambda p: p.stat().st_mtime, reverse=True):
            if budget <= 0:
                break
            data = log_file.read_text(encoding="utf-8", errors="replace")[-budget:]
            budget -= len(data)
            put_text(z, f"logs/{log_file.name}", data)
        # traces + images they reference
        tdir = paths.trace_dir()
        traces = sorted(tdir.glob("session-*.jsonl"))[-MAX_TRACE_FILES:]
        images: list[str] = []
        for t in traces:
            put_text(z, f"trace/{t.name}", t.read_text(encoding="utf-8", errors="replace"))
            for e in read_trace(t):
                if e.get("image"):
                    images.append(e["image"])
        for name in list(dict.fromkeys(reversed(images)))[:MAX_IMAGES]:
            f = tdir / name
            if f.is_file():
                z.write(f, f"trace/{name}")
        # protocol of the latest session + metrics
        latest = latest_trace(tdir)
        if latest is not None:
            rows = build_rows(read_trace(latest))
            csv_path = write_csv(rows, tdir / "protocol.csv", keep_manual_from=tdir / "protocol.csv")
            put_text(z, "protocol.csv", csv_path.read_text(encoding="utf-8"))
            from smart360.health.protocol import read_csv

            m = compute_metrics(read_csv(csv_path))
            put_text(z, "metrics.json", json.dumps(m, indent=2))
            put_text(z, "metrics.txt", metrics_text(m))
    return target
