"""Optional cross-check of an AI prediction with the rule-based theory engine (setting: safety.theory_crosscheck).

It can only make a prediction MORE conservative:
  * theory engine sure AND different answer  ->  prediction becomes uncertain (no click in safe mode)
  * theory engine uncertain or agreeing      ->  prediction unchanged
It never raises a confidence, never clears 'uncertain', never selects answers itself.
Unverified knowledge (FeV/StVG/BKatV without official text) can never make it block: a theory result that rests on
an unverified rule counts as 'theory_uncertain' (defence in depth - the engine already caps it as uncertain)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from smart360.theory.reasoning import TheoryQuestion, solve

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CrossCheck:
    verdict: str  # agree | disagree | theory_uncertain | error
    theory_selected: tuple[int, ...] = ()
    theory_number: str | None = None
    theory_confidence: float = 0.0
    reasons: tuple[str, ...] = ()

    @property
    def should_block(self) -> bool:
        return self.verdict == "disagree"


def crosscheck(question: str, answers: list[str], number_input: bool, ocr_confidence: float, has_image: bool,
               ai_answers: tuple[int, ...], ai_number: str | None) -> CrossCheck:
    try:
        r = solve(TheoryQuestion(question, answers, number_input=number_input, ocr_confidence=ocr_confidence,
                                 has_image=has_image))
    except Exception as e:  # the cross-check must never break the assistant
        log.warning("theory cross-check failed: %s", e)
        return CrossCheck("error", reasons=(f"{type(e).__name__}",))
    if r.uncertain:
        return CrossCheck("theory_uncertain", r.selected, r.number_answer, r.confidence, tuple(r.reasons[:3]))
    from smart360.theory.kb import get_kb

    kb = get_kb()
    if any(not kb.verified(x) for e in r.evals if e.verdict.value != "UNKNOWN" for x in e.evidence):
        return CrossCheck("theory_uncertain", r.selected, r.number_answer, r.confidence, ("unverified_knowledge",))
    if number_input:
        same = _num(r.number_answer) is not None and _num(r.number_answer) == _num(ai_number)
    else:
        same = tuple(sorted(r.selected)) == tuple(sorted(ai_answers))
    return CrossCheck("agree" if same else "disagree", r.selected, r.number_answer, r.confidence)


def _num(x: str | None) -> float | None:
    try:
        return round(float(str(x).replace(",", ".")), 2)
    except (TypeError, ValueError):
        return None
