"""Write reports/knowledge_gap_clusters.md: development-golden answers that NO claim of the knowledge base covers,
grouped into systematic gaps (law section, topic, missing concept / relation / numeric rule / exception).

Analysis only (development golden = regression data): the report lists item ids and single terms, never the
question text, and nothing in the engine or the knowledge base reads it. Gaps are closed per law section from the
official text - never per question.

    python tools/analysis/knowledge_gaps.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from smart360.theory.kb import KnowledgeBase
from smart360.theory.reasoning import MATCH_MIN, NUMBER_TOKEN, Verdict, _core, solve
from smart360.theory.semantics import action_concepts
from smart360.theory.splits import load_development_golden
from smart360.theory.text import content, numbers, similarity

ROOT = Path(__file__).resolve().parents[3]
_EXCEPTION = re.compile(r"\b(außer|ausser|ausgenommen|es sei denn|nur wenn|nur bei|ausnahme|auch wenn)\b", re.I)
_NON_RIS = re.compile(r"probezeit|punkte|fahrerlaubnis|führerschein|alkohol|promille|cannabis|bußgeld|fahrverbot|"
                      r"klasse b|prüfung", re.I)


def _norm_index(kb: KnowledgeBase) -> list[tuple[str, frozenset[str]]]:
    out = []
    for law, snap in kb.snapshots.items():
        keys = list(snap["norms"])
        for key, n in snap["norms"].items():
            if any(k != key and k.startswith(key + " Nr.") for k in keys):
                continue  # the whole Anlage - its numbered entries are more precise
            out.append((f"{law} {key}", frozenset(content(n["text"]))))
    return out


def _law_section(text: str, idx: list[tuple[str, frozenset[str]]]) -> tuple[str, float]:
    """Closest norm by overlap normalised for the norm's length (a long norm must not win by size alone);
    the returned score is the share of the text's words found in that norm."""
    words = set(content(text))
    best, rank, cover = "-", 0.0, 0.0
    for name, ws in idx:
        if not ws:
            continue
        ov = len(words & ws)
        r = ov / (len(ws) ** 0.5)
        if r > rank:
            best, rank, cover = name, r, ov / max(1, len(words))
    return best, cover


def main() -> int:
    kb = KnowledgeBase.load()
    claims = [(o, c, frozenset(_core(c.statement))) for o in kb.objects.values() for c in o.claims]
    kb_vocab = set()
    for o in kb.objects.values():
        kb_vocab |= set(content(" ".join([o.title, o.rule, *o.keywords, *(" ".join(c.context) + " " + c.statement
                                                                           for c in o.claims)])))
    topic_actions: dict[str, set[str]] = defaultdict(set)
    for o in kb.objects.values():
        for c in o.claims:
            topic_actions[o.topic] |= action_concepts(c.statement)
    units = {u for o in kb.objects.values() for c in o.claims for _, u in numbers(" ".join(c.numbers) or c.statement)}
    units |= {r.unit for r in kb.numeric.values()}
    nidx = _norm_index(kb)

    gaps = []
    for it in load_development_golden():
        r = solve(it.question, kb)
        for e, a in zip(r.evals, it.question.answers, strict=False):
            if e.verdict != Verdict.UNKNOWN:
                continue
            ac = frozenset(w for w in _core(a) if not NUMBER_TOKEN.match(w))
            if len(ac) < 2:
                continue  # short slot answers ('Rechts', 'Ja') carry no knowledge of their own
            best = max((similarity(ac, cc) for _, _, cc in claims), default=0.0)
            if best >= MATCH_MIN:
                continue  # a claim exists - this is a matching problem, not a knowledge gap
            section, sc = _law_section(it.question.text + " " + a, nidx)
            if sc < 0.35:
                section = "FeV/StVG/BKatV (kein amtlicher Text)" if _NON_RIS.search(it.question.text + " " + a) \
                    else "keine Norm eindeutig"
            kinds = []
            missing_terms = sorted(w for w in content(a) if w not in kb_vocab and len(w) > 3 and not NUMBER_TOKEN.match(w)
                                   and w not in ("nein", "ja"))
            if missing_terms:
                kinds.append("missing_concept")
            acts = action_concepts(a)
            if acts and not acts <= topic_actions[it.topic]:
                kinds.append("missing_relation")
            nums = [(v, u) for v, u in numbers(a) if u]
            if nums and any(u not in units for _, u in nums):
                kinds.append("missing_numeric_rule")
            elif nums:
                kinds.append("missing_numeric_condition")
            if _EXCEPTION.search(a) or _EXCEPTION.search(it.question.text):
                kinds.append("missing_exception")
            if not kinds:
                kinds.append("missing_statement")
            gaps.append({"id": f"{it.id}#{e.index}", "topic": it.topic, "section": section, "kinds": kinds,
                         "terms": missing_terms[:4]})

    by_section: dict[str, list[dict]] = defaultdict(list)
    for g in gaps:
        by_section[g["section"].split(" Abs")[0]].append(g)
    lines = ["# Knowledge gap clusters (development golden, analysis only)", "",
             f"{len(gaps)} answer options with **no** sufficiently similar claim in the knowledge base. These are "
             "knowledge gaps, not matching problems. They are grouped so that whole law sections can be added "
             "systematically from the official text, **not** question by question. Only ids and single terms are "
             "listed. This report is not read by the engine.", "",
             "## By gap type", "", "| Gap type | Count |", "|---|---|"]
    for k, n in Counter(k for g in gaps for k in g["kinds"]).most_common():
        lines.append(f"| {k} | {n} |")
    lines += ["", "## By topic", "", "| Topic | Count |", "|---|---|"]
    for k, n in Counter(g["topic"] for g in gaps).most_common():
        lines.append(f"| {k} | {n} |")
    lines += ["", "## By law section (closest official norm)", "",
              "| Law section | Count | Topics | Gap types | Terms missing in the KB | Items |", "|---|---|---|---|---|---|"]
    for sec, gs in sorted(by_section.items(), key=lambda x: -len(x[1])):
        topics = ", ".join(sorted({g["topic"] for g in gs}))
        kinds = ", ".join(f"{k} {n}" for k, n in Counter(k for g in gs for k in g["kinds"]).most_common())
        terms = ", ".join(t for t, _ in Counter(t for g in gs for t in g["terms"]).most_common(8)) or "-"
        ids = ", ".join(g["id"] for g in gs[:8]) + (" …" if len(gs) > 8 else "")
        lines.append(f"| {sec} | {len(gs)} | {topics} | {kinds} | {terms} | {ids} |")
    lines += ["", "## Recommended systematic steps", "",
              "1. For every law section above, check the whole section of the official text for statements without a "
              "claim, not only the listed items.",
              "2. `missing_relation`: add the action concept and its contradictions to the lexicon / contradiction "
              "index (valid only if the law text supports it).",
              "3. `missing_numeric_rule` / `missing_numeric_condition`: add the numeric rule with its conditions "
              "(numeric condition model).",
              "4. `FeV/StVG/BKatV`: only after a manual official-source import (`knowledge/sources/manual/`).", ""]
    out = ROOT / "reports" / "knowledge_gap_clusters.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(gaps)} gaps in {len(by_section)} law sections -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
