"""Core domain models shared by every layer.

Everything here is plain data (no Qt, no I/O) so it can be unit tested and
shared with the engine thread without locking concerns: all models are frozen.
"""

from __future__ import annotations

import hashlib
import re
import time
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum

# --------------------------------------------------------------------------- geometry


@dataclass(frozen=True, slots=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)

    @property
    def area(self) -> int:
        return max(0, self.w) * max(0, self.h)

    def translated(self, dx: int, dy: int) -> Rect:
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h

    def is_valid(self) -> bool:
        return self.w > 0 and self.h > 0


@dataclass(frozen=True, slots=True)
class NormRect:
    """A rectangle relative to a window client area (0..1). Survives move/resize."""

    x: float
    y: float
    w: float
    h: float

    def to_abs(self, frame: Rect) -> Rect:
        return Rect(
            frame.x + round(self.x * frame.w),
            frame.y + round(self.y * frame.h),
            max(1, round(self.w * frame.w)),
            max(1, round(self.h * frame.h)),
        )

    @staticmethod
    def from_abs(r: Rect, frame: Rect) -> NormRect:
        if frame.w <= 0 or frame.h <= 0:
            raise ValueError("frame must have a positive size")
        return NormRect((r.x - frame.x) / frame.w, (r.y - frame.y) / frame.h, r.w / frame.w, r.h / frame.h)

    def is_valid(self) -> bool:
        return 0.0 <= self.x <= 1.0 and 0.0 <= self.y <= 1.0 and self.w > 0.0 and self.h > 0.0


# --------------------------------------------------------------------------- text helpers

_WS = re.compile(r"\s+")
_NON_WORD = re.compile(r"[^\w%/.,+\-]", re.UNICODE)
_NUMBERS = re.compile(r"\d+(?:[.,]\d+)?")


def normalize_text(text: str) -> str:
    """Canonical form used for hashing and similarity (case/whitespace/quote insensitive)."""
    t = unicodedata.normalize("NFKC", text).casefold()
    t = t.replace("ß", "ss")
    t = _NON_WORD.sub(" ", t)
    return _WS.sub(" ", t).strip()


def numeric_tokens(text: str) -> tuple[str, ...]:
    """All numbers in order. Two questions that differ only by '50 km/h' vs '70 km/h'
    are textually ~98% similar, so numbers are compared exactly by the cache."""
    return tuple(n.replace(",", ".") for n in _NUMBERS.findall(text))


# --------------------------------------------------------------------------- question


class QuestionType(StrEnum):
    SINGLE_OR_MULTI = "choice"  # 360° / official catalog: one or more correct boxes
    NUMBER_INPUT = "number"  # "Zahl eingeben" questions
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AnswerOption:
    index: int  # 1-based, top to bottom as displayed
    text: str
    bbox: Rect | None = None  # absolute screen coordinates of the whole answer row
    checkbox: Rect | None = None  # click target (left part of the row)
    ocr_confidence: float = 1.0
    checkbox_found: bool = True  # False = position estimated (no box edges found) - safe mode won't click


@dataclass(frozen=True, slots=True)
class Question:
    text: str
    answers: tuple[AnswerOption, ...]
    question_type: QuestionType = QuestionType.SINGLE_OR_MULTI
    image_hash: int | None = None  # dHash of the situation image, None if there is no image
    has_image: bool = False
    ocr_confidence: float = 1.0
    layout_confidence: float = 1.0
    image_clarity: float = 1.0
    captured_at: float = field(default_factory=time.time)
    # Encoded PNG crops, kept in memory only (ephemeral, never persisted unless debug)
    question_png: bytes | None = field(default=None, repr=False, compare=False)
    answers_png: bytes | None = field(default=None, repr=False, compare=False)
    image_png: bytes | None = field(default=None, repr=False, compare=False)

    @property
    def normalized_text(self) -> str:
        return normalize_text(self.text)

    @property
    def normalized_answers(self) -> tuple[str, ...]:
        return tuple(normalize_text(a.text) for a in self.answers)

    @property
    def fingerprint(self) -> str:
        """Identity of the *visible* question. Two captures of the same screen produce the
        same fingerprint; a different question produces a different one."""
        h = hashlib.sha256()
        h.update(self.normalized_text.encode())
        for a in self.normalized_answers:
            h.update(b"\x1f" + a.encode())
        h.update(b"\x1e" + self.question_type.value.encode())
        if self.image_hash is not None:
            # coarse bucket so tiny rendering noise does not change the identity
            h.update(b"\x1d" + str(self.image_hash >> 16).encode())
        return h.hexdigest()[:24]

    @property
    def question_id(self) -> str:
        return self.fingerprint

    def answer_by_index(self, idx: int) -> AnswerOption | None:
        for a in self.answers:
            if a.index == idx:
                return a
        return None


# --------------------------------------------------------------------------- prediction


class PredictionSource(StrEnum):
    AI = "ai"
    CACHE = "cache"
    MOCK = "mock"


@dataclass(frozen=True, slots=True)
class Prediction:
    question_id: str
    answers: tuple[int, ...]  # 1-based indices into Question.answers
    model_confidence: float
    confidence: float  # composite (see confidence.py)
    reason: str
    uncertain: bool
    source: PredictionSource
    model: str = ""
    topic: str = ""
    number_answer: str | None = None
    latency_ms: float = 0.0
    confidence_breakdown: tuple[tuple[str, float], ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def needs_manual_check(self) -> bool:
        return self.uncertain


class Decision(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SKIPPED = "skipped"  # question changed before the user decided
    FAILED = "failed"  # accepted but execution failed
    DRY_RUN = "dry_run"  # accepted in dry-run mode: targets shown, nothing clicked


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    question_id: str
    question_text: str
    answers: tuple[str, ...]
    recommended: tuple[int, ...]
    confidence: float
    decision: Decision
    topic: str
    source: str
    processing_ms: float
    timestamp: float
    uncertain: bool
    ocr_confidence: float
    model: str = ""
    id: int | None = None
