"""Knowledge base loader: knowledge/<topic>/*.json, numeric_rules.json, signs.json, concept_graph.json and the
official law snapshots (knowledge/sources/snapshots). Validated with pydantic on load."""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from smart360.theory.schema import TOPICS, Edge, KnowledgeObject, NumericRule, Sign
from smart360.theory.text import content


def knowledge_dir() -> Path:
    env = os.environ.get("SMART360_KNOWLEDGE")
    if env:
        return Path(env)
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        return Path(frozen) / "knowledge"
    return Path(__file__).resolve().parents[3] / "knowledge"


@dataclass
class KnowledgeBase:
    root: Path
    objects: dict[str, KnowledgeObject] = field(default_factory=dict)
    numeric: dict[str, NumericRule] = field(default_factory=dict)
    signs: dict[str, Sign] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    snapshots: dict[str, dict] = field(default_factory=dict)
    by_topic: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    by_concept: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    status: dict[str, str] = field(default_factory=dict)  # id -> verified | unverified | secondary
    evidence_errors: list[str] = field(default_factory=list)
    _vocab: frozenset[str] | None = field(default=None, repr=False)

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, root: Path | None = None) -> KnowledgeBase:
        root = Path(root) if root else knowledge_dir()
        kb = cls(root)
        for topic in TOPICS:
            for p in sorted((root / topic).glob("*.json")):
                data = json.loads(p.read_text(encoding="utf-8"))
                for raw in data["items"]:
                    obj = KnowledgeObject.model_validate(raw)
                    if obj.id in kb.objects:
                        raise ValueError(f"duplicate knowledge id {obj.id}")
                    if obj.topic != topic:
                        raise ValueError(f"{obj.id}: topic {obj.topic} stored under {topic}")
                    kb.objects[obj.id] = obj
                    kb.by_topic[topic].append(obj.id)
                    for c in obj.concepts:
                        kb.by_concept[c].append(obj.id)
        num = root / "numeric_rules.json"
        if num.exists():
            for raw in json.loads(num.read_text(encoding="utf-8"))["items"]:
                r = NumericRule.model_validate(raw)
                if r.id in kb.numeric:
                    raise ValueError(f"duplicate numeric id {r.id}")
                kb.numeric[r.id] = r
        sg = root / "signs.json"
        if sg.exists():
            for raw in json.loads(sg.read_text(encoding="utf-8"))["items"]:
                s = Sign.model_validate(raw)
                kb.signs[s.number] = s
        cg = root / "concept_graph.json"
        if cg.exists():
            kb.edges = [Edge.model_validate(e) for e in json.loads(cg.read_text(encoding="utf-8"))["edges"]]
        for p in sorted((root / "sources" / "snapshots").glob("*.json")):
            kb.snapshots[p.stem] = json.loads(p.read_text(encoding="utf-8"))
        kb._verify()
        return kb

    def _verify(self) -> None:
        """Check every law citation against the official snapshot.

        verified   - at least one law source whose evidence occurs verbatim in the snapshot of that norm
        unverified - cites a law that has no official snapshot yet (e.g. FeV/StVG/BKatV, not in the RIS test
                     phase): the engine must not answer confidently from it
        secondary  - only non-law sources (rule of thumb, authority text without snapshot)
        A citation whose evidence is NOT found in an existing snapshot is an error (evidence_errors)."""
        items: list = [*self.objects.values(), *self.numeric.values(), *self.signs.values()]  # type: ignore[type-arg]
        for it in items:
            ok, missing = False, False
            for s in it.sources:
                if s.type != "law" or not s.law:
                    continue
                if s.law not in self.snapshots:
                    missing = True
                    continue
                text = self.norm_text(s.law, s.norm or "")
                if text is None:
                    self.evidence_errors.append(f"{it.id}: {s.law} {s.norm} not in snapshot")
                elif not s.evidence or _ws(s.evidence) not in _ws(text):
                    self.evidence_errors.append(f"{it.id}: evidence not found in {s.law} {s.norm}: {s.evidence[:80]}")
                else:
                    ok = True
            if isinstance(it, NumericRule) and ok:
                ev = " ".join(s.evidence for s in it.sources)
                if _ws(it.value_text) not in _ws(ev):
                    self.evidence_errors.append(f"{it.id}: value_text {it.value_text!r} not in its evidence")
                    ok = False
            self.status[it.id] = "verified" if ok else ("unverified" if missing else "secondary")

    @property
    def vocabulary(self) -> frozenset[str]:
        """Lower-case words of the knowledge base and the official law snapshots (for OCR repair)."""
        if self._vocab is None:
            parts: list[str] = []
            for o in self.objects.values():
                parts += [o.title, o.rule, " ".join(o.keywords), " ".join(o.conditions), " ".join(o.exceptions)]
                parts += [" ".join(c.context) + " " + c.statement for c in o.claims]
            for sg in self.signs.values():
                parts += [sg.name, sg.meaning, " ".join(sg.keywords)]
            for snap in self.snapshots.values():
                parts += [n["text"] for n in snap["norms"].values()]
            self._vocab = frozenset(w.lower() for w in re.findall(r"[A-Za-zÄÖÜäöüß]+", " ".join(parts)))
        return self._vocab

    def verified(self, item_id: str) -> bool:
        return self.status.get(item_id) != "unverified"

    # ------------------------------------------------------------------ queries
    def norm_text(self, law: str, norm: str) -> str | None:
        snap = self.snapshots.get(law)
        n = snap["norms"].get(norm) if snap else None
        return n["text"] if n else None

    def neighbours(self, concept: str) -> set[str]:
        out = set()
        for e in self.edges:
            if e.a == concept:
                out.add(e.b)
            elif e.b == concept:
                out.add(e.a)
        return out

    def retrieve(self, text: str, limit: int = 8, topics: set[str] | None = None) -> list[tuple[float, KnowledgeObject]]:
        """Rule retrieval: content-word overlap with keywords/title/rule/claims, boosted by concept matches."""
        q = content(text)
        scored = []
        for obj in self.objects.values():
            if topics and obj.topic not in topics:
                continue
            kw = _object_words(obj)
            inter = len(q & kw)
            if not inter:
                continue
            score = inter / (len(q) ** 0.5 * len(kw) ** 0.25)
            scored.append((score, obj))
        scored.sort(key=lambda x: -x[0])
        return scored[:limit]


def _ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=4096)
def _words_for(obj_id: str, blob: str) -> frozenset[str]:
    return frozenset(content(blob))


def _object_words(obj: KnowledgeObject) -> frozenset[str]:
    blob = " ".join([obj.title, obj.rule, " ".join(obj.keywords), " ".join(obj.concepts),
                     " ".join(" ".join(c.context) + " " + c.statement for c in obj.claims)])
    return _words_for(obj.id, blob)


_KB: KnowledgeBase | None = None


def get_kb() -> KnowledgeBase:
    global _KB
    if _KB is None:
        _KB = KnowledgeBase.load()
    return _KB


def numeric_value(rule_id: str) -> float:
    return get_kb().numeric[rule_id].value
