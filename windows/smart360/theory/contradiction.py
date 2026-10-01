"""Contradiction index - built only from the knowledge base and the lexicon, never from test questions.

Relations (a RELATION b):
    contradicts        the two cannot both hold in the same situation
                       - incompatible action concepts of the lexicon (STOP contradicts ROLL_THROUGH)
                       - opposite sides (rechts contradicts links)
                       - members of one exclusive situation group (Arm hoch contradicts Arme quer)
                       - a FALSE claim contradicts the TRUE claims of the same rule and situation
                       - permission vs prohibition of the same act in the same rule (PARKING_ALLOWED vs
                         PARKING_PROHIBITED)
    incompatible_with  a claim whose action concept excludes the action of another rule's TRUE claim
    exception_to       a claim that only holds under an extra condition of its rule (Einbahnstraße, Zeichen 308)
                       and concept-graph 'exception_of' edges
    narrower_than      compound head / qualifier hierarchy (Wohnanhänger narrower_than Anhänger) and rules that
                       name an extra qualifier of a more general rule on the same subject
    broader_than       inverse of narrower_than
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field

from smart360.theory.kb import KnowledgeBase
from smart360.theory.negation import Deontic, analyze
from smart360.theory.semantics import action_concepts, load_lexicon
from smart360.theory.text import content

RELATIONS = ("contradicts", "incompatible_with", "exception_to", "narrower_than", "broader_than")


@dataclass(frozen=True)
class Relation:
    a: str
    relation: str
    b: str
    origin: str  # lexicon | claims | concept_graph | qualifiers


@dataclass
class ContradictionIndex:
    relations: list[Relation] = field(default_factory=list)
    by_a: dict[str, list[Relation]] = field(default_factory=lambda: defaultdict(list))

    def add(self, a: str, rel: str, b: str, origin: str) -> None:
        r = Relation(a, rel, b, origin)
        self.relations.append(r)
        self.by_a[a].append(r)
        if rel == "contradicts":
            r2 = Relation(b, rel, a, origin)
            self.relations.append(r2)
            self.by_a[b].append(r2)
        elif rel == "narrower_than":
            r2 = Relation(b, "broader_than", a, origin)
            self.relations.append(r2)
            self.by_a[b].append(r2)

    def related(self, a: str, rel: str) -> set[str]:
        return {r.b for r in self.by_a.get(a, ()) if r.relation == rel}

    def contradicts(self, a: str, b: str) -> bool:
        return b in self.related(a, "contradicts")

    def to_json(self) -> str:
        seen = sorted({(r.a, r.relation, r.b, r.origin) for r in self.relations})
        return json.dumps({"relations": [dict(zip(("a", "relation", "b", "origin"), x, strict=True)) for x in seen]},
                          ensure_ascii=False, indent=1) + "\n"


_NOT_ACT = frozenset("nicht kein keine nie niemals darf dürfen muss müssen kann können soll sollte werden wird ist "
                     "sind sein haben hat auch nur immer".split())


def _act_key(statement: str) -> str | None:
    """The act a modal statement is about: German puts the infinitive at the end of the main clause
    ('Ich darf hier nicht parken' -> 'park'). None when there is no such verb."""
    from smart360.theory.reasoning import main_clause
    from smart360.theory.text import stem

    words = re.findall(r"[a-zäöüß]+", main_clause(statement).lower())
    for w in reversed(words):
        if w in _NOT_ACT or len(w) < 4:
            continue
        if w.endswith(("en", "ern", "eln")):
            return stem(w)
        return None
    return None


_CACHE: dict[int, ContradictionIndex] = {}


def _build(kb: KnowledgeBase) -> ContradictionIndex:
    idx = ContradictionIndex()
    lex = load_lexicon()
    for pair in sorted(lex.incompatible, key=sorted):
        a, b = sorted(pair)
        idx.add(a, "contradicts", b, "lexicon")
    for pairs in lex.opposites:
        for x, y in pairs:
            idx.add(f"SIDE:{x}", "contradicts", f"SIDE:{y}", "lexicon")
    for gname, members in lex.exclusive:
        names = [n for n, _ in members]
        for i, x in enumerate(names):
            for y in names[i + 1:]:
                idx.add(f"{gname}:{x}", "contradicts", f"{gname}:{y}", "lexicon")
    for e in kb.edges:
        if e.relation == "exception_of":
            idx.add(e.a, "exception_to", e.b, "concept_graph")
        elif e.relation == "part_of":
            idx.add(e.a, "narrower_than", e.b, "concept_graph")
    from smart360.theory.reasoning import QUALIFIERS

    for q in sorted(QUALIFIERS):
        for h in sorted(QUALIFIERS):
            if q != h and q.endswith(h):
                idx.add(q, "narrower_than", h, "qualifiers")
    # claims of one rule: FALSE vs TRUE in the same situation, allowed vs forbidden act, exceptions
    for obj in kb.objects.values():
        by_ctx: dict[frozenset[str], list[tuple[int, bool, str]]] = defaultdict(list)
        for i, c in enumerate(obj.claims):
            by_ctx[frozenset(content(" ".join(c.context)))].append((i, c.truth, c.statement))
        for group in by_ctx.values():
            trues = [g for g in group if g[1]]
            for fi, ftruth, _fstmt in group:
                if not ftruth:
                    for tj, _ttruth, _tstmt in trues:
                        idx.add(f"{obj.id}#{fi}", "contradicts", f"{obj.id}#{tj}", "claims")
        modal: dict[str, set[str]] = defaultdict(set)
        for c in obj.claims:
            p = analyze(c.statement)
            key = _act_key(c.statement)
            if key is None or p.deontic == Deontic.NONE:
                continue
            allowed = (p.deontic in (Deontic.PERMITTED, Deontic.OBLIGATORY)) != p.negated
            modal[key].add(("ALLOWED" if allowed else "PROHIBITED") + ("" if c.truth else "_FALSE"))
        for key, kinds in modal.items():
            if "ALLOWED" in kinds and "PROHIBITED" in kinds:
                continue  # rule itself distinguishes situations - no blanket contradiction
            if kinds & {"ALLOWED", "PROHIBITED"}:
                idx.add(f"{obj.id}:{key.upper()}_ALLOWED", "contradicts", f"{obj.id}:{key.upper()}_PROHIBITED", "claims")
        base_ctx = set.intersection(*(set(content(" ".join(c.context))) for c in obj.claims)) if obj.claims else set()
        for i, c in enumerate(obj.claims):
            extra = set(content(" ".join(c.context))) - base_ctx
            if (c.truth and extra & QUALIFIERS) or re.search(r"\b(auch|ausnahmsweise|ausgenommen|außer)\b", c.statement):
                idx.add(f"{obj.id}#{i}", "exception_to", obj.id, "claims")
    # action concepts: claims that exclude the TRUE claims of other rules in the same situation words
    true_acts = [(f"{o.id}#{i}", action_concepts(c.statement)) for o in kb.objects.values()
                 for i, c in enumerate(o.claims) if c.truth]
    for cid, acts in true_acts:
        for a in acts:
            for b in idx.related(a, "contradicts"):
                idx.add(cid, "incompatible_with", f"ACTION:{b}", "claims")
    return idx


def build_index(kb: KnowledgeBase) -> ContradictionIndex:
    if id(kb) not in _CACHE:
        _CACHE[id(kb)] = _build(kb)
    return _CACHE[id(kb)]
