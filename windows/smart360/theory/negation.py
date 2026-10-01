"""Negation / modality / quantifier analysis (NICHT, KEIN, DÜRFEN, MÜSSEN, KÖNNEN, IMMER, NUR, VERBOTEN,
ERLAUBT, AUSNAHME ...).

The exam loves small words: "darf" vs. "darf nicht" vs. "muss nicht", "immer" vs. "in der Regel". This module
turns a sentence into explicit features so the evaluator can flip, compare or refuse (UNCERTAIN)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from smart360.theory.text import fold

NEGATORS = ("nicht", "kein", "keine", "keinen", "keinem", "keiner", "keines", "nie", "niemals", "keinesfalls",
            "nichts", "weder", "auf keinen fall")
PERMIT = ("darf", "dürfen", "duerfen", "dürfte", "erlaubt", "zulässig", "zulaessig", "gestattet")
OBLIGE = ("muss", "müssen", "muessen", "musste", "verpflichtet", "ist zu", "sind zu", "hat zu", "haben zu",
          "vorgeschrieben", "pflicht")
POSSIBLE = ("kann", "können", "koennen", "könnte", "möglich", "moeglich")
ABSOLUTE = ("immer", "stets", "jederzeit", "nie", "niemals", "ausnahmslos", "in jedem fall", "grundsätzlich",
            "nur", "ausschließlich", "ausschliesslich", "alle", "jeder", "jede", "jedes", "überall")
EXCEPTION = ("außer", "ausser", "ausgenommen", "es sei denn", "ausnahme", "ausnahmsweise", "sofern nicht",
             "wenn nicht", "abweichend")
# question asks for the WRONG / FORBIDDEN options
ASKS_NEGATIVE = (
    r"\bnicht (erlaubt|zulässig|gestattet|richtig|korrekt|zutreffend|vorgeschrieben)\b",
    r"\b(verboten|unzulässig|falsch|fehlerhaft|untersagt)\b\s*\?",
    r"\bwas (dürfen|darf) sie (hier )?nicht\b",
    r"\bwelche[rs]?\b.*\bnicht\b.*\?",
    r"\bwas ist (hier )?(verboten|falsch|unzulässig)\b",
    r"\bwann dürfen sie (hier )?nicht\b",
)


class Deontic(StrEnum):
    NONE = "none"
    PERMITTED = "permitted"  # darf / erlaubt
    FORBIDDEN = "forbidden"  # darf nicht / verboten
    OBLIGATORY = "obligatory"  # muss
    NOT_OBLIGATORY = "not_obligatory"  # muss nicht / braucht nicht
    POSSIBLE = "possible"  # kann


@dataclass(frozen=True)
class Polarity:
    negated: bool  # odd number of plain negators (deontic words excluded)
    deontic: Deontic
    absolutes: tuple[str, ...] = ()
    exceptions: tuple[str, ...] = ()
    cues: tuple[str, ...] = field(default_factory=tuple)


def _hits(t: str, words: tuple[str, ...]) -> list[str]:
    return [w for w in words if re.search(rf"(?<![a-zäöü]){re.escape(w)}(?![a-zäöü])", t)]


def analyze(text: str) -> Polarity:
    t = fold(text)
    n_neg = len(re.findall(r"(?<![a-zäöü])(nicht|kein\w*|nie|niemals|keinesfalls|nichts)(?![a-zäöü])", t))
    prohibit = _hits(t, ("verboten", "untersagt", "unzulässig", "unzulaessig"))
    permit = _hits(t, PERMIT)
    oblige = _hits(t, OBLIGE)
    possible = _hits(t, POSSIBLE)
    needs_not = bool(re.search(r"\bbrauch\w*\b", t)) and n_neg > 0
    deontic = Deontic.NONE
    if prohibit:  # "verboten"; "nicht verboten" = permitted
        deontic = Deontic.PERMITTED if n_neg % 2 else Deontic.FORBIDDEN
        n_neg = 0 if n_neg % 2 else n_neg
    elif permit:  # "darf" / "darf nicht"
        deontic = Deontic.FORBIDDEN if n_neg % 2 else Deontic.PERMITTED
        n_neg = n_neg - 1 if n_neg % 2 else n_neg
    elif oblige or needs_not:  # "muss" / "muss nicht" / "braucht nicht"
        deontic = Deontic.NOT_OBLIGATORY if n_neg % 2 else Deontic.OBLIGATORY
        n_neg = n_neg - 1 if n_neg % 2 else n_neg
    elif possible:
        deontic = Deontic.POSSIBLE
    absolutes = tuple(_hits(t, ABSOLUTE))
    exceptions = tuple(_hits(t, EXCEPTION))
    cues = tuple(_hits(t, NEGATORS) + prohibit + permit + oblige + possible)
    return Polarity(n_neg % 2 == 1, deontic, absolutes, exceptions, cues)


def asks_for_negative(question: str) -> bool:
    """'Was ist hier NICHT erlaubt?', 'Welches Verhalten ist falsch?' -> select the false/forbidden options."""
    t = fold(question)
    return any(re.search(p, t) for p in ASKS_NEGATIVE)


def deontic_truth(claim: Deontic, answer: Deontic, claim_truth: bool) -> bool | None:
    """Truth of the answer given a claim about the same action with a deontic status.

    Returns None when the two modalities cannot be compared safely (e.g. 'muss' vs 'darf')."""
    if claim == answer:
        return claim_truth
    opposite = {
        (Deontic.PERMITTED, Deontic.FORBIDDEN), (Deontic.FORBIDDEN, Deontic.PERMITTED),
        (Deontic.OBLIGATORY, Deontic.NOT_OBLIGATORY), (Deontic.NOT_OBLIGATORY, Deontic.OBLIGATORY),
    }
    if (claim, answer) in opposite:
        return not claim_truth
    # an obligation implies permission; a prohibition implies "not obligatory"
    if claim_truth and (claim, answer) in {(Deontic.OBLIGATORY, Deontic.PERMITTED),
                                           (Deontic.FORBIDDEN, Deontic.NOT_OBLIGATORY)}:
        return True
    if claim_truth and (claim, answer) in {(Deontic.OBLIGATORY, Deontic.FORBIDDEN),
                                           (Deontic.FORBIDDEN, Deontic.OBLIGATORY)}:
        return False
    return None
