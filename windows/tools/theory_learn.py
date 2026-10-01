"""Terminal learn session (Klasse B theory) - for trying the tutor without the GUI.

    python tools/theory_learn.py                # learn mode, profile in ~/.smart360/learner.sqlite
    python tools/theory_learn.py --exam         # exam simulation (no help while answering)
    python tools/theory_learn.py --status       # mastery per subtopic + next tasks
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smart360.tutor.learn import ExamSession, LearnSession
from smart360.tutor.levels import LEVEL_NAMES
from smart360.tutor.store import LearnerStore


def _ask(item) -> tuple[set[int], str | None, int]:  # type: ignore[no-untyped-def]
    print("\n" + item.question.text)
    for i, a in enumerate(item.question.answers, start=1):
        print(f"  [{i}] {a}")
    t0 = time.time()
    raw = input("Zahl eingeben: " if item.question.number_input else "Antwort(en), z. B. 1,3: ").strip()
    ms = int((time.time() - t0) * 1000)
    if item.question.number_input:
        return set(), raw, ms
    return {int(x) for x in raw.replace(" ", "").split(",") if x.isdigit()}, None, ms


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=Path.home() / ".smart360" / "learner.sqlite")
    ap.add_argument("--exam", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--n", type=int, default=10)
    a = ap.parse_args(argv)
    a.db.parent.mkdir(parents=True, exist_ok=True)
    store = LearnerStore(a.db)
    session = LearnSession(store)
    if a.status:
        for sub, st in sorted(session.states().items(), key=lambda x: x[1].score):
            print(f"{st.score:5.1f}  {sub:35s} Versuche {st.attempts:3d}  Retention {st.retention:.0%}")
        for t in session.next_tasks():
            print(f"-> [{t.priority_class}] {t.kind} {t.subtopic or ''}: {t.reason}")
        return 0
    if a.exam:
        ex = ExamSession.start(session.items)
        print(f"Prüfungssimulation: {len(ex.items)} Fragen ({ex.rules.source})")
        for it in ex.items:
            chosen, number, _ = _ask(it)
            ex.answer(it.id, chosen, number)
        r = ex.finish(store)
        print(f"\nFehlerpunkte: {r.error_points} - {'BESTANDEN' if r.passed else 'NICHT bestanden'}")
        for topic, (w, t) in sorted(r.by_topic.items()):
            print(f"  {topic}: {t - w}/{t} richtig")
        return 0
    for _ in range(a.n):
        item = session.next_item()
        if item is None:
            break
        chosen, number, ms = _ask(item)
        fb = session.submit(item, chosen, number, ms)
        print("RICHTIG" if fb.correct else "FALSCH")
        if not fb.correct:
            # first the concept behind the mistake - the answer itself comes last
            if fb.diagnosis:
                print(f"  Fehlerursache: {fb.diagnosis.cause.value} - {fb.diagnosis.detail}")
            for k, v in fb.steps:
                print(f"  {k}: {v}")
        for i, o in enumerate(fb.options, start=1):
            mark = "✔" if o.correct else "✘"
            print(f"  {mark} [{i}] {o.text}\n      {o.why}")
        if fb.number_expected:
            print(f"  Lösung: {fb.number_expected}")
        if fb.correct:
            print(f"  Regel: {fb.rule}\n  Quelle: {fb.source}")
            if fb.mnemonic:
                print(f"  Merkhilfe: {fb.mnemonic}")
            print(f"  Nächste Stufe: {fb.next_level} ({LEVEL_NAMES.get(fb.next_level, '')})")
        for w in fb.warnings:
            print(f"  ! {w}")
        print(f"  Mastery {fb.mastery_before:.0f} -> {fb.mastery_after:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
