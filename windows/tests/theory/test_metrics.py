"""Quality gates on the synthetic variants and the golden set.

The most critical gate is the false-confident rate: a wrong answer the engine is sure about. UNCERTAIN is
allowed (it is the safe outcome) - its rate is reported, not gated tightly."""

import hashlib
from pathlib import Path

import pytest

import tools.theory_eval as ev
from smart360.theory.generator import all_items
from smart360.theory.golden import GOLDEN_DIR, load_golden

GOLDEN_V1_SHA256 = "7caf82dca079a52428dbcc0c1beda6d81e706e8edd4136468fcdf5e09ec50a5e"


@pytest.fixture(scope="module")
def synthetic(kb):
    return ev.run(all_items(kb), kb)


def test_synthetic_size(synthetic):
    _, m = synthetic
    assert m["overall"]["n"] >= 3000


def test_synthetic_false_confident_is_zero(synthetic):
    rows, m = synthetic
    bad = [r["id"] for r in rows if r["false_confident"]]
    assert m["overall"]["false_confident_rate"] <= 0.001, bad[:20]


def test_synthetic_category_gates(synthetic):
    _, m = synthetic
    c = m["by_category"]
    assert c["numeric"]["accuracy"] >= 0.95
    assert c["priority"]["accuracy"] >= 0.95
    assert c["sign"]["accuracy"] >= 0.9
    assert c["negation"]["false_confident_rate"] == 0.0
    assert m["multiselect_exact_match"]["false_confident_rate"] == 0.0
    assert m["rule_selection_accuracy"] >= 0.95
    assert m["overall"]["precision_when_answered"] >= 0.995


def test_golden_v1_is_frozen():
    """The golden set must not be edited to fit the engine - a new version gets a new file."""
    data = (GOLDEN_DIR / "golden_v1.json").read_bytes()
    assert hashlib.sha256(data).hexdigest() == GOLDEN_V1_SHA256


def test_golden_false_confident_gate(kb):
    rows, m = ev.run(load_golden(), kb)
    assert m["overall"]["false_confident_rate"] <= 0.05, [r["id"] for r in rows if r["false_confident"]]


def test_golden_set_does_not_reuse_knowledge_claims(kb):
    """Independence check: golden answers are not verbatim knowledge-base claims."""
    claims = {c.statement.strip().lower() for o in kb.objects.values() for c in o.claims}
    reused = [a for it in load_golden() for a in it.question.answers if a.strip().lower() in claims]
    assert len(reused) <= 3, reused


def test_eval_tool_writes_report(tmp_path, kb, monkeypatch):
    out = tmp_path / "m.json"
    assert ev.main(["--golden", "--out", str(out)]) == 0
    assert Path(out).exists()
