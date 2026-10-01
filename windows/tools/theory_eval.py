"""Evaluate the theory engine on the synthetic variants (and optionally the golden set).

    python tools/theory_eval.py                  # synthetic, writes reports/theory_metrics.json
    python tools/theory_eval.py --golden         # golden set (tests/theory/golden/*.json)
    python tools/theory_eval.py --show-wrong 30  # print false-confident cases

Definitions (per item):
  answered        = engine NOT uncertain
  correct         = answered and selected set == expected set (exact multiselect match) / number matches
  false_confident = answered and NOT correct      <- the most critical metric
  uncertain       = engine returned UNCERTAIN (counts as 'not answered', never as correct)
  accuracy        = correct / all items
  precision       = correct / answered
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smart360.theory.generator import TheoryItem, all_items
from smart360.theory.kb import KnowledgeBase
from smart360.theory.reasoning import TheoryResult, Verdict, solve

ROOT = Path(__file__).resolve().parents[2]

CATEGORY_OF_VARIANT = {
    "negation": "negation", "negative_question": "negation", "calc": "numeric", "calc_units": "numeric",
    "number_input": "numeric", "calc_ocr": "numeric", "calc_factor": "numeric", "calc_factor_neg": "numeric",
    "number_change": "numeric", "unit_error": "numeric", "priority": "priority", "sign": "sign",
    "sign_paraphrase": "sign", "sign_ocr": "sign", "licence": "licence", "licence_paraphrase": "licence",
}


def _num_eq(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return False
    try:
        return abs(float(a.replace(",", ".")) - float(b.replace(",", "."))) < 0.051
    except ValueError:
        return False


def judge(item: TheoryItem, r: TheoryResult) -> dict:
    answered = not r.uncertain
    if item.question.number_input:
        ok = _num_eq(r.number_answer, item.number_answer)
    else:
        ok = tuple(sorted(r.selected)) == tuple(sorted(item.correct))
    decided_ids = {x for e in r.evals if e.verdict != Verdict.UNKNOWN for x in e.evidence}
    rule_ok = bool(set(item.sources) & decided_ids) if item.sources and item.variant not in (
        "priority",) and not item.id.startswith(("CALC", "LIC")) else None
    return {"id": item.id, "topic": item.topic, "variant": item.variant, "answered": answered,
            "correct": answered and ok, "false_confident": answered and not ok, "uncertain": not answered,
            "uncertain_ok": item.expect_uncertain_ok, "multiselect": len(item.correct) > 1,
            "image": item.question.has_image or item.question.scene is not None, "rule_ok": rule_ok,
            "selected": list(r.selected), "expected": list(item.correct), "reasons": r.reasons[:3],
            "confidence": r.confidence}


def metrics(rows: list[dict]) -> dict:
    def rate(sel: list[dict], key: str) -> float | None:
        return round(sum(r[key] for r in sel) / len(sel), 4) if sel else None

    def block(sel: list[dict]) -> dict:
        ans = [r for r in sel if r["answered"]]
        return {"n": len(sel), "accuracy": rate(sel, "correct"), "uncertain_rate": rate(sel, "uncertain"),
                "false_confident_rate": rate(sel, "false_confident"),
                "precision_when_answered": round(sum(r["correct"] for r in ans) / len(ans), 4) if ans else None}

    cats: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        cats[CATEGORY_OF_VARIANT.get(r["variant"], "claims")].append(r)
    rule_rows = [r for r in rows if r["rule_ok"] is not None and r["answered"]]
    return {
        "overall": block(rows),
        "multiselect_exact_match": block([r for r in rows if r["multiselect"]]),
        "image": block([r for r in rows if r["image"]]),
        "by_category": {k: block(v) for k, v in sorted(cats.items())},
        "by_topic": {k: block([r for r in rows if r["topic"] == k]) for k in sorted({r["topic"] for r in rows})},
        "by_variant": {k: block([r for r in rows if r["variant"] == k]) for k in sorted({r["variant"] for r in rows})},
        "rule_selection_accuracy": round(sum(r["rule_ok"] for r in rule_rows) / len(rule_rows), 4) if rule_rows else None,
        "uncertain_acceptable": sum(1 for r in rows if r["uncertain"] and r["uncertain_ok"]),
        "uncertain_reasons": Counter(x.split(":")[0] for r in rows if r["uncertain"] for x in r["reasons"]).most_common(10),
    }


def run(items: list[TheoryItem], kb: KnowledgeBase) -> tuple[list[dict], dict]:
    rows = [judge(it, solve(it.question, kb)) for it in items]
    return rows, metrics(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--show-wrong", type=int, default=0)
    a = ap.parse_args(argv)
    kb = KnowledgeBase.load()
    t0 = time.time()
    if a.golden:
        from smart360.theory.golden import load_golden

        items = load_golden()
    else:
        items = all_items(kb)
    rows, m = run(items, kb)
    m["seconds"] = round(time.time() - t0, 1)
    m["set"] = "golden" if a.golden else "synthetic"
    out = a.out or ROOT / "reports" / f"theory_metrics_{m['set']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: m[k] for k in ("overall", "multiselect_exact_match", "image", "by_category",
                                        "rule_selection_accuracy", "uncertain_reasons")}, ensure_ascii=False, indent=1))
    for r in [r for r in rows if r["false_confident"]][: a.show_wrong]:
        print("FALSE-CONFIDENT", r["id"], "sel", r["selected"], "exp", r["expected"], r["confidence"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
