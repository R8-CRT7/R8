"""Contradiction index, prove-false engine, yes/no propositions, role resolution, numeric condition model."""

from smart360.theory.contradiction import build_index
from smart360.theory.numeric_model import comparator, judge_number, unit_fits
from smart360.theory.prove_false import (
    contradicts_rule,
    exception_breaks_absolute,
    prove_false,
    sign_prohibits,
)
from smart360.theory.reasoning import TheoryQuestion, solve
from smart360.theory.semantics import resolve_roles, yes_no_proposition


def test_contradiction_index_is_built_from_rules_and_lexicon(kb):
    idx = build_index(kb)
    assert idx.contradicts("STOP", "ROLL_THROUGH") and idx.contradicts("ROLL_THROUGH", "STOP")
    assert idx.contradicts("SIDE:rechts", "SIDE:links")
    assert "anhang" in idx.related("wohnanhang", "narrower_than")
    assert {r.origin for r in idx.relations} <= {"lexicon", "claims", "concept_graph", "qualifiers"}
    assert any(r.relation == "exception_to" for r in idx.relations)
    assert any(r.a.endswith("_ALLOWED") for r in idx.relations)


def test_sign_prohibits_uses_the_official_text_only(kb):
    assert sign_prohibits("Was gilt bei Zeichen 272?", "Ich darf hier wenden", kb)
    assert sign_prohibits("Was gilt bei Zeichen 272?", "Ich darf hier nicht wenden", kb) is None
    # conditional prohibition (more than 20 l) - never proven false by the sign alone
    assert sign_prohibits("Zeichen 269. Was gilt?", "Ich darf die Straße mit 5 l Ladung benutzen", kb) is None


def test_contradicts_rule_needs_the_same_situation(kb):
    cands = [kb.objects["PRI_RAIL_CROSSING"]]
    q = "Die Schranken eines Bahnübergangs senken sich gerade. Was tun Sie?"
    assert contradicts_rule("Wie ist das Wetter auf dem Mond?", "Ich fahre schnell weiter", cands, kb) is None
    p = prove_false(q, "Ich fahre schnell noch durch", cands, kb)
    assert p is None or p.kind == "contradicts_rule"


def test_exception_proof_only_for_absolute_answers(kb):
    cands = list(kb.objects.values())
    assert exception_breaks_absolute("Was gilt?", "Rechts überholen ist verboten", cands, kb) is None


def test_no_elimination_without_proof(kb):
    """'A is proven right' alone never makes B false."""
    q = TheoryQuestion("Ein Kind steht am Straßenrand. Was ist richtig?",
                       ["Ich fahre langsamer und bin bremsbereit", "Ich denke an mein Abendessen"])
    res = solve(q, kb)
    assert res.evals[1].method not in ("joint", "prove_false") or res.evals[1].flags


def test_yes_no_proposition():
    p = yes_no_proposition("Dürfen Sie hier halten?", "Nein.")
    assert p and p.text == "ich darf nicht hier halten"
    p = yes_no_proposition("Am Zebrastreifen staut sich der Verkehr. Dürfen Sie auf den Zebrastreifen fahren?", "Ja")
    assert p and p.text == "ich darf auf den Zebrastreifen fahren"
    p = yes_no_proposition("Dürfen Sie weiterfahren, wenn der andere nur wenig behindert wird?", "Nein")
    assert p and "wenn" in p.text  # a condition stays part of the proposition
    assert yes_no_proposition("Was tun Sie?", "Nein") is None


def test_role_resolution():
    assert resolve_roles("Ein Kind fährt Fahrrad. Wo muss es fahren?", "Es muss auf dem Gehweg fahren").startswith("Ein Kind")
    assert resolve_roles("Ein Bus hält an der Haltestelle.", "Dort halte ich").startswith("an der Haltestelle")
    assert resolve_roles("Was tun Sie?", "Sie bremsen").startswith("Ich")


def test_numeric_condition_model(kb):
    assert comparator("mehr als 20 l") == "gt" and comparator("höchstens 50 km/h") == "max"
    assert not unit_fits("Wie weit vor der Kreuzung?", "km/h") and unit_fits("Wie schnell?", "km/h")
    ok, fact = judge_number("Wie schnell darf ein Pkw innerorts höchstens fahren?", "50 km/h", kb)
    assert ok is True and fact is not None
    ok, _ = judge_number("Wie schnell darf ein Pkw innerorts höchstens fahren?", "70 km/h", kb)
    assert ok is False
    assert judge_number("Wie schnell?", "70 km/h", kb) == (None, None)  # no condition named -> undecidable


def test_threshold_claims_are_not_compared_by_equality(kb):
    res = solve(TheoryQuestion("Zeichen 269 steht vor Ihnen. Was gilt?",
                               ["Ich darf die Straße mit 5 l Ladung benutzen", "Mit 100 l Heizöl darf ich hier fahren"]), kb)
    assert res.evals[0].verdict.value != "FALSE"
