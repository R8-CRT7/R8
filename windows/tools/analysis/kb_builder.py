"""Helper for adding knowledge objects from the official text (used by the knowledge-completeness batches).

Every evidence string is checked verbatim against the official snapshot BEFORE anything is written; an object
whose evidence is not found is rejected. Claims are written in own words; FALSE claims are typical
misconceptions that contradict the cited provision.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KNOW = ROOT / "knowledge"


def _ws(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def snapshot_text(law: str, norm: str) -> str:
    snap = json.loads((KNOW / "sources" / "snapshots" / f"{law}.json").read_text(encoding="utf-8"))
    return _ws(snap["norms"][norm]["text"])


def src(law: str, norm: str, evidence: str, para: str | None = None) -> dict:
    if _ws(evidence) not in snapshot_text(law, norm):
        raise ValueError(f"evidence not in {law} {norm}: {evidence[:80]}")
    return {"type": "law", "law": law, "norm": norm, "para": para, "evidence": evidence, "ref": None}


def obj(id_: str, topic: str, sub: str, title: str, rule: str, sources: list[dict], keywords: list[str],
        concepts: list[str], claims: list[tuple[list[str], str, bool]], relevance: int = 3, difficulty: int = 2,
        mnemonic: str = "") -> dict:
    return {"id": id_, "version": 1, "valid_from": None, "valid_until": None, "last_verified": "2026-10-01",
            "sources": sources, "confidence": 1.0, "topic": topic, "subtopic": sub, "title": title, "rule": rule,
            "conditions": [], "exceptions": [], "numeric_refs": [], "concepts": concepts, "keywords": keywords,
            "claims": [{"context": c, "statement": s, "truth": t, "numbers": re.findall(r"\d+(?:,\d+)? ?(?:km/h|m|t|cm|l)\b", s) if t else []}
                       for c, s, t in claims],
            "mnemonic": mnemonic, "exam_relevance": relevance, "difficulty": difficulty}


def write(topic: str, filename: str, items: list[dict]) -> Path:
    p = KNOW / topic / filename
    ids = {o["id"] for o in items}
    for f in KNOW.glob("*/*.json"):
        if f == p or f.parent.name in ("sources", "semantics", "curation", "watch"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            clash = ids & {o.get("id") for o in data["items"] if isinstance(o, dict)}
            if clash:
                raise ValueError(f"duplicate ids {clash} in {f}")
    p.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return p
