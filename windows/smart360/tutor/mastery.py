"""Personal mastery model (0-100 per subtopic) and spaced repetition.

mastery = 100 x (recency-weighted Bayesian accuracy) x (evidence from distinct variants and days)
              x (0.5 + 0.5 x current retention), with caps so that ONE correct answer is never 'mastered':
  * fewer than 3 distinct variants answered correctly -> at most 70
  * only one attempt -> at most 50
  * correct answers given while unsure count 0.6, slow answers (> 60 s) 0.9, difficult items 1.3

Generalisation (mastery requires understanding, not recognition): a correct answer counts
  * 0.3 when the very same question was answered before, 0.6 for a known wording (variant) of the concept,
    1.0 for a new wording, 1.3 for a new level (exception / combination / situation),
  * x1.5 when it is a delayed retest (>= 1 day after the last correct answer of the concept).
Mastery >= 80 needs at least three difficulty levels and at least one delayed retest.

Retention R = exp(-days_since_last / S) with stability S (days): starts at 1, grows x(1.8 + 0.3 x difficulty)
after a correct answer that came after a real gap, shrinks to 40 % after a mistake. The next review is due
when R would fall to 0.8; weak and exam-critical subtopics come back sooner."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from smart360.tutor.store import Attempt

DAY = 86_400.0
TARGET_RETENTION = 0.8


@dataclass
class MasteryState:
    subtopic: str
    score: float  # 0..100
    attempts: int
    accuracy: float
    distinct_correct_variants: int
    stability_days: float
    retention: float
    last_seen: float | None
    due_at: float | None
    recent_mistakes: int
    mistake_types: dict[str, int] = field(default_factory=dict)
    unsure_rate: float = 0.0

    @property
    def mastered(self) -> bool:
        return self.score >= 80


def compute(subtopic: str, attempts: list[Attempt], now: float | None = None, exam_relevance: int = 2) -> MasteryState:
    now = now or time.time()
    att = sorted((a for a in attempts if a.subtopic == subtopic), key=lambda a: a.ts)
    if not att:
        return MasteryState(subtopic, 0.0, 0, 0.0, 0, 1.0, 0.0, None, None, 0)
    from smart360.tutor.levels import level_of_attempt

    alpha, beta = 1.0, 1.0
    stability = 1.0
    last_ts: float | None = None
    last_correct: float | None = None
    mistakes: dict[str, int] = {}
    seen_items: set[str] = set()
    seen_variants: set[str] = set()
    seen_levels: set[int] = set()
    delayed = False
    for a in att:
        age_days = (now - a.ts) / DAY
        w = 0.5 ** (age_days / 30)  # old evidence fades (half-life 30 days)
        if a.correct:
            lv = level_of_attempt(a)
            novelty = (0.3 if a.item_id in seen_items else 0.6 if a.variant in seen_variants
                       else 1.3 if lv >= 4 and lv not in seen_levels else 1.0)
            if last_correct is not None and (a.ts - last_correct) >= DAY:
                novelty *= 1.5
                delayed = True
            seen_items.add(a.item_id)
            seen_variants.add(a.variant)
            seen_levels.add(lv)
            last_correct = a.ts
            q = (0.6 if a.unsure else 1.0) * novelty
            q *= 0.9 if a.response_ms > 60_000 else 1.0
            q *= {1: 0.85, 2: 1.0, 3: 1.3}.get(a.difficulty, 1.0)
            alpha += w * q
            gap_days = (a.ts - last_ts) / DAY if last_ts else 0.0
            if gap_days >= 0.2 * stability or last_ts is None:
                stability *= 1.8 + 0.3 * a.difficulty
        else:
            beta += w * (1.3 if a.difficulty == 1 else 1.0)  # an easy item answered wrongly weighs more
            stability = max(0.5, stability * 0.4)
            if a.mistake_type:
                mistakes[a.mistake_type] = mistakes.get(a.mistake_type, 0) + 1
        last_ts = a.ts
    acc = alpha / (alpha + beta)
    distinct = len({a.variant for a in att if a.correct})
    days = len({int(a.ts // DAY) for a in att if a.correct})
    evidence = min(1.0, distinct / 3) * min(1.0, 0.6 + 0.4 * min(days, 2) / 2)
    retention = math.exp(-((now - (last_ts or now)) / DAY) / stability)
    score = 100 * acc * evidence * (0.5 + 0.5 * retention)
    if distinct < 3:
        score = min(score, 70.0)
    if len(seen_levels) < 3 or not delayed:
        score = min(score, 79.0)  # 'mastered' needs different levels AND a delayed retest
    if len(att) == 1:
        score = min(score, 50.0)
    recent = sum(1 for a in att[-5:] if not a.correct)
    interval_days = stability * math.log(1 / TARGET_RETENTION)
    interval_days *= {3: 0.7, 2: 1.0, 1: 1.2}.get(exam_relevance, 1.0)  # exam-critical topics come back sooner
    interval_days *= 0.5 if recent >= 2 else 1.0
    due = (last_ts or now) + interval_days * DAY
    unsure = sum(a.unsure for a in att) / len(att)
    return MasteryState(subtopic, round(score, 1), len(att), round(sum(a.correct for a in att) / len(att), 3),
                        distinct, round(stability, 3), round(retention, 3), last_ts, due, recent, mistakes,
                        round(unsure, 3))
