"""Data splits and holdout enforcement.

    TRAIN            knowledge base (rules, claims, lexicon) + synthetic variants generated from it
    VALIDATION       adversarial / paraphrase variants generated from the rules with a different seed and
                     different transformations (generator.validation_items) - used to develop the engine
    DEVELOPMENT_GOLDEN tests/theory/golden/golden_v*.json (formerly "golden internal") - own questions, frozen.
                     Since the generalization milestone they are DEVELOPMENT SETS: they run as regression tests,
                     show errors and give historical numbers, but they must NOT produce claims, synonyms or
                     special rules and must not be used to tune single questions. They are no longer an
                     independent measurement (they were used for root-cause analysis).
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
    DEVELOPMENT_GOLDEN = "development_golden"
    GOLDEN_EXTERNAL = "golden_external"


GOLDEN_INTERNAL = Split.DEVELOPMENT_GOLDEN  # old name, kept for readers of older reports
HOLDOUT = frozenset({Split.DEVELOPMENT_GOLDEN, Split.GOLDEN_EXTERNAL})
DEVELOPMENT_GOLDEN_POLICY = (
    "development_golden: regression + historical metrics only - never a source of claims, synonyms, lexicon "
    "entries or special rules, never used to tune single questions")


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
    author: str = Field(min_length=1)  # who wrote / provided the question
    notes: str = ""
    leakage: str = ""  # set by the importer: "" or "POSSIBLE_LEAKAGE" (kept out of the independent metric)
    leakage_detail: str = ""

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


def load_development_golden(path: Path | None = None) -> list[TheoryItem]:
    """Development golden sets (v1, v2): regression tests and historical metrics only."""
    return load_golden_internal(path)


def load_golden_internal(path: Path | None = None) -> list[TheoryItem]:
    items = []
    for p in [path] if path else sorted(GOLDEN_DIR.glob("golden_v*.json")):
        for g in json.loads(p.read_text(encoding="utf-8"))["items"]:
            number = g.get("number")
            q = TheoryQuestion(g["q"], list(g.get("a", [])), number_input=number is not None,
                               sign_ids=list(g.get("signs", [])))
            items.append(TheoryItem(g["id"], g["topic"], g.get("subtopic", g["topic"]), "development_golden", q,
                                    tuple(g.get("c", [])), number_answer=number, sources=[]))
    return items


def load_golden_external(*, purpose: Literal["evaluation", "import_check"]) -> list[TheoryItem]:
    """External golden questions - evaluation only. Any other purpose is refused.
    'import_check' lets the importer compare new questions with the already imported ones (ids, duplicates)."""
    return [it.to_item() for it in load_external_records(purpose=purpose)]


def load_external_records(*, purpose: Literal["evaluation", "import_check"]) -> list[ExternalItem]:
    if purpose not in ("evaluation", "import_check"):
        raise PermissionError("golden_external is read-only evaluation data")
    out: list[ExternalItem] = []
    seen: set[str] = set()
    for p in sorted(EXTERNAL_DIR.glob("*.json")):
        if p.name == MANIFEST:
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for raw in data["items"] if isinstance(data, dict) else data:
            it = ExternalItem.model_validate(raw)
            if it.id in seen:
                raise ValueError(f"duplicate external id {it.id}")
            seen.add(it.id)
            out.append(it)
    return out


MANIFEST = "MANIFEST.json"  # sha256 of every imported file - imported files are never changed again
