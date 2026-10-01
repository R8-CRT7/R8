"""Learn mode and exam mode (headless - the UI and the CLI tools/theory_learn.py sit on top).

Learn loop:  next question (planner: highest mastery gain per minute)  ->  learner answers  ->  check
             ->  explanation of EVERY option (why right / why wrong)  ->  the rule + official source
             ->  mnemonic  ->  a similar question (other variant of the same rule)  ->  profile update.

Ground truth comes from the generated item (knowledge data), never from the engine's guess. Rules whose law
text could not be verified against an official snapshot are shown with a visible warning."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from smart360.theory.generator import TheoryItem, all_items
from smart360.theory.kb import KnowledgeBase, get_kb
from smart360.theory.reasoning import Verdict, solve
from smart360.tutor.errors import Diagnosis, learner_mistake
from smart360.tutor.exam import (
    ExamItem,
    ExamResult,
    ExamRules,
    build_exam,
    class_b_rules,
    points_for,
    score_exam,
)
from smart360.tutor.mastery import MasteryState, compute
from smart360.tutor.planner import NextTask, SubtopicInfo, plan
from smart360.tutor.store import Attempt, LearnerStore

NOT_PROVABLE = "Diese Regel kann ich noch nicht zuverlässig belegen."
UNVERIFIED_NOTE = ("Hinweis: Diese Regel stammt aus einem Gesetz, dessen amtlicher Text hier noch nicht "
                   "abgeglichen werden konnte (FeV/StVG). Bitte mit aktueller Quelle prüfen.")


@dataclass
class OptionFeedback:
    text: str
    correct: bool  # is this option part of the correct answer?
    chosen: bool
    why: str


@dataclass
class Feedback:
    correct: bool
    options: list[OptionFeedback]
    rule: str
    source: str
    mnemonic: str
    diagnosis: Diagnosis | None
    similar: TheoryItem | None
    mastery_before: float
    mastery_after: float
    warnings: list[str] = field(default_factory=list)
    number_expected: str | None = None


class LearnSession:
    def __init__(self, store: LearnerStore, kb: KnowledgeBase | None = None, seed: int | None = None,
                 items: list[TheoryItem] | None = None):
        self.kb = kb or get_kb()
        self.store = store
        self.rng = random.Random(seed)
        self.items = items if items is not None else all_items(self.kb)
        self.by_sub: dict[str, list[TheoryItem]] = {}
        for it in self.items:
            self.by_sub.setdefault(it.subtopic, []).append(it)
        self.infos = [SubtopicInfo(sub, its[0].topic, max(i.exam_relevance for i in its))
                      for sub, its in sorted(self.by_sub.items())]

    # ------------------------------------------------------------------ planning
    def states(self, now: float | None = None) -> dict[str, MasteryState]:
        attempts = self.store.attempts()
        rel = {i.subtopic: i.exam_relevance for i in self.infos}
        return {s: compute(s, [a for a in attempts if a.subtopic == s], now, rel.get(s, 2))
                for s in {a.subtopic for a in attempts}}

    def next_tasks(self, now: float | None = None, limit: int = 5) -> list[NextTask]:
        return plan(self.infos, self.states(now), now, limit)

    def next_item(self, now: float | None = None) -> TheoryItem | None:
        for task in self.next_tasks(now, limit=10):
            if task.subtopic and task.subtopic in self.by_sub:
                return self._pick(task.subtopic)
        return None

    def _pick(self, subtopic: str, exclude: str | None = None) -> TheoryItem | None:
        seen = {a.item_id for a in self.store.attempts(subtopic)}
        pool = [i for i in self.by_sub.get(subtopic, []) if i.id != exclude]
        fresh = [i for i in pool if i.id not in seen] or pool
        return self.rng.choice(fresh) if fresh else None

    # ------------------------------------------------------------------ answering
    def submit(self, item: TheoryItem, chosen: set[int] | None = None, number: str | None = None,
               response_ms: int = 0, unsure: bool = False, now: float | None = None) -> Feedback:
        now = now or time.time()
        chosen = chosen or set()
        before = compute(item.subtopic, self.store.attempts(item.subtopic), now, item.exam_relevance).score
        if item.question.number_input:
            correct = _num_eq(number, item.number_answer)
        else:
            correct = chosen == set(item.correct)
        diagnosis = None if correct else learner_mistake(
            item.question.text, item.question.answers, chosen, set(item.correct),
            numeric=item.question.number_input, image=item.question.has_image)
        self.store.add(Attempt(now, item.id, item.topic, item.subtopic, item.variant, correct,
                               chosen=number if number else ",".join(map(str, sorted(chosen))),
                               expected=",".join(map(str, item.correct)) or (item.number_answer or ""),
                               response_ms=response_ms, difficulty=item.difficulty,
                               mistake_type=diagnosis.cause.value if diagnosis else "", mode="learn", unsure=unsure))
        after = compute(item.subtopic, self.store.attempts(item.subtopic), now, item.exam_relevance).score
        rule, source, mnemonic, warnings = self._rule_info(item)
        return Feedback(correct, self._explain_options(item, chosen), rule, source, mnemonic, diagnosis,
                        self._pick(item.subtopic, exclude=item.id), before, after, warnings, item.number_answer)

    def _rule_info(self, item: TheoryItem) -> tuple[str, str, str, list[str]]:
        obj = next((self.kb.objects[s] for s in item.sources if s in self.kb.objects), None)
        if obj is None:
            sign = next((s for s in self.kb.signs.values() if s.id in item.sources), None)
            if sign:
                src = sign.sources[-1]
                return sign.meaning, f"StVO {src.norm} (Zeichen {sign.number})", "", []
            return "", "Faustformel / Rechenregel" if item.id.startswith("CALC") else "", "", []
        src = obj.sources[0]
        where = f"{src.law} {src.norm or ''} {src.para or ''}".strip() if src.law else (src.ref or src.type)
        warnings = [UNVERIFIED_NOTE] if not self.kb.verified(obj.id) else []
        return obj.rule, where, obj.mnemonic, warnings

    def _explain_options(self, item: TheoryItem, chosen: set[int]) -> list[OptionFeedback]:
        if item.question.number_input:
            return []
        res = solve(item.question, self.kb)
        negative = "negative_question" in res.kinds
        out = []
        for i, text in enumerate(item.question.answers, start=1):
            ok = i in item.correct
            ev = res.evals[i - 1] if i - 1 < len(res.evals) else None
            expected = (Verdict.FALSE if negative else Verdict.TRUE) if ok else (Verdict.TRUE if negative else Verdict.FALSE)
            if ev is not None and ev.verdict == expected and ev.explanation:
                why = ev.explanation
            else:
                # the engine cannot back this option (UNKNOWN) or contradicts the answer key: never explain a rule
                # it cannot prove - only the answer key and an honest note
                why = ("Laut Lösung richtig. " if ok else "Laut Lösung falsch. ") + NOT_PROVABLE
            out.append(OptionFeedback(text, ok, i in chosen, why))
        return out


# ----------------------------------------------------------------------------- exam mode
@dataclass
class ExamSession:
    items: list[TheoryItem]
    rules: ExamRules
    started: float
    answers: dict[str, set[int]] = field(default_factory=dict)
    numbers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def start(cls, pool: list[TheoryItem], seed: int | None = None) -> ExamSession:
        rules = class_b_rules()
        candidates = [i for i in pool if not i.question.has_image or i.question.scene is not None]
        return cls(build_exam(candidates, rules, seed), rules, time.time())

    def answer(self, item_id: str, chosen: set[int] | None = None, number: str | None = None) -> None:
        """No feedback during the exam."""
        if number is not None:
            self.numbers[item_id] = number
        else:
            self.answers[item_id] = set(chosen or ())

    def finish(self, store: LearnerStore | None = None) -> ExamResult:
        exam_items = []
        given: dict[str, set[int]] = {}
        for it in self.items:
            if it.question.number_input:
                ok = _num_eq(self.numbers.get(it.id), it.number_answer)
                exam_items.append(ExamItem(it.id, points_for(it.exam_relevance), {0}, it.topic))
                given[it.id] = {0} if ok else set()
            else:
                exam_items.append(ExamItem(it.id, points_for(it.exam_relevance), set(it.correct), it.topic))
                given[it.id] = self.answers.get(it.id, set())
        result = score_exam(exam_items, given, self.rules)
        if store is not None:
            now = time.time()
            for it in self.items:
                ok = it.id not in result.wrong
                store.add(Attempt(now, it.id, it.topic, it.subtopic, it.variant, ok, mode="exam",
                                  difficulty=it.difficulty))
        return result


def _num_eq(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return False
    try:
        return abs(float(a.replace(",", ".")) - float(b.replace(",", "."))) < 0.051
    except ValueError:
        return False
