"""External golden importer: validation, duplicates, leakage marking, read-only manifest."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from smart360.theory import leakage, splits

SRC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC))
from tools.external_import import validate  # noqa: E402

GOOD = {"id": "EXT-T1", "topic": "05_priority", "question": "Eine Ampel ist ausgefallen. Was regelt jetzt den Verkehr?",
        "answers": ["Die aufgestellten Schilder", "Der schnellere Fahrer"], "correct": [1],
        "source": "external-human-authored", "author": "Test"}


def test_validate_rejects_bad_and_duplicate_items():
    bad_topic = {**GOOD, "id": "X2", "topic": "99"}
    no_author = {**GOOD, "id": "X3", "author": ""}
    wrong_correct = {**GOOD, "id": "X4", "correct": [5]}
    dup_question = {**GOOD, "id": "X5"}
    items, errors = validate([GOOD, bad_topic, no_author, wrong_correct, dup_question, {**GOOD}], [])
    assert [i.id for i in items] == ["EXT-T1"]
    assert len(errors) == 5
    assert any("duplicate" in e for e in errors) and any("id already used" in e for e in errors)


def test_validate_against_earlier_imports():
    earlier = [splits.ExternalItem.model_validate(GOOD)]
    _, errors = validate([{**GOOD, "id": "NEW"}], earlier)
    assert errors and "duplicate" in errors[0]
    _, errors = validate([{**GOOD, "question": "Etwas ganz anderes?"}], earlier)
    assert errors and "id already used" in errors[0]


def test_leakage_detects_copies_of_training_text(kb):
    claim = next(c.statement for o in kb.objects.values() for c in o.claims if len(c.statement.split()) >= 7)
    rep = leakage.check_item("L1", claim + "?", ["Ja", "Nein"])
    assert rep.leak and rep.hits[0].source in ("claims", "generator")
    fresh = leakage.check_item("L2", "Auf dem Mond rollt ein Rover über einen Krater, was beachtet der Pilot?",
                               ["Er beobachtet den Staub der Mondoberfläche genau", "Er funkt der Bodenstation Grüße"])
    assert not fresh.leak


def test_leakage_answers_majority(kb):
    stmts = [c.statement for o in kb.objects.values() for c in o.claims if len(c.statement.split()) >= 7][:3]
    rep = leakage.check_item("L3", "Eine völlig neu formulierte Situation am Nachmittag?", stmts)
    assert rep.leak


def test_external_eval_refuses_changed_files(tmp_path, monkeypatch):
    monkeypatch.setattr(splits, "EXTERNAL_DIR", tmp_path)
    f = tmp_path / "external_x.json"
    f.write_text(json.dumps({"items": [GOOD]}), encoding="utf-8")
    (tmp_path / splits.MANIFEST).write_text(json.dumps({"files": {"external_x.json": "0" * 64}}), encoding="utf-8")
    from tools import theory_eval

    with pytest.raises(SystemExit):
        theory_eval._external_metrics([], {})


def test_importer_dry_run_cli(tmp_path):
    p = tmp_path / "new.json"
    p.write_text(json.dumps({"items": [{**GOOD, "author": ""}]}), encoding="utf-8")
    r = subprocess.run([sys.executable, str(SRC / "tools" / "external_import.py"), str(p), "--dry-run"],
                       capture_output=True, text=True, cwd=SRC)
    assert r.returncode == 1 and "REJECTED" in r.stdout
