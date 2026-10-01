"""Data splits and holdout enforcement.

    TRAIN            knowledge base (rules, claims, lexicon) + synthetic variants generated from it
    VALIDATION       adversarial / paraphrase variants generated from the rules with a different seed and
                     different transformations (generator.validation_items) - used to develop the engine
    GOLDEN_INTERNAL  tests/theory/golden/golden_v*.json - own questions, frozen; evaluated, never trained on
    GOLDEN_EXTERNAL  tests/theory/golden_external/*.json - questions written by people / sources outside this
                     project. READ-ONLY EVALUATION: this module is the only code that reads them, and only
                     for purpose="evaluation" (tools/theory_eval.py). Tests enforce that nothing else - KB,
                     generator, lexicon, OCR vocabulary, AI prompts - reads or contains them.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from smart360.theory.generator import TheoryItem
from smart360.theory.reasoning import TheoryQuestion
from smart360.theory.schema import TOPICS

TESTS_DIR = Path(__file__).resolve().parents[2] / "tests" / "theory"
GOLDEN_DIR = TESTS_DIR / "golden"
EXTERNAL_DIR = TESTS_DIR / "golden_external"


class Split(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    GOLDEN_INTERNAL = "golden_internal"
    GOLDEN_EXTERNAL = "golden_external"


HOLDOUT = frozenset({Split.GOLDEN_INTERNAL, Split.GOLDEN_EXTERNAL})


class ExternalItem(BaseModel):
    """Import format for externally authored questions (see tests/theory/golden_external/README.md)."""

    model_config = ConfigDict(extra="forbid")
    id: str
    topic: str
    question: str
    answers: list[str] = Field(default_factory=list)
    correct: list[int] = Field(default_factory=list)  # 1-based; empty for number questions
    number: str | None = None  # expected number for number-input questions
    source: str  # must start with "external-", e.g. "external-human-authored"
    notes: str = ""

    @field_validator("source")
    @classmethod
    def _external(cls, v: str) -> str:
        if not v.startswith("external-"):
            raise ValueError("source must start with 'external-' (e.g. external-human-authored)")
        return v

    @field_validator("topic")
    @classmethod
    def _topic(cls, v: str) -> str:
        if v not in TOPICS:
            raise ValueError(f"unknown topic {v}")
        return v

    def to_item(self) -> TheoryItem:
        if self.number is None and (not self.answers or not self.correct
                                    or any(not 1 <= c <= len(self.answers) for c in self.correct)):
            raise ValueError(f"{self.id}: 'correct' must point into 'answers'")
        q = TheoryQuestion(self.question, list(self.answers), number_input=self.number is not None)
        return TheoryItem(self.id, self.topic, self.topic, "golden_external", q, tuple(self.correct),
                          number_answer=self.number, sources=[])


def load_golden_internal(path: Path | None = None) -> list[TheoryItem]:
    items = []
    for p in [path] if path else sorted(GOLDEN_DIR.glob("golden_v*.json")):
        for g in json.loads(p.read_text(encoding="utf-8"))["items"]:
            number = g.get("number")
            q = TheoryQuestion(g["q"], list(g.get("a", [])), number_input=number is not None,
                               sign_ids=list(g.get("signs", [])))
            items.append(TheoryItem(g["id"], g["topic"], g.get("subtopic", g["topic"]), "golden", q,
                                    tuple(g.get("c", [])), number_answer=number, sources=[]))
    return items


def load_golden_external(*, purpose: Literal["evaluation"]) -> list[TheoryItem]:
    """External golden questions - evaluation only. Any other purpose is refused."""
    if purpose != "evaluation":
        raise PermissionError("golden_external is read-only evaluation data")
    items: list[TheoryItem] = []
    seen: set[str] = set()
    for p in sorted(EXTERNAL_DIR.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for raw in data["items"] if isinstance(data, dict) else data:
            it = ExternalItem.model_validate(raw)
            if it.id in seen:
                raise ValueError(f"duplicate external id {it.id}")
            seen.add(it.id)
            items.append(it.to_item())
    return items
