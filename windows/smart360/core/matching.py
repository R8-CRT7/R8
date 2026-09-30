"""Question identity under OCR noise.

`same_question` answers "is the question on screen now the one the user approved?".
It is strict on meaning (numbers, whole words, answer set, image) and tolerant to
character-level OCR noise (resize, re-render, anti-aliasing)."""

from __future__ import annotations

from rapidfuzz import fuzz

from smart360.core.imaging import hamming
from smart360.core.models import Question, numeric_tokens


def words_compatible(a: str, b: str) -> bool:
    """OCR noise changes characters inside words; it does not insert or delete whole words.
    A long question with an added "nicht" is >97% similar by characters, so every differing
    word must have a close (OCR-like) counterpart at the same position."""
    wa, wb = a.split(), b.split()
    if len(wa) != len(wb):
        # merged/split words from OCR are allowed only if the joined text is identical
        return a.replace(" ", "") == b.replace(" ", "")
    for x, y in zip(wa, wb, strict=True):
        if x == y:
            continue
        if len(x) <= 3 or len(y) <= 3:
            return False  # short words carry meaning ("nie", "kein", numbers) - must be exact
        if fuzz.ratio(x, y) < 80:
            return False
    return True


def text_equivalent(a: str, b: str, threshold: float = 0.95) -> bool:
    if a == b:
        return True
    if numeric_tokens(a) != numeric_tokens(b):
        return False
    return fuzz.ratio(a, b) / 100.0 >= threshold and words_compatible(a, b)


def same_question(a: Question, b: Question, max_image_distance: int = 10) -> bool:
    if a.question_id == b.question_id:
        return True
    if a.question_type != b.question_type or len(a.answers) != len(b.answers):
        return False
    if a.has_image != b.has_image:
        return False
    if (
        a.image_hash is not None
        and b.image_hash is not None
        and hamming(a.image_hash, b.image_hash) > max_image_distance
    ):
        return False
    if not text_equivalent(a.normalized_text, b.normalized_text):
        return False
    # answers as a set (order may differ), matched 1:1
    remaining = list(b.normalized_answers)
    for ans in a.normalized_answers:
        hit = next((i for i, other in enumerate(remaining) if text_equivalent(ans, other, 0.92)), None)
        if hit is None:
            return False
        remaining.pop(hit)
    return True
