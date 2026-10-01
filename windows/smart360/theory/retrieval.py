"""Hybrid rule-candidate retrieval.

    question -> A. structured conditions (RuleFrame of the question)
             -> B. lexical candidates      (content-word overlap, KnowledgeBase.retrieve)
             -> C. semantic candidates     (normalised concepts + character n-grams, TF-IDF cosine;
                                            optional pluggable embedding backend)
                + concept-graph expansion  (one hop, only typed relations - no free synonyms)
             -> D. specificity ranking     (matched / missing / contradicting conditions, source quality)
             -> E. rule verification       (reasoning.match_claims - deterministic, unchanged)

Semantic similarity NEVER decides an answer: it only proposes candidate rules. TRUE/FALSE always comes from
the deterministic claim/number/sign/priority checks in reasoning.py.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol

from smart360.theory.kb import KnowledgeBase
from smart360.theory.schema import KnowledgeObject
from smart360.theory.semantics import (
    action_concepts,
    canonicalize,
    conditions,
    load_lexicon,
    question_intent,
    situations,
)
from smart360.theory.text import content, fold, numbers

# ----------------------------------------------------------------------------- A. semantic representation
SOURCE_QUALITY = {"verified": 1.0, "secondary": 0.8, "unverified": 0.5}


@dataclass(frozen=True)
class RuleFrame:
    """Structured meaning of a rule (or of a question): what kind of statement, who, doing what, where."""

    intents: frozenset[str] = frozenset()  # REQUIRED_ACTION, PERMISSION, PROHIBITION, PRIORITY, SPEED, DISTANCE ...
    actors: frozenset[str] = frozenset()  # pkw, lkw, kraftrad, fahrrad, fussganger, schienenfahrzeug, ...
    actions: frozenset[str] = frozenset()  # lexicon action concepts (YIELD, STOP, ...)
    objects: frozenset[str] = frozenset()  # lexicon object concepts (CROSSWALK, TRAFFIC_LIGHT, ...)
    road_context: str | None = None  # innerorts | außerorts | autobahn
    vehicle_context: frozenset[str] = frozenset()  # vehicle classes + 'trailer'
    conditions: frozenset[str] = frozenset()  # weather, traffic state, visibility, age ...
    exceptions: frozenset[str] = frozenset()  # 'ohne X' / exception terms
    modality: frozenset[str] = frozenset()  # must / may / must_not / should
    numeric_constraints: tuple[tuple[str, float, str], ...] = ()  # (quantity, value, unit)
    traffic_signs: frozenset[str] = frozenset()
    priority_relation: bool = False

    def describe(self) -> dict:
        return {k: (sorted(v) if isinstance(v, frozenset) else v) for k, v in self.__dict__.items()}


_ACTORS = {"pkw": r"\bpkw\b", "lkw": r"\blkw\b", "kraftrad": r"\bkraftrad", "fahrrad": r"\bfahrrad|\bradfahr",
           "fussganger": r"fussgänger|fußgänger", "schienenfahrzeug": r"schienenfahrzeug", "bus": r"\bbus\b|omnibus",
           "einsatzfahrzeug": r"einsatzfahrzeug|ceinsatzx|rettungswagen|polizei", "kind": r"\bkind",
           "gegenverkehr": r"gegenverkehr"}
_MODAL = (("must_not", r"\b(darf|dürfen) nicht\b|\bverboten\b|\bunzulässig\b|\buntersagt\b|\bnicht erlaubt\b"),
          ("must", r"\b(muss|müssen)\b|\bpflicht\b|\bvorgeschrieben\b"),
          ("may", r"\b(darf|dürfen)\b|\berlaubt\b|\bzulässig\b"),
          ("should", r"\b(sollte|sollten|soll)\b"))
_QUANTITY_OF_UNIT = {"km/h": "speed", "m": "distance", "cm": "distance", "mm": "depth", "km": "distance",
                     "kg": "mass", "t": "mass", "s": "time", "min": "time", "tage": "time", "monate": "time",
                     "jahre": "age_or_time", "‰": "alcohol", "%": "share", "punkte": "points", "l": "volume"}


def frame_of(text: str) -> RuleFrame:
    canon = canonicalize(text)
    t = canon.text
    cond = conditions(text)
    lex = load_lexicon()
    by_id = {e.id: e.concept for e in lex.entries}
    applied = {by_id[a] for a in canon.applied if a in by_id}
    # every lexicon entry that matched names a concept (objects rewrite to plain words, actions to tokens)
    objects = frozenset(c for c in canon.concepts | applied if c not in lex.action_concepts and not c.startswith("CTX"))
    actors = frozenset(a for a, rx in _ACTORS.items() if re.search(rx, t))
    modal = frozenset(m for m, rx in _MODAL if re.search(rx, t))
    nums = tuple((_QUANTITY_OF_UNIT.get(u, "number"), v, u) for v, u in numbers(text) if u)
    cnds = set(cond.weather) | set(cond.traffic_state)
    if cond.visibility_m is not None:
        cnds.add("visibility")
    if cond.age_years is not None:
        cnds.add("age")
    vehicles = set(cond.vehicle) | ({"trailer"} if cond.trailer else set())
    return RuleFrame(
        intents=frozenset(question_intent(text)), actors=actors, actions=frozenset(action_concepts(text)),
        objects=objects, road_context=cond.road_context, vehicle_context=frozenset(vehicles),
        conditions=frozenset(cnds), exceptions=frozenset(cond.excluded), modality=modal, numeric_constraints=nums,
        traffic_signs=situations(text).get("SIGN", frozenset()),
        priority_relation=bool(re.search(r"vorfahrt|vorrang|zuerst|cyieldx|cinsistx|cgofirstx", t)))


def _object_text(obj: KnowledgeObject) -> str:
    return " ".join([obj.title, obj.rule, *obj.keywords,
                     *(" ".join(c.context) + ". " + c.statement for c in obj.claims)])


@lru_cache(maxsize=1024)
def _frame_cached(obj_id: str, text: str) -> RuleFrame:
    return frame_of(text)


def rule_frame(obj: KnowledgeObject) -> RuleFrame:
    return _frame_cached(obj.id, _object_text(obj))


# ----------------------------------------------------------------------------- D. structural match
@dataclass
class StructuralMatch:
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)  # named by the question, absent from the rule
    contradicting: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        return len(self.matched) - 0.5 * len(self.missing) - 2.0 * len(self.contradicting)


_EXCLUSIVE_ROADS = {("innerorts", "außerorts"), ("innerorts", "autobahn")}


def compare(q: RuleFrame, r: RuleFrame) -> StructuralMatch:
    """Question frame vs rule frame. Contradiction = both name a value and the values exclude each other."""
    m = StructuralMatch()
    for name in ("actions", "objects", "actors", "conditions", "traffic_signs", "vehicle_context"):
        qa, ra = getattr(q, name), getattr(r, name)
        m.matched += [f"{name}:{x}" for x in qa & ra]
        m.missing += [f"{name}:{x}" for x in qa - ra]
    if q.road_context and r.road_context:
        if q.road_context == r.road_context:
            m.matched.append(f"road:{q.road_context}")
        elif (q.road_context, r.road_context) in _EXCLUSIVE_ROADS or (r.road_context, q.road_context) in _EXCLUSIVE_ROADS:
            m.contradicting.append(f"road:{q.road_context}/{r.road_context}")
    if q.traffic_signs and r.traffic_signs and not q.traffic_signs & r.traffic_signs:
        m.contradicting.append("sign:" + "/".join(sorted(q.traffic_signs)))
    if q.exceptions & (r.vehicle_context | r.conditions):
        m.contradicting.append("excluded:" + ",".join(sorted(q.exceptions & (r.vehicle_context | r.conditions))))
    if q.priority_relation and r.priority_relation:
        m.matched.append("priority")
    return m


# ----------------------------------------------------------------------------- C. semantic candidates
class EmbeddingBackend(Protocol):
    """Optional: any local or remote embedding model. Used ONLY to propose candidate rules."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


