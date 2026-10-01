"""Real-device diagnostics: session trace, test protocol + metrics, and the 'Create diagnosis' ZIP
(which must never contain API keys, passwords or tokens)."""

import json
import zipfile

import pytest

from smart360.engine.engine import EngineSettings
from smart360.engine.trace import SessionTrace, latest_trace, read_trace
from smart360.health.protocol import build_rows, compute_metrics, metrics_text, read_csv, write_csv

from .conftest import requires_tesseract

FAKE_KEY = "sk-ant-api03-THIS-IS-A-FAKE-KEY-0123456789abcdef"
FAKE_PASSWORD = "hunter2-very-private"


# ----------------------------------------------------------------------------- trace (engine, real OCR)
@requires_tesseract
@pytest.mark.parametrize("dry_run", [True, False])
def test_trace_records_every_stage_per_question(harness, tmp_path, dry_run):
    h = harness(settings=EngineSettings(safe_mode=True, dry_run=dry_run, settle_s=0.05))
    h.engine.tracer = SessionTrace(tmp_path / "trace")
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    h.engine.approve(h.engine.question.question_id)
    h.wait_event("execution")
    lines = read_trace(latest_trace(tmp_path / "trace"))
    stages = [e["stage"] for e in lines]
    for s in ("ocr", "prediction", "decision", "execute_capture", "execution"):
        assert s in stages, stages
    assert ("verification" in stages) is (not dry_run)
    ocr = next(e for e in lines if e["stage"] == "ocr")
    assert ocr["n"] == 1 and ocr["ocr_engine"] == "tesseract" and ocr["window"]
    assert all(a["checkbox"] and a["checkbox_found"] for a in ocr["answers"])
    pred = next(e for e in lines if e["stage"] == "prediction")
    assert pred["confidence"] > 0 and pred["latency_ms"] > 0 and pred["confidence_breakdown"]
    ex = next(e for e in lines if e["stage"] == "execution")
    assert ex["mode"] == ("dry_run" if dry_run else "click") and ex["ok"]
    assert len(ex["clicks"]) == len(h.sim.displayed_correct())
    # pictures of the question/answer area exist for the referenced steps
    for e in lines:
        if e.get("image"):
            assert (tmp_path / "trace" / e["image"]).is_file()
    rows = build_rows(lines)
    assert len(rows) == 1
    r = rows[0]
    assert r["Mode"] == ("dry_run" if dry_run else "click")
    assert r["AI Answer"] == "+".join(str(i) for i in h.engine.prediction.answers)
    assert r["Verification Passed"] == ("" if dry_run else "yes")
    assert r["Latency ms"] and r["Clicks"] and r["Image"]


@requires_tesseract
def test_trace_records_blocked_click_reason(harness, tmp_path, monkeypatch):
    monkeypatch.setattr("smart360.engine.engine.checkbox_states", lambda *a, **k: None)
    h = harness(settings=EngineSettings(safe_mode=True, settle_s=0.05))
    h.engine.tracer = SessionTrace(tmp_path / "trace")
    h.engine.start()
    h.wait_state("WAITING_FOR_CONFIRMATION")
    h.engine.approve(h.engine.question.question_id)
    h.wait_event("execution")
    rows = build_rows(read_trace(latest_trace(tmp_path / "trace")))
    assert rows[0]["Mode"] == "blocked" and rows[0]["Error Category"] == "checkbox_unreadable"
    assert "nothing was clicked" in rows[0]["Notes"]


def test_trace_survives_truncated_line(tmp_path):
    t = SessionTrace(tmp_path)
    t.record("ocr", question_id="q1", question="Wer?")
    with t.path.open("a") as f:
        f.write('{"stage": "predic')  # app killed mid-write
    assert [e["stage"] for e in read_trace(t.path)] == ["ocr"]


# ----------------------------------------------------------------------------- protocol + metrics
def _row(n, mode="click", ai="1+3", expected="", verified="yes", click_ok="", q_ok="", a_ok="", lat="900",
         cat=""):
    return {"Question #": str(n), "Question ID": f"q{n}", "Mode": mode, "AI Answer": ai,
            "Expected Answer": expected, "Verification Passed": verified, "Click Correct": click_ok,
            "OCR Question Correct": q_ok, "Answers Correct": a_ok, "Latency ms": lat, "Error Category": cat}


