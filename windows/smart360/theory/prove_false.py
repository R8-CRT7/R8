"""Prove-false engine: explicit counter-proofs for answer options no claim matches directly.

An option becomes FALSE only with a proof from VERIFIED knowledge, in the question's situation:
    contradicts_rule      its action contradicts (contradiction index) the action a verified TRUE claim of a
                          candidate rule requires in this situation, and no candidate rule allows that action
    sign_prohibits        the question names one traffic sign that prohibits the act the option affirms
                          (and the sign meaning names no exception)
    exception_breaks_absolute
                          the option claims something holds 'immer'/'nie' but a verified exception of the same
                          rule says otherwise
    numeric_limit         handled by the numeric condition model (reasoning / numeric facts)

NOT a proof: 'answer A is right, so B must be wrong' - only the joint step may use that, and only where the
question itself guarantees exclusivity ('Wer hat Vorrang?', incompatible actions in the same situation).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from smart360.theory.contradiction import _act_key, build_index
from smart360.theory.kb import KnowledgeBase
from smart360.theory.negation import Deontic, analyze
from smart360.theory.schema import KnowledgeObject
from smart360.theory.semantics import action_concepts, actor, situation_conflict, situations
from smart360.theory.text import similarity

PROVE_CTX_MIN = 0.3  # the claim's situation must match the question at least this well
_ABSOLUTE = re.compile(r"\b(immer|nie|niemals|ausnahmslos|stets|in jedem fall|auf keinen fall)\b", re.IGNORECASE)
_EXCEPTION_WORDS = re.compile(r"\b(ausgenommen|außer|ausser|nur|frei|gilt nicht|nicht für)\b", re.IGNORECASE)


@dataclass
class Proof:
    kind: str
    evidence: str  # rule id
    explanation: str


def _affirms(text: str) -> bool:
    from smart360.theory.reasoning import main_clause

    p = analyze(main_clause(text))
    return not p.negated and p.deontic in (Deontic.NONE, Deontic.OBLIGATORY, Deontic.PERMITTED)


def _ctx_sim(question: str, claim_ctx: list[str], statement: str) -> float:
    from smart360.theory.reasoning import _core

    q = _core(question)
    return max(similarity(q, _core(" ".join(claim_ctx))), similarity(q, _core(statement))) if claim_ctx else 0.0


def contradicts_rule(question: str, answer: str, candidates: list[KnowledgeObject], kb: KnowledgeBase) -> Proof | None:
    from smart360.theory.reasoning import main_clause

    a_acts = action_concepts(main_clause(answer))
    if not a_acts or not _affirms(answer):
        return None
    idx = build_index(kb)
    a_actor = actor(main_clause(answer))
    proof: Proof | None = None
    for obj in candidates:
        if kb.status.get(obj.id) != "verified":
            continue
        for i, c in enumerate(obj.claims):
            c_acts = action_concepts(main_clause(c.statement))
            if not c_acts:
                continue
            situation = " ".join(c.context) + " " + c.statement
            if situation_conflict(question, situation, answer) or _ctx_sim(question, c.context, c.statement) < PROVE_CTX_MIN:
                continue
            c_actor = actor(main_clause(c.statement))
            if a_actor and c_actor and a_actor != c_actor:
                continue
            if c.truth and a_acts & c_acts and _affirms(c.statement):
                return None  # a rule in this situation requires / allows exactly this action - no proof
            if (c.truth and _affirms(c.statement) and not a_acts & c_acts
                    and f"{obj.id}#{i}" not in {r.a for r in idx.relations if r.relation == "exception_to"}
                    and any(idx.contradicts(x, y) for x in a_acts for y in c_acts)):
                proof = proof or Proof("contradicts_rule", obj.id,
                                       f"widerspricht der Regel: {c.statement} ({obj.title})")
    return proof


def sign_prohibits(question: str, answer: str, kb: KnowledgeBase) -> Proof | None:
    signs = situations(question).get("SIGN", frozenset())
    if len(signs) != 1:
        return None
    sg = kb.signs.get(next(iter(signs)))
    if sg is None or sg.category != "Vorschriftzeichen" or kb.status.get(sg.id) != "verified":
        return None
    texts = [x.evidence for x in sg.sources if x.evidence]  # only the official text decides
    if any(_EXCEPTION_WORDS.search(t) for t in texts):
        return None  # the sign has exceptions - an option may be one of them
    if any(re.search(r"\d", t.replace(sg.number, "")) for t in texts):
        return None  # conditional prohibition ('mehr als 20 l') - the numeric condition model decides, not the sign
    prohibited = set()
    for t in texts:
        p = analyze(t)
        if (p.deontic == Deontic.FORBIDDEN or (p.negated and p.deontic == Deontic.PERMITTED)) and _act_key(t):
            prohibited.add(_act_key(t))
    pa = analyze(answer)
    allows = not pa.negated and pa.deontic in (Deontic.PERMITTED, Deontic.NONE)
    key = _act_key(answer)
    if allows and key and key in prohibited:
        return Proof("sign_prohibits", sg.id, f"Zeichen {sg.number} ({sg.name}) verbietet das: {sg.meaning}")
    return None


def exception_breaks_absolute(question: str, answer: str, candidates: list[KnowledgeObject],
                              kb: KnowledgeBase) -> Proof | None:
    if not _ABSOLUTE.search(answer):
        return None
    from smart360.theory.reasoning import _core

    a_core = _core(answer)
    a_key = _act_key(answer)
    a_forbid = analyze(answer)
    a_allowed = (a_forbid.deontic in (Deontic.PERMITTED, Deontic.OBLIGATORY)) != a_forbid.negated
    idx = build_index(kb)
    exceptions = {r.a for r in idx.relations if r.relation == "exception_to"}
    for obj in candidates:
        if kb.status.get(obj.id) != "verified":
            continue
        for i, c in enumerate(obj.claims):
            if f"{obj.id}#{i}" not in exceptions or not c.truth or _act_key(c.statement) != a_key or a_key is None:
                continue
            if similarity(a_core, _core(c.statement)) < 0.3:
                continue
            pc = analyze(c.statement)
            c_allowed = (pc.deontic in (Deontic.PERMITTED, Deontic.OBLIGATORY)) != pc.negated
            if Deontic.NONE not in (pc.deontic, a_forbid.deontic) and c_allowed != a_allowed:
                return Proof("exception_breaks_absolute", obj.id, f"Ausnahme: {c.statement} ({obj.title})")
    return None


def prove_false(question: str, answer: str, candidates: list[KnowledgeObject], kb: KnowledgeBase) -> Proof | None:
    return (sign_prohibits(question, answer, kb) or contradicts_rule(question, answer, candidates, kb)
            or exception_breaks_absolute(question, answer, candidates, kb))