_BACKEND: EmbeddingBackend | None = None


def set_embedding_backend(backend: EmbeddingBackend | None) -> None:
    """Plug in an embedding model (none by default - no new dependency). Clears the cached index."""
    global _BACKEND
    _BACKEND = backend
    _semantic_index.cache_clear()


def _sem_tokens(text: str) -> dict[str, float]:
    from smart360.theory.reasoning import _core

    toks: dict[str, float] = dict.fromkeys(_core(text), 1.0)
    f = re.sub(r"[^a-zäöüß ]", " ", fold(text))
    for w in f.split():
        if len(w) >= 5:
            for i in range(len(w) - 3):
                g = "#" + w[i:i + 4]
                toks[g] = toks.get(g, 0.0) + 0.25  # character 4-grams: morphology / compounds / OCR noise
    return toks


@dataclass
class _SemIndex:
    ids: list[str]
    vecs: list[dict[str, float]]
    idf: dict[str, float]
    dense: list[list[float]] | None = None
    postings: dict[str, list[tuple[int, float]]] = field(default_factory=dict)


def _tfidf(tok: dict[str, float], idf: dict[str, float]) -> dict[str, float]:
    v = {t: c * idf.get(t, 1.0) for t, c in tok.items()}
    n = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {t: x / n for t, x in v.items()}


@lru_cache(maxsize=4)
def _semantic_index(kb_key: int, texts: tuple[tuple[str, str], ...]) -> _SemIndex:
    toks = [(i, _sem_tokens(t)) for i, t in texts]
    df: Counter[str] = Counter()
    for _, tk in toks:
        df.update(set(tk))
    n = len(toks)
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
    idx = _SemIndex([i for i, _ in toks], [_tfidf(tk, idf) for _, tk in toks], idf)
    for d, vec in enumerate(idx.vecs):
        for t, w in vec.items():
            idx.postings.setdefault(t, []).append((d, w))
    if _BACKEND is not None:
        idx.dense = _BACKEND.embed([t for _, t in texts])
    return idx


