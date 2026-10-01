"""Write reports/golden_uncertain_analysis.md from the manual labels + a fresh engine run (analysis only)."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from smart360.theory.kb import KnowledgeBase
from smart360.theory.reasoning import Verdict, solve
from smart360.theory.splits import load_golden_internal
from tools.analysis.golden_uncertain_labels import CATEGORIES, LABELS

ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    kb = KnowledgeBase.load()
    items = {it.id: it for it in load_golden_internal()}
    unc, hidden = [], []
    for it in items.values():
        r = solve(it.question, kb)
        if r.uncertain:
            unc.append(it.id)
            # per-answer verdicts that contradict the expected answer, masked by the overall UNCERTAIN
            for e in r.evals:
                if e.verdict == Verdict.UNKNOWN:
                    continue
                should = e.index in it.correct
                if (e.verdict == Verdict.TRUE) != should:
                    hidden.append((it.id, e.index))
    missing = [i for i in unc if i not in LABELS]
    prim = Counter(LABELS[i][0] for i in unc if i in LABELS)
    sec = Counter(s for i in unc if i in LABELS for s in LABELS[i][1])
    n = len(unc)
    lines = ["# Golden v1/v2 – Analyse der UNCERTAIN-Fälle", "",
             f"Stand: Golden v1+v2 (160 Fragen), {n} UNCERTAIN ({n / len(items):.0%}). "
             "Jeder Fall wurde **einzeln von Hand** einer Hauptursache zugeordnet "
             "(`windows/tools/analysis/golden_uncertain_labels.py`); die Engine nutzt diese Labels nicht.",
             "", "| Kategorie | Anzahl | Prozent | Nebenursache in | Beschreibung | Empfohlene Verbesserung |",
             "|---|---|---|---|---|---|"]
    for cat, cnt in prim.most_common():
        desc, fix = CATEGORIES[cat]
        lines.append(f"| {cat} | {cnt} | {cnt / n:.0%} | {sec.get(cat, 0)} | {desc} | {fix} |")
    lines += ["", "## Beispiele je Kategorie (eigene Kurzbeschreibung)", ""]
    for cat, _ in prim.most_common():
        ex = [f"{i}: {LABELS[i][2]}" for i in unc if i in LABELS and LABELS[i][0] == cat][:5]
        lines.append(f"**{cat}**")
        lines += [f"- {e}" for e in ex]
        lines.append("")
    lines += ["## Versteckte Fehlurteile", "",
              f"In UNCERTAIN-Fragen gab es **{len(hidden)} Einzelurteile**, die dem erwarteten Ergebnis widersprechen, "
              "aber durch die Gesamt-Unsicherheit verdeckt waren. Wer UNCERTAIN einfach senkt, macht daraus "
              "falsch-sichere Antworten – deshalb werden sie hier mitgezählt und jede Verbesserung muss sie "
              "beseitigen statt aufdecken.", "",
              ", ".join(f"{i}#{a}" for i, a in hidden) or "-", ""]
    if missing:
        lines += ["## Noch nicht gelabelt", "", ", ".join(missing), ""]
    out = ROOT / "reports" / "golden_uncertain_analysis.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{n} uncertain, {len(missing)} unlabelled, {len(hidden)} hidden wrong verdicts -> {out}")
    for c, k in prim.most_common():
        print(f"  {c}: {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
