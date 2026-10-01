"""Leakage detection: is an external question (too) similar to anything the engine was built or tuned on?

Reference corpus (everything the engine "has seen"):
    claims        claim statements + rule texts + titles of the knowledge base
    generator     synthetic training items and validation items (questions and options)
    development   the development golden sets v1/v2
    lexicon       the patterns of knowledge/semantics/lexicon.json (regex syntax stripped)
    prompts       string literals of the AI prompts (smart360/ai)

Two similarity measures, both must stay below their limit:
    lexical      Jaccard of stemmed content words           (>= LEXICAL_LIMIT -> leak)
    semantic     cosine of the normalised representation     (>= SEMANTIC_LIMIT -> leak)
                 (canonical concepts, compound parts, participles - see reasoning._core)

Texts with fewer than MIN_WORDS content words are ignored (single words like 'Rechts' are no leakage).
A question is POSSIBLE_LEAKAGE if its text is a near copy of a reference question / rule, or if the majority of
its options are near copies of reference texts. Leaked items stay in the set but are excluded from the
independent main metric.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from smart360.theory.text import content

LEXICAL_LIMIT = 0.8
SEMANTIC_LIMIT = 0.9
MIN_WORDS = 4
POSSIBLE_LEAKAGE = "POSSIBLE_LEAKAGE"


@dataclass(frozen=True)
class RefText:
    source: str  # claims | generator | development | lexicon | prompts
    text: str
    lex: frozenset[str]
    sem: frozenset[str]


@dataclass
class LeakHit:
    part: str  # question | answer N
    source: str
    reference: str
    lexical: float
    semantic: float


@dataclass
class LeakReport:
    item_id: str
    leak: bool
    hits: list[LeakHit] = field(default_factory=list)

    @property
    def detail(self) -> str:
        return "; ".join(f"{h.part}~{h.source} (lex {h.lexical:.2f}, sem {h.semantic:.2f}): {h.reference[:60]}"
                         for h in self.hits[:3])


def _sem(text: str) -> frozenset[str]:
    from smart360.theory.reasoning import _core

    return frozenset(_core(text))


def _ref(source: str, text: str) -> RefText | None:
    lex = frozenset(content(text))
    if len(lex) < MIN_WORDS:
        return None
    return RefText(source, text, lex, _sem(text))


def _lexicon_texts(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for e in data.get("entries", []):
        for p in e.get("patterns", []):
            out.append(re.sub(r"\\w\*|\\b|\(\?[^)]*\)|[()\[\]?*+|\\{}0-9,^$]", " ", p))
    return out


def _prompt_texts(ai_dir: Path) -> list[str]:
    out = []
    for p in ai_dir.rglob("*.py"):
        out += re.findall(r'"([^"]{20,})"', p.read_text(encoding="utf-8"))
        out += [s for s in re.findall(r'"""(.*?)"""', p.read_text(encoding="utf-8"), re.S) if len(s) > 20]
    return [line for t in out for line in re.split(r"[\n.]", t) if line.strip()]


class ReferenceCorpus:
    """Inverted index over the reference texts (content words -> texts) for fast near-duplicate search."""

    def __init__(self, refs: list[RefText]):
        self.refs = refs
        self.index: dict[str, list[int]] = defaultdict(list)
        for i, r in enumerate(refs):
            for w in r.lex | r.sem:
                self.index[w].append(i)

    def best(self, text: str) -> tuple[RefText | None, float, float]:
        lex, sem = frozenset(content(text)), _sem(text)
        if len(lex) < MIN_WORDS:
            return None, 0.0, 0.0
        counts: dict[int, int] = defaultdict(int)
        for w in lex | sem:
            for i in self.index.get(w, ()):
                counts[i] += 1
        best, bl, bs = None, 0.0, 0.0
        for i, _ in sorted(counts.items(), key=lambda x: -x[1])[:200]:
            r = self.refs[i]
            jl = len(lex & r.lex) / len(lex | r.lex)
            cs = len(sem & r.sem) / (len(sem) * len(r.sem)) ** 0.5 if sem and r.sem else 0.0
            if max(jl / LEXICAL_LIMIT, cs / SEMANTIC_LIMIT) > max(bl / LEXICAL_LIMIT, bs / SEMANTIC_LIMIT):
                best, bl, bs = r, jl, cs
        return best, bl, bs


@lru_cache(maxsize=1)
def default_corpus() -> ReferenceCorpus:
    """Everything the engine was built or developed on (never the external set)."""
    from smart360.theory import generator
    from smart360.theory.kb import KnowledgeBase, knowledge_dir
    from smart360.theory.splits import load_development_golden

    kb = KnowledgeBase.load()
    raw: list[tuple[str, str]] = []
    for o in kb.objects.values():
        raw += [("claims", o.rule), ("claims", o.title)]
        raw += [("claims", c.statement) for c in o.claims]
    for sg in kb.signs.values():
        raw.append(("claims", sg.meaning))
    for it in generator.all_items(kb) + generator.validation_items(kb):
        raw.append(("generator", it.question.text))
        raw += [("generator", a) for a in it.question.answers]
    for it in load_development_golden():
        raw.append(("development", it.question.text))
        raw += [("development", a) for a in it.question.answers]
    raw += [("lexicon", t) for t in _lexicon_texts(knowledge_dir() / "semantics" / "lexicon.json")]
    raw += [("prompts", t) for t in _prompt_texts(Path(__file__).resolve().parents[1] / "ai")]
    seen: set[tuple[str, str]] = set()
    refs = []
    for src, t in raw:
        if (src, t) in seen:
            continue
        seen.add((src, t))
        r = _ref(src, t)
        if r:
            refs.append(r)
    return ReferenceCorpus(refs)


def check_item(item_id: str, question: str, answers: list[str], corpus: ReferenceCorpus | None = None) -> LeakReport:
    corpus = corpus or default_corpus()
    rep = LeakReport(item_id, False)

    def leaked(lex: float, sem: float) -> bool:
        return lex >= LEXICAL_LIMIT or sem >= SEMANTIC_LIMIT

    ref, lx, sm = corpus.best(question)
    if ref and leaked(lx, sm):
        rep.hits.append(LeakHit("question", ref.source, ref.text, lx, sm))
        rep.leak = True
    leaked_answers = 0
    checked = 0
    for i, a in enumerate(answers, start=1):
        ref, lx, sm = corpus.best(a)
        if ref is None and len(content(a)) < MIN_WORDS:
            continue
        checked += 1
        if ref and leaked(lx, sm):
            leaked_answers += 1
            rep.hits.append(LeakHit(f"answer {i}", ref.source, ref.text, lx, sm))
    if checked >= 2 and leaked_answers * 2 > checked:
        rep.leak = True
    return rep