def _index_for(kb: KnowledgeBase) -> _SemIndex:
    texts = tuple((o.id, _object_text(o)) for o in kb.objects.values())
    return _semantic_index(id(kb), texts)


def semantic_candidates(text: str, kb: KnowledgeBase, k: int = 12) -> list[tuple[float, str]]:
    idx = _index_for(kb)
    qv = _tfidf(_sem_tokens(expand_query(text, kb)), idx.idf)
    acc = [0.0] * len(idx.ids)
    for t, w in qv.items():
        for d, dw in idx.postings.get(t, ()):
            acc[d] += w * dw
    scores = list(zip(acc, idx.ids, strict=True))
    if idx.dense is not None and _BACKEND is not None:
        q = _BACKEND.embed([text])[0]
        qn = math.sqrt(sum(x * x for x in q)) or 1.0
        for i, vec in enumerate(idx.dense):
            vn = math.sqrt(sum(x * x for x in vec)) or 1.0
            cos = sum(a * b for a, b in zip(q, vec, strict=False)) / (qn * vn)
            scores[i] = (0.5 * scores[i][0] + 0.5 * cos, scores[i][1])
    scores.sort(reverse=True)
    return scores[:k]


# ----------------------------------------------------------------------------- concept-graph expansion
_EXPAND_RELATIONS = frozenset({"requires", "part_of", "exception_of", "related"})


def expand_query(text: str, kb: KnowledgeBase) -> str:
    """Adds the one-hop neighbours of concepts named in the question (typed relations only, no free synonyms):
    'Fußgänger beim Abbiegen' may also look for 'vorrang', 'abbiegen' rules linked in the concept graph."""
    words = set(content(text))
    extra: set[str] = set()
    for e in kb.edges:
        if e.relation not in _EXPAND_RELATIONS:
            continue
        a, b = content(e.a.replace("_", " ")), content(e.b.replace("_", " "))
        if a and a <= words:
            extra.add(e.b.replace("_", " "))
        if b and b <= words and e.relation in ("related", "part_of"):
            extra.add(e.a.replace("_", " "))
    return text + (" " + " ".join(sorted(extra)) if extra else "")


# ----------------------------------------------------------------------------- hybrid retriever
@dataclass
class Candidate:
    obj: KnowledgeObject
    lexical: float = 0.0
    semantic: float = 0.0
    structure: StructuralMatch = field(default_factory=StructuralMatch)
    source_quality: float = 1.0
    channels: set[str] = field(default_factory=set)

    @property
    def rank(self) -> float:
        if self.structure.contradicting and not self.structure.matched:
            return -1.0
        return (self.lexical + self.semantic + 0.15 * self.structure.score) * self.source_quality


def hybrid_retrieve(text: str, kb: KnowledgeBase, limit: int = 12) -> list[Candidate]:
    q_frame = frame_of(text)
    cands: dict[str, Candidate] = {}
    lex = kb.retrieve(text, limit=limit)
    top_lex = lex[0][0] if lex else 1.0
    for s, o in lex:
        c = cands.setdefault(o.id, Candidate(o))
        c.lexical = s / top_lex if top_lex else 0.0
        c.channels.add("lexical")
    sem = semantic_candidates(text, kb, k=limit)
    top_sem = sem[0][0] if sem and sem[0][0] > 0 else 1.0
    for s, oid in sem:
        if s <= 0:
            continue
        c = cands.setdefault(oid, Candidate(kb.objects[oid]))
        c.semantic = s / top_sem
        c.channels.add("semantic")
    for c in cands.values():
        c.structure = compare(q_frame, rule_frame(c.obj))
        c.source_quality = SOURCE_QUALITY.get(kb.status.get(c.obj.id, "verified"), 0.8)
    ranked = sorted(cands.values(), key=lambda c: -c.rank)
    return ranked[:limit]


def warm_up(kb: KnowledgeBase) -> None:
    """Build the semantic index and the rule frames once (app start), so the first question is not slow."""
    _index_for(kb)
    for o in kb.objects.values():
        rule_frame(o)


@lru_cache(maxsize=20_000)
def claim_frame(text: str) -> RuleFrame:
    return frame_of(text)


def structural_conflict(q: RuleFrame, c: RuleFrame) -> str | None:
    """A claim whose situation explicitly contradicts the question: other road context (innerorts vs außerorts)
    or a different, explicitly named vehicle class (question 'Lkw', claim only about 'Pkw')."""
    if q.road_context and c.road_context and q.road_context != c.road_context and (
            (q.road_context, c.road_context) in _EXCLUSIVE_ROADS or (c.road_context, q.road_context) in _EXCLUSIVE_ROADS):
        return f"road {q.road_context}/{c.road_context}"
    qv, cv = q.vehicle_context - {"trailer"}, c.vehicle_context - {"trailer"}
    if qv and cv and not qv & cv:
        return f"vehicle {','.join(sorted(qv))}/{','.join(sorted(cv))}"
    return None


def channel_stats(cands: list[Candidate]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for c in cands:
        out["+".join(sorted(c.channels))] += 1
    return dict(out)
