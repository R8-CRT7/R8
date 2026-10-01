"""Exam simulator (theory test, class B) - structure and pass rule come from the numeric knowledge base
(FeV Anlage 7, verified against the official law snapshot), not from hard-coded memory.

In exam mode there is no help and no solution while answering. Afterwards: full analysis per question and
per topic, error points, pass/fail, and the learner profile is updated (mode='exam')."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from smart360.theory.kb import get_kb


@dataclass(frozen=True)
class ExamRules:
    questions: int
    max_error_points: int
    fail_on_two_five_point_errors: bool
    minutes: int | None
    source: str


def class_b_rules() -> ExamRules:
    kb = get_kb()
    n = kb.numeric
    return ExamRules(
        questions=int(n["FEV_A7_B_QUESTIONS"].value),
        max_error_points=int(n["FEV_A7_B_MAX_ERROR_POINTS"].value),
        fail_on_two_five_point_errors=True,
        minutes=int(n["FEV_A7_B_MINUTES"].value) if "FEV_A7_B_MINUTES" in n else None,
        source="FeV Anlage 7 (snapshot verified)",
    )


@dataclass
class ExamItem:
    item_id: str
    points: int  # 2..5 error points
    correct: set[int]
    topic: str = ""


@dataclass
class ExamResult:
    error_points: int
    five_point_errors: int
    passed: bool
    wrong: list[str] = field(default_factory=list)
    by_topic: dict[str, tuple[int, int]] = field(default_factory=dict)  # topic -> (wrong, total)


def score_exam(items: list[ExamItem], answers: dict[str, set[int]], rules: ExamRules) -> ExamResult:
    """A question counts as correct only if exactly the correct set was chosen (multiselect exact match)."""
    pts, fives, wrong = 0, 0, []
    by_topic: dict[str, tuple[int, int]] = {}
    for it in items:
        ok = answers.get(it.item_id, set()) == it.correct
        w, t = by_topic.get(it.topic, (0, 0))
        by_topic[it.topic] = (w + (not ok), t + 1)
        if not ok:
            pts += it.points
            fives += it.points == 5
            wrong.append(it.item_id)
    passed = pts <= rules.max_error_points and not (rules.fail_on_two_five_point_errors and fives >= 2)
    return ExamResult(pts, fives, passed, wrong, by_topic)


def points_for(exam_relevance: int) -> int:
    """The real error points belong to the official question catalogue (not available to us). Approximation
    for simulation only: exam-critical rules 5, normal 3, minor 2."""
    return {3: 5, 2: 3, 1: 2}.get(exam_relevance, 3)


def build_exam(pool: list, rules: ExamRules, seed: int | None = None) -> list:  # type: ignore[type-arg]
    """Pick `rules.questions` items spread over topics (round-robin), seeded for reproducibility."""
    rng = random.Random(seed if seed is not None else int(time.time()))
    by_topic: dict[str, list] = {}  # type: ignore[type-arg]
    for it in pool:
        by_topic.setdefault(it.topic, []).append(it)
    for v in by_topic.values():
        rng.shuffle(v)
    out: list = []  # type: ignore[type-arg]
    topics = sorted(by_topic)
    while len(out) < rules.questions and any(by_topic.values()):
        for t in topics:
            if by_topic[t] and len(out) < rules.questions:
                out.append(by_topic[t].pop())
    return out
