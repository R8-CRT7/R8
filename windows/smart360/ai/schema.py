"""Structured response contract shared by all providers.

Providers use the provider-native structured-output feature with SOLVE_JSON_SCHEMA
*and* the result is validated again with pydantic - never trust free text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

TOPICS = (
    "Vorfahrt",
    "Verkehrszeichen",
    "Geschwindigkeit",
    "Abstand",
    "Überholen",
    "Verhalten",
    "Gefahrenlehre",
    "Technik",
    "Umwelt",
    "Recht",
    "Sonstiges",
)

SOLVE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answers": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "1-based indices of ALL correct answers (empty for number questions)",
        },
        "number_answer": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "description": "Only for number-input questions: the number to enter, else null",
        },
        "confidence": {"type": "number", "description": "0.0 - 1.0"},
        "reason": {"type": "string", "description": "max 2 short German sentences"},
        "uncertain": {"type": "boolean"},
        "topic": {"type": "string", "enum": list(TOPICS)},
    },
    "required": ["answers", "number_answer", "confidence", "reason", "uncertain", "topic"],
    "additionalProperties": False,
}


class SolveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    answers: list[int] = Field(default_factory=list)
    number_answer: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=600)
    uncertain: bool
    topic: str = "Sonstiges"

    @field_validator("answers")
    @classmethod
    def _unique_positive(cls, v: list[int]) -> list[int]:
        if any(a < 1 for a in v):
            raise ValueError("answer indices are 1-based")
        if len(set(v)) != len(v):
            raise ValueError("duplicate answers")
        return sorted(v)

    @field_validator("topic")
    @classmethod
    def _topic(cls, v: str) -> str:
        return v if v in TOPICS else "Sonstiges"

    @field_validator("number_answer")
    @classmethod
    def _number(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        cleaned = v.strip().replace(" ", "")
        if not all(c.isdigit() or c in ",." for c in cleaned) or len(cleaned) > 12:
            raise ValueError("number_answer must be numeric")
        return cleaned


class SchemaViolation(ValueError):
    pass


def parse_solve_response(raw: str | dict[str, Any], answer_count: int, number_question: bool) -> SolveResponse:
    """Validate a provider response against the schema AND the visible question."""
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        resp = SolveResponse.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise SchemaViolation(f"invalid structured response: {exc}") from exc
    if number_question:
        if resp.number_answer is None and not resp.uncertain:
            raise SchemaViolation("number question without number_answer")
    else:
        if any(a > answer_count for a in resp.answers):
            raise SchemaViolation(f"answer index out of range (have {answer_count})")
        if not resp.answers and not resp.uncertain:
            raise SchemaViolation("no answer selected")
    return resp


@dataclass(frozen=True, slots=True)
class SolveRequest:
    question_text: str
    answers: tuple[str, ...]
    number_question: bool = False
    question_png: bytes | None = None
    answers_png: bytes | None = None
    image_png: bytes | None = None
    ocr_confidence: float = 1.0
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        import hashlib

        h = hashlib.sha256(self.question_text.encode())
        for a in self.answers:
            h.update(b"\x1f" + a.encode())
        if self.image_png:
            h.update(hashlib.sha256(self.image_png).digest())
        return h.hexdigest()


@dataclass(frozen=True, slots=True)
class SolveResult:
    response: SolveResponse
    model: str
    provider: str
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
