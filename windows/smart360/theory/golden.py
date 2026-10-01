"""Golden set loader (tests/theory/golden/*.json). The golden set is evaluated, never tuned against."""

from __future__ import annotations

import json
from pathlib import Path

from smart360.theory.generator import TheoryItem
from smart360.theory.reasoning import TheoryQuestion

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "tests" / "theory" / "golden"


def load_golden(path: Path | None = None) -> list[TheoryItem]:
    items = []
    for p in [path] if path else sorted(GOLDEN_DIR.glob("golden_v*.json")):
        for g in json.loads(p.read_text(encoding="utf-8"))["items"]:
            number = g.get("number")
            q = TheoryQuestion(g["q"], list(g.get("a", [])), number_input=number is not None,
                               sign_ids=list(g.get("signs", [])))
            items.append(TheoryItem(g["id"], g["topic"], g.get("subtopic", g["topic"]), "golden", q,
                                    tuple(g.get("c", [])), number_answer=number, sources=[]))
    return items
