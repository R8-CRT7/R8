"""Real-device test protocol: one row per question, built automatically from the session trace.

The automatic columns come from the trace. Four columns can be filled in by the tester (in Excel; they are
kept when the protocol is regenerated): OCR Question Correct, Answers Correct, Expected Answer,
Click Correct (yes/no). Metrics are computed from whatever is available and say how many rows they rest on.
"""

from __future__ import annotations

import csv
import io
import re
import statistics
from pathlib import Path
from typing import Any

COLUMNS = [
    "Question #",
    "Question ID",
    "Question (OCR)",
    "Answers (OCR)",
    "OCR Question Correct",  # manual: yes / no
    "Answers Correct",  # manual: yes / no
    "AI Answer",
    "Expected Answer",  # manual: e.g. 1+3
    "Confidence",
    "Uncertain",
    "User Decision",
    "Mode",  # click / dry_run / blocked / advisory / failed / -
    "Verification Passed",
    "Click Correct",  # manual: yes / no (only for real clicks)
    "Clicks",
    "Latency ms",
    "Error Category",
    "Notes",
    "Image",
]
MANUAL = ("OCR Question Correct", "Answers Correct", "Expected Answer", "Click Correct")


def build_rows(trace: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    order: list[str] = []
    no_question = 0
    for e in trace:
        stage, qid = e.get("stage"), e.get("question_id")
        if stage == "no_question":
            no_question += 1
            continue
        if not qid:
            continue
        if qid not in rows:
            rows[qid] = {c: "" for c in COLUMNS}
            rows[qid]["Question #"] = str(e.get("n") or len(order) + 1)
            rows[qid]["Question ID"] = qid
            rows[qid]["Mode"] = "-"
            order.append(qid)
        r = rows[qid]
        if stage == "ocr":
            r["Question (OCR)"] = e.get("question") or ""
            r["Answers (OCR)"] = " | ".join(f"{a['index']}) {a['text']}" for a in e.get("answers", []))
            r["Image"] = r["Image"] or (e.get("image") or "")
            if any(not a.get("checkbox_found", True) for a in e.get("answers", [])):
                r["Notes"] = _join(r["Notes"], "checkbox position estimated for some answers")
        elif stage == "prediction":
            r["AI Answer"] = e.get("number_answer") or "+".join(str(i) for i in e.get("answers", []))
            r["Confidence"] = f"{e.get('confidence', 0):.3f}"
            r["Uncertain"] = "yes" if e.get("uncertain") else "no"
            if e.get("latency_ms") is not None:
                r["Latency ms"] = f"{e['latency_ms']:.0f}"
        elif stage == "ai_error":
            r["Error Category"] = f"ai_{e.get('kind', 'error')}"
            r["Notes"] = _join(r["Notes"], str(e.get("message", "")))
        elif stage == "decision":
            r["User Decision"] = str(e.get("decision", ""))
        elif stage == "verification":
            r["Verification Passed"] = "yes" if e.get("ok") else "no"
        elif stage == "execute_capture" and e.get("image"):
            r["Image"] = e["image"]
        elif stage == "execution":
            r["Mode"] = str(e.get("mode") or "-")
            if e.get("blocked"):
                r["Error Category"] = str(e["blocked"])
            elif not e.get("ok"):
                r["Error Category"] = r["Error Category"] or "failed"
            clicks = e.get("clicks") or []
            r["Clicks"] = "; ".join(
                f"{c['answer']}@({c['x']},{c['y']})" + (" BLOCKED" if c.get("blocked") else "")
                for c in clicks
            )
            r["Notes"] = _join(r["Notes"], str(e.get("message", "")))
            if r["Mode"] == "click" and not r["Verification Passed"]:
                r["Verification Passed"] = "yes" if e.get("ok") else "no"
    out = [rows[q] for q in order]
    if out and no_question:
        note = f"({no_question} screen changes without a readable question)"
        out[0]["Notes"] = _join(out[0]["Notes"], note)
    return out


def _join(a: str, b: str) -> str:
    return f"{a}; {b}" if a and b else (a or b)


# ----------------------------------------------------------------------------- CSV (Excel-friendly)
def write_csv(rows: list[dict[str, str]], path: Path, keep_manual_from: Path | None = None) -> Path:
    """German Excel opens ';'-separated UTF-8 with BOM directly. Manual columns of an existing file are kept
    (matched by Question ID)."""
    manual: dict[str, dict[str, str]] = {}
    src = keep_manual_from if keep_manual_from is not None else path
    if src.exists():
        for old in read_csv(src):
            manual[old.get("Question ID", "")] = {c: old.get(c, "") for c in MANUAL}
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, delimiter=";", extrasaction="ignore")
    w.writeheader()
    for r in rows:
        row = dict(r)
        for c in MANUAL:
            if manual.get(r["Question ID"], {}).get(c):
                row[c] = manual[r["Question ID"]][c]
        w.writerow(row)
    path.write_text("﻿" + buf.getvalue(), encoding="utf-8")
    return path