def test_metrics_formulas():
    rows = [
        _row(1, expected="1+3", q_ok="ja", a_ok="yes", lat="800"),  # e2e success
        _row(2, expected="2", q_ok="yes", a_ok="no", lat="1000"),  # wrong AI answer clicked -> false click
        _row(3, mode="blocked", verified="", cat="low_confidence", expected="1", lat="1200"),
        _row(4, mode="blocked", verified="", cat="covered", lat="1100"),
        _row(5, mode="dry_run", verified="", lat="700", q_ok="nein"),
        _row(6, mode="click", verified="no", expected="1,3", lat="5000"),  # right answer, not verified
    ]
    m = compute_metrics(rows)
    assert m["questions"] == 6
    assert m["question_ocr_accuracy"] == pytest.approx(2 / 3, abs=1e-3) and m["question_ocr_rated"] == 3
    assert m["answer_ocr_accuracy"] == pytest.approx(1 / 2, abs=1e-3)
    assert m["with_expected_answer"] == 4
    assert m["ai_accuracy"] == pytest.approx(2 / 4, abs=1e-3)  # rows 1 and 6 ("1,3" == "1+3")
    assert m["end_to_end_success_rate"] == pytest.approx(1 / 4, abs=1e-3)
    assert m["real_clicks"] == 3 and m["false_click_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert m["prevented_unsafe_clicks"] == 2
    assert m["prevented_by_reason"] == {"low_confidence": 1, "covered": 1}
    assert m["dry_runs"] == 1
    assert m["median_latency_ms"] == pytest.approx(1050)
    assert m["p95_latency_ms"] == 5000
    assert "End-to-end success rate" in metrics_text(m)


def test_metrics_without_manual_ratings_say_not_rated():
    m = compute_metrics([_row(1), _row(2, mode="dry_run", verified="")])
    assert m["question_ocr_accuracy"] is None and m["end_to_end_success_rate"] is None
    assert "not rated yet" in metrics_text(m)


def test_protocol_csv_keeps_manual_columns_and_opens_in_excel(tmp_path):
    rows = [{**{c: "" for c in ("Question #", "Question ID")}, "Question #": "1", "Question ID": "abc",
             "AI Answer": "2", "Mode": "click"}]
    path = tmp_path / "protocol.csv"
    write_csv(rows, path)
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and b"Question #;" in raw  # BOM + ';' for German Excel
    filled = read_csv(path)
    filled[0]["Expected Answer"] = "2"
    filled[0]["Click Correct"] = "ja"
    import csv

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filled[0]), delimiter=";")
        w.writeheader()
        w.writerows(filled)
    write_csv(rows, path)  # regenerated from the trace
    again = read_csv(path)
    assert again[0]["Expected Answer"] == "2" and again[0]["Click Correct"] == "ja"


# ----------------------------------------------------------------------------- diagnosis ZIP
def test_diagnosis_zip_contents_and_no_secrets(tmp_path, monkeypatch):
    import logging

    from smart360.health.bundle import create_bundle
    from smart360.services import Services
    from smart360.storage import paths

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    svc = Services.create(tmp_path / "home", demo=True)
    try:
        svc.secrets.use_keyring = False  # never touch the real OS credential store in tests
        svc.secrets.set("ANTHROPIC_API_KEY", FAKE_KEY)
        svc.store.update(ai={"provider": "anthropic"})
        # a secret slipped into a log line, a raw key without a prefix pattern and a password
        (paths.log_dir() / "360smart.log").write_text(
            f"INFO something {FAKE_KEY}\nDEBUG login password={FAKE_PASSWORD}\n"
            "DEBUG header Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123\n",
            encoding="utf-8",
        )
        trace = SessionTrace(paths.trace_dir())
        trace.record("ocr", question_id="q1", question="Wer hat Vorfahrt?", answers=[], note=FAKE_KEY)
        svc.build_engine(None)
        out = create_bundle(svc, tmp_path / "out")
    finally:
        svc.shutdown()
        logging.getLogger().handlers.clear()

    assert out.name.startswith("360SMART-Diagnose-") and out.suffix == ".zip"
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        for required in ("README.txt", "report.json", "self_test.txt", "logs/360smart.log", "protocol.csv",
                         "metrics.json", "metrics.txt"):
            assert required in names, names
        assert any(n.startswith("trace/session-") for n in names)
        blob = b"".join(z.read(n) for n in names)
        report = json.loads(z.read("report.json"))
    for secret in (FAKE_KEY, FAKE_PASSWORD, "abcdefghijklmnopqrstuvwxyz0123", "THIS-IS-A-FAKE-KEY"):
        assert secret.encode() not in blob, f"{secret} leaked into the diagnosis"
    assert b"[REDACTED]" in blob
    sysinfo, eng = report["system"], report["engine"]
    for k in ("app_version", "build", "windows", "monitors", "monitor_count", "dpi_awareness"):
        assert k in sysinfo
    for k in ("state", "safe_mode", "dry_run", "ocr_engine", "target", "last_state_changes", "profiles"):
        assert k in eng
    assert eng["target"]["window_rect"]  # simulator window located
    assert "capture_regions" in eng["target"]


def test_diagnose_cli_creates_zip(tmp_path, monkeypatch):
    from smart360.app import main

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import logging

    try:
        code = main(["--diagnose", "--demo", "--data-dir", str(tmp_path / "home"), "--out", str(tmp_path)])
    finally:
        logging.getLogger().handlers.clear()
    assert code == 0
    assert len(list(tmp_path.glob("360SMART-Diagnose-*.zip"))) == 1


def test_metrics_cli(tmp_path, capsys):
    from smart360.app import main

    path = tmp_path / "protocol.csv"
    write_csv([{"Question #": "1", "Question ID": "a", "AI Answer": "1", "Mode": "click",
                "Verification Passed": "yes", "Latency ms": "900"}], path)
    assert main(["--metrics", str(path)]) == 0
    assert "Median latency" in capsys.readouterr().out
    assert json.loads((tmp_path / "metrics.json").read_text())["questions"] == 1
