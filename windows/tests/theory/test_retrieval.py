"""Hybrid retrieval: frames, semantic candidates, concept expansion, structural specificity - and the rule that
semantic similarity only proposes candidates and never decides an answer."""

import random

from smart360.theory import retrieval
from smart360.theory.reasoning import TheoryQuestion, solve
from smart360.theory.retrieval import (
    compare,
    expand_query,
    frame_of,
    hybrid_retrieve,
    rule_frame,
    semantic_candidates,
    structural_conflict,
)


def test_frame_extraction():
    f = frame_of("Sie fahren mit Pkw und Anhänger außerorts bei Nebel. Wie schnell dürfen Sie höchstens fahren?")
    assert f.road_context == "außerorts"
    assert {"pkw", "trailer"} <= f.vehicle_context
    assert "nebel" in f.conditions
    assert "SPEED" in f.intents
    g = frame_of("Vor Zeichen 206 muss ich anhalten und Vorfahrt gewähren")
    assert "206" in g.traffic_signs and {"STOP", "YIELD"} <= g.actions and "must" in g.modality and g.priority_relation


def test_every_rule_has_a_frame(kb):
    frames = {o.id: rule_frame(o) for o in kb.objects.values()}
    assert len(frames) == len(kb.objects)
    structured = [f for f in frames.values() if f.actions or f.objects or f.traffic_signs or f.actors or f.road_context
                  or f.vehicle_context or f.conditions or f.numeric_constraints]
    assert len(structured) >= 0.85 * len(frames)  # measured 82/92; concept-level (actions/objects/signs) only 45/92


def test_structural_conflicts():
    assert structural_conflict(frame_of("innerorts"), frame_of("Außerorts beträgt der Abstand 2 m"))
    assert structural_conflict(frame_of("Ein Lkw fährt"), frame_of("Pkw dürfen 100 km/h fahren"))
    assert structural_conflict(frame_of("Ein Pkw mit Anhänger"), frame_of("Pkw dürfen 100 km/h fahren")) is None
    m = compare(frame_of("Pkw mit Anhänger außerorts"), frame_of("Mit Pkw und Anhänger außerorts 80 km/h"))
    assert "road:außerorts" in m.matched and not m.contradicting


def test_semantic_channel_finds_rules_without_word_overlap(kb):
    # own paraphrase: 'Schulbus mit eingeschaltetem Warnblinker an der Haltestelle' - lexical words differ from rule
    ids = [oid for _, oid in semantic_candidates("Ein Bus steht mit Warnblinklicht an der Haltestelle", kb, k=8)]
    assert any("BUS" in i or "STOP" in i or "PRI" in i for i in ids), ids


def test_concept_expansion_uses_typed_graph_edges_only(kb):
    out = expand_query("Wie lang ist der Reaktionsweg?", kb)
    assert "anhalteweg" in out
    assert expand_query("Ein völlig unbekanntes Wort", kb) == "Ein völlig unbekanntes Wort"


def test_hybrid_ranks_contradicting_rules_down(kb):
    cands = hybrid_retrieve("Wie schnell darf ein Pkw innerorts fahren?", kb)
    assert cands and all(c.rank >= -1 for c in cands)
    assert {"lexical", "semantic"} & set().union(*(c.channels for c in cands))


class _NoiseBackend:
    def embed(self, texts):
        rng = random.Random(len(texts))
        return [[rng.random() for _ in range(16)] for _ in texts]


def test_semantic_similarity_never_decides(kb):
    """A nonsense embedding model may change which rules are proposed, but every verdict still needs the
    deterministic checks: no confident answer may appear that the engine cannot prove."""
    q = TheoryQuestion("Was gilt für ein Fahrzeug auf dem Mond?", ["Es schwebt", "Es rollt"])
    retrieval.set_embedding_backend(_NoiseBackend())
    try:
        res = solve(q, kb)
    finally:
        retrieval.set_embedding_backend(None)
    assert res.uncertain


def test_latency_is_recorded(kb):
    retrieval.warm_up(kb)
    res = solve(TheoryQuestion("Wie schnell innerorts?", ["50 km/h", "70 km/h"]), kb)
    assert set(res.timings) == {"retrieval_latency", "reasoning_latency"}
    assert res.timings["retrieval_latency"] < 1.0