def read_csv(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8-sig")
    delim = ";" if text.split("\n", 1)[0].count(";") >= text.split("\n", 1)[0].count(",") else ","
    return list(csv.DictReader(io.StringIO(text), delimiter=delim))


# ----------------------------------------------------------------------------- metrics
_YES = {"yes", "y", "ja", "j", "true", "1", "x", "ok", "richtig"}
_NO = {"no", "n", "nein", "false", "0", "falsch", "wrong"}


def _yn(v: str | None) -> bool | None:
    v = (v or "").strip().lower()
    return True if v in _YES else (False if v in _NO else None)


def _answer_set(v: str | None) -> frozenset[str] | None:
    parts = [p for p in re.split(r"[^0-9A-Za-z]+", (v or "").strip()) if p]
    return frozenset(parts) if parts else None


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def compute_metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    n = len(rows)
    q_rated = [b for r in rows if (b := _yn(r.get("OCR Question Correct"))) is not None]
    a_rated = [b for r in rows if (b := _yn(r.get("Answers Correct"))) is not None]

    def ai_right(r: dict[str, str]) -> bool:
        return _answer_set(r.get("AI Answer")) == _answer_set(r.get("Expected Answer"))

    with_expected = [r for r in rows if _answer_set(r.get("Expected Answer"))]
    ai_correct = [r for r in with_expected if ai_right(r)]

    clicked = [r for r in rows if r.get("Mode") == "click"]
    wrong_clicks = [
        r for r in clicked
        if _yn(r.get("Click Correct")) is False
        or (_answer_set(r.get("Expected Answer")) and not ai_right(r))
        or r.get("Verification Passed") == "no"
    ]

    def e2e_ok(r: dict[str, str]) -> bool:
        return (
            r.get("Mode") == "click"
            and r.get("Verification Passed") == "yes"
            and _yn(r.get("Click Correct")) is not False
            and ai_right(r)
        )

    blocked: dict[str, int] = {}
    for r in rows:
        if r.get("Mode") == "blocked" and r.get("Error Category") not in ("stale", ""):
            blocked[r["Error Category"]] = blocked.get(r["Error Category"], 0) + 1
    lat = sorted(float(r["Latency ms"]) for r in rows if (r.get("Latency ms") or "").strip())
    verified = [r for r in rows if r.get("Verification Passed") in ("yes", "no")]

    return {
        "questions": n,
        "question_ocr_accuracy": _rate(sum(q_rated), len(q_rated)),
        "question_ocr_rated": len(q_rated),
        "answer_ocr_accuracy": _rate(sum(a_rated), len(a_rated)),
        "answer_ocr_rated": len(a_rated),
        "ai_accuracy": _rate(len(ai_correct), len(with_expected)),
        "with_expected_answer": len(with_expected),
        # of all questions with a known correct answer: clicked, verified AND correct
        "end_to_end_success_rate": _rate(sum(e2e_ok(r) for r in with_expected), len(with_expected)),
        "real_clicks": len(clicked),
        "false_click_rate": _rate(len(wrong_clicks), len(clicked)),
        "prevented_unsafe_clicks": sum(blocked.values()),
        "prevented_by_reason": blocked,
        "dry_runs": sum(r.get("Mode") == "dry_run" for r in rows),
        "verification_pass_rate": _rate(sum(r["Verification Passed"] == "yes" for r in verified),
                                        len(verified)),
        "median_latency_ms": round(statistics.median(lat), 1) if lat else None,
        "p95_latency_ms": round(lat[min(len(lat) - 1, int(0.95 * len(lat)))], 1) if lat else None,
    }


def metrics_text(m: dict[str, Any]) -> str:
    def pct(v: float | None, base: int | None = None) -> str:
        if v is None:
            return "n/a (not rated yet)"
        return f"{v * 100:.1f} %" + (f" of {base}" if base is not None else "")

    lines = [
        f"Questions:                 {m['questions']}",
        f"Question OCR accuracy:     {pct(m['question_ocr_accuracy'], m['question_ocr_rated'])}",
        f"Answer OCR accuracy:       {pct(m['answer_ocr_accuracy'], m['answer_ocr_rated'])}",
        f"AI accuracy:               {pct(m['ai_accuracy'], m['with_expected_answer'])}",
        f"End-to-end success rate:   {pct(m['end_to_end_success_rate'], m['with_expected_answer'])}",
        f"Real clicks:               {m['real_clicks']}",
        f"False click rate:          {pct(m['false_click_rate'], m['real_clicks'])}",
        f"Prevented unsafe clicks:   {m['prevented_unsafe_clicks']} {m['prevented_by_reason'] or ''}",
        f"Dry runs:                  {m['dry_runs']}",
        f"Verification pass rate:    {pct(m['verification_pass_rate'])}",
        f"Median latency:            {m['median_latency_ms']} ms",
        f"P95 latency:               {m['p95_latency_ms']} ms",
    ]
    return "\n".join(lines)
