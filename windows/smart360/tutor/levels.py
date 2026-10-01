"""Adaptive difficulty: the same concept is asked in harder and harder forms, never the same wording again.

    Level 1  direct rule              base, sign, calc, number input, licence
    Level 2  other wording            paraphrase, OCR noise, other units, sign paraphrase
    Level 3  distractor / negation    multiple choice with traps, changed numbers, wrong units, 'which is wrong?'
    Level 4  exception                exception and context variants
    Level 5  several rules combined   factor calculations, licence combinations, right-of-way chains
    Level 6  picture / situation      scene questions (images, videos)

The next level for a concept = one above the highest level solved correctly (and not failed since); after a
mistake at a level the learner stays there (or goes one down after two mistakes in a row).
"""

from __future__ import annotations

from smart360.theory.generator import TheoryItem
from smart360.tutor.store import Attempt

LEVEL_OF_VARIANT = {
    "base": 1, "sign": 1, "calc": 1, "number_input": 1, "licence": 1,
    "paraphrase": 2, "ocr_noise": 2, "calc_units": 2, "sign_paraphrase": 2, "sign_ocr": 2, "calc_ocr": 2,
    "multiselect": 3, "number_change": 3, "unit_error": 3, "negation": 3, "negative_question": 3,
    "exception": 4, "context": 4, "calc_factor_neg": 4,
    "calc_factor": 5, "licence_paraphrase": 5,
    "priority": 6,
}
MAX_LEVEL = 6
LEVEL_NAMES = {1: "direkte Regel", 2: "andere Formulierung", 3: "Distraktor", 4: "Ausnahme",
               5: "mehrere Regeln kombiniert", 6: "Bild / Situation"}


def level_of(item: TheoryItem) -> int:
    if item.question.scene is not None or item.question.has_image or item.question.frames:
        return 6
    return LEVEL_OF_VARIANT.get(item.variant, 2)


def level_of_attempt(a: Attempt) -> int:
    return LEVEL_OF_VARIANT.get(a.variant, 2)


def target_level(attempts: list[Attempt]) -> int:
    """Next level for one concept (subtopic) from its attempt history."""
    if not attempts:
        return 1
    att = sorted(attempts, key=lambda a: a.ts)
    best = 0
    for a in att:
        lv = level_of_attempt(a)
        if a.correct:
            best = max(best, lv)
        elif lv <= best:
            best = lv - 1  # failed a level already 'solved' -> it is not solved
    last_two = att[-2:]
    if len(last_two) == 2 and not any(a.correct for a in last_two):
        return max(1, min(level_of_attempt(last_two[-1]), best + 1) - 1)
    if not att[-1].correct:
        return max(1, level_of_attempt(att[-1]))
    return min(MAX_LEVEL, best + 1)


def pick_for_level(pool: list[TheoryItem], level: int, seen_items: set[str], seen_variants: set[str]) -> list[TheoryItem]:
    """Unseen items of the target level, preferring a wording (variant) not used yet; falls back to the nearest
    available level (higher first: the learner should be stretched, not bored)."""
    order = [level] + [lv for d in range(1, MAX_LEVEL) for lv in (level + d, level - d) if 1 <= lv <= MAX_LEVEL]
    for lv in order:
        cands = [i for i in pool if level_of(i) == lv and i.id not in seen_items]
        fresh = [i for i in cands if i.variant not in seen_variants]
        if fresh or cands:
            return fresh or cands
    return [i for i in pool if i.id not in seen_items] or pool
