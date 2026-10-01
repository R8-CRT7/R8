"""Numeric condition model: a number is never just '15 m' - it is distance=15 m under a condition.

    NumericFact(value=15, unit='m', quantity='distance', comparator='max',
                conditions={'haltestell', 'park', ...}, source='PRK_NO_PARKING#4', verified=True)

Facts come from claims with numbers and from the verified numeric rules (knowledge/numeric_rules.json).
A bare numeric answer may only be judged against a fact whose conditions the question names:
    * the unit must fit the quantity the question asks for (no 'm' answer judged by a km/h rule)
    * every specific condition term of the fact must appear in the question (full coverage)
    * every qualifier of the question (Anhänger, Lkw, Nebel ...) must be covered by the fact
    * all facts that fit must agree on the value - otherwise UNKNOWN
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from smart360.theory.kb import KnowledgeBase
from smart360.theory.retrieval import _QUANTITY_OF_UNIT
from smart360.theory.text import content, numbers

# words that only name the quantity / the question form - never a condition
GENERIC = frozenset(content(
    "abstand meter weit wie viel viele lang lange schnell geschwindigkeit höchstgeschwindigkeit km/h höchstens "
    "mindestens maximal bis zu ab etwa mindestabstand gilt beträgt betragen zulässig zulässige darf dürfen muss "
    "müssen fahren gefahren werden nicht vor hinter dem der die das einhalten halten sie ich"))
# the quantity a question asks for comes from its interrogative phrase only ('Ab welcher Sichtweite ... 50 km/h?'
# asks for a distance, the km/h is part of the condition)
_QUESTION_QUANTITY = (("speed", r"wie schnell|(welche[rnms]?|wie hoch\w*( \w+){0,3}) (zulässige )?(höchst)?geschwindigkeit|"
                                r"mit welcher geschwindigkeit"),
                      ("distance", r"wie weit|wie viele meter|welche[rnms]? (mindest|seiten|sicherheits)?abstand|"
                                   r"welche[rnms]? (entfernung|sichtweite|strecke)|wie (hoch|breit|lang ist)"),
                      ("time", r"wie lange|wie oft|ab wann|nach wie vielen|wie viele (monate|jahre|minuten|tage)"))


@dataclass(frozen=True)
class NumericFact:
    value: float
    unit: str
    quantity: str
    comparator: str  # max | min | eq
    conditions: frozenset[str]
    source: str
    truth: bool
    verified: bool


def _comparator(text: str) -> str:
    t = text.lower()
    if re.search(r"höchstens|maximal|nicht mehr als|bis zu|nicht schneller|nicht über", t):
        return "max"
    if re.search(r"mindestens|wenigstens|nicht weniger als|nicht unter|\bab\b", t):
        return "min"
    if re.search(r"mehr als|über\s+\d|schneller als|länger als", t):
        return "gt"
    if re.search(r"weniger als|unter\s+\d|langsamer als|kürzer als", t):
        return "lt"
    return "eq"


comparator = _comparator


def comparator_of(text: str, value: float, unit: str) -> str:
    """Comparator of one number in a text ('Bei Sichtweite unter 50 m darf höchstens 50 km/h' -> 'lt' for 50 m,
    'max' for 50 km/h): only the words right before that number count."""
    t = text.lower()
    v = f"{value:g}".replace(".", ",")
    for m in re.finditer(rf"(?<![\d,]){re.escape(v)}\s*{re.escape(unit)}" if unit else rf"(?<![\d,]){re.escape(v)}", t):
        return _comparator(t[max(0, m.start() - 25):m.start()])
    return _comparator(t)


def _conditions(text: str) -> frozenset[str]:
    from smart360.theory.reasoning import NUMBER_TOKEN

    return frozenset(w for w in content(text) if w not in GENERIC and not NUMBER_TOKEN.match(w))


_FACTS: dict[int, list[NumericFact]] = {}


def facts(kb: KnowledgeBase) -> list[NumericFact]:
    if id(kb) not in _FACTS:
        _FACTS[id(kb)] = _build_facts(kb)
    return _FACTS[id(kb)]


def _build_facts(kb: KnowledgeBase) -> list[NumericFact]:
    out: list[NumericFact] = []
    for obj in kb.objects.values():
        ver = kb.status.get(obj.id) == "verified"
        for i, c in enumerate(obj.claims):
            for v, u in numbers(" ".join(c.numbers) or c.statement):
                if not u:
                    continue
                out.append(NumericFact(v, u, _QUANTITY_OF_UNIT.get(u, "number"), _comparator(c.statement),
                                       _conditions(" ".join(c.context) + " " + c.statement), f"{obj.id}#{i}", c.truth, ver))
    for r in kb.numeric.values():
        out.append(NumericFact(r.value, r.unit, _QUANTITY_OF_UNIT.get(r.unit, "number"), r.comparator,
                               _conditions(r.applies_to + " " + " ".join(r.keywords)), r.id, True,
                               kb.status.get(r.id) == "verified"))
    return out


def question_quantity(question: str) -> str | None:
    t = question.lower()
    for q, rx in _QUESTION_QUANTITY:
        if re.search(rx, t):
            return q
    return None


def unit_fits(question: str, unit: str) -> bool:
    """'Wie weit ...?' cannot be answered in km/h; unknown question quantity -> no restriction."""
    q = question_quantity(question)
    u = _QUANTITY_OF_UNIT.get(unit)
    if q is None or u is None:
        return True
    return u == q or (q == "time" and u in ("time", "age_or_time"))


def fitting_facts(question: str, unit: str, kb: KnowledgeBase) -> list[NumericFact]:
    from smart360.theory.reasoning import QUALIFIERS, _core

    q_words = _core(question)
    q_quals = q_words & QUALIFIERS
    out = []
    for f in facts(kb):
        if f.unit != unit or not f.conditions or not f.verified:
            continue
        if not f.conditions <= q_words:
            continue  # a condition of the fact is not named in the question
        if q_quals - f.conditions:
            continue  # the question names a qualifier the fact does not cover
        out.append(f)
    return out


def judge_number(question: str, answer: str, kb: KnowledgeBase) -> tuple[bool | None, NumericFact | None]:
    """Bare numeric answer: True / False from the verified facts that fit the question, None if undecidable."""
    nums = [(v, u) for v, u in numbers(answer) if u]
    if len(nums) != 1:
        return None, None
    v, u = nums[0]
    if not unit_fits(question, u):
        return None, None
    fit = [f for f in fitting_facts(question, u, kb) if f.truth]
    values = {f.value for f in fit}
    if len(values) != 1:
        return None, None  # no fact, or facts with different values for this situation
    f = fit[0]
    return (abs(f.value - v) < 1e-9), f
