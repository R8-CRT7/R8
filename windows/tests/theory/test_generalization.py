"""Generalization milestone: frozen baseline, semantic layer, adversarial paraphrases, honest learn mode.

The adversarial questions below are written for these tests (own wording, not taken from any golden set). Each
must be answered correctly OR be UNCERTAIN - never confidently wrong."""

import hashlib
import json
from pathlib import Path

import pytest

from smart360.theory.reasoning import TheoryQuestion, Verdict, clauses, solve
from smart360.theory.semantics import (
    canonicalize,
    conditions,
    load_lexicon,
    opposite_conflict,
    participle_base,
    resolve_answer,
    separable_verbs,
    situation_conflict,
    split_compound,
)
from smart360.tutor.learn import NOT_PROVABLE, LearnSession
from smart360.tutor.store import LearnerStore

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "reports" / "generalization_baseline.json"
BASELINE_SHA256 = "dab62178c5a30a12e418eaf270d07707525a4372fc696d6c9efe3f7f7b817b48"


# ----------------------------------------------------------------------------- 1. frozen baseline
def test_generalization_baseline_is_frozen():
    data = BASELINE.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(data).hexdigest() == BASELINE_SHA256, "reports/generalization_baseline.json must never change"
    base = json.loads(data)
    for key in ("synthetic_accuracy", "synthetic_uncertain", "synthetic_false_confident", "golden_v1_first_run",
                "golden_v2_first_run", "commit", "date"):
        assert key in base


# ----------------------------------------------------------------------------- 6. semantic normalisation layer
def test_every_lexicon_entry_is_documented():
    lex = load_lexicon()
    raw = json.loads((ROOT / "knowledge" / "semantics" / "lexicon.json").read_text(encoding="utf-8"))
    for e in raw["entries"]:
        assert {"id", "canonical_concept", "rewrite", "confidence", "valid_context", "invalid_context", "patterns"} <= set(e)
        assert 0.5 <= e["confidence"] <= 1.0 and e["patterns"]
    concepts = {e.concept for e in lex.entries}
    for pair in lex.incompatible:
        assert pair <= concepts, f"incompatible pair names an unknown concept: {pair}"


def test_canonicalization_never_swallows_a_negation():
    assert "nicht cyieldx" in canonicalize("Ich lasse nicht den Gegenverkehr zuerst vorbei").text
    assert canonicalize("Ich lasse den Gegenverkehr zuerst vorbei").text.endswith("cyieldx")
    assert "nicht über die linie" in canonicalize("Er darf nicht über die Linie fahren").text
    assert canonicalize("nicht schneller als 30 km/h").text == "höchstens 30 km/h"


def test_context_restricted_entry():
    # 'Landstraße' means außerorts - but not inside a sentence that says innerorts
    assert "außerorts" in canonicalize("Sie fahren auf einer Landstraße").text.replace("ausserorts", "außerorts")


# ----------------------------------------------------------------------------- 8. conditions / word formation
def test_condition_extraction():
    c = conditions("Ein Kind ist sieben Jahre alt und fährt Fahrrad außerorts bei Nebel")
    assert c.road_context == "außerorts"
    assert "nebel" in c.weather


def test_compounds_participles_separable_verbs():
    assert split_compound("grundstucksausfahr") == ("grundstuck", "ausfahr")
    assert participle_base("abgeschlepp") == ("abschlepp",)
    assert "abschleppen" in separable_verbs("Sie schleppen ein Fahrzeug ab.")
    assert separable_verbs("Ich halte, wenn es rot ist") == set()


def test_situations_and_opposites():
    assert situation_conflict("Zeichen 286", "Zeichen 283 absolutes Haltverbot") == "SIGN"
    assert situation_conflict("streckt die Arme seitlich aus", "Arm hochheben") == "POLICE_GESTURE"
    # an answer naming its own situation overrides the question's
    assert situation_conflict("Ampel zeigt Grün", "Gelb bedeutet warten", "Gelb bedeutet warten") is None
    assert opposite_conflict("rechts", "auf der linken Seite")
    assert not opposite_conflict("rechts vor links", "links")


# ----------------------------------------------------------------------------- 11/12/14. roles, polarity, joint reading
def test_answer_roles_and_clauses():
    assert resolve_answer("Wer muss warten?", "Ich").lower() == "ich muss warten"
    assert clauses("Ich warte an der Haltlinie und lasse den Radfahrer vorbei") == [
        "Ich warte an der Haltlinie", "ich lasse den Radfahrer vorbei"]
    assert clauses("Ich halte an, wenn die Ampel rot ist") == ["Ich halte an, wenn die Ampel rot ist"]


# ----------------------------------------------------------------------------- 17/18. adversarial generalization
ADVERSARIAL = [
    # (label, question, answers, correct)
    ("wording", "Ein Martinshorn ist zu hören und hinter Ihnen blinkt es blau. Was ist Ihre Pflicht?",
     ["Dem Einsatzfahrzeug sofort Platz machen", "Unverändert weiterfahren"], (1,)),
    ("irrelevant_info", "Das Radio läuft. Sie sind müde vom Tag. Ein Stoppschild steht an der Einmündung. Was gilt?",
     ["Ich muss anhalten, auch wenn frei ist", "Ich darf ohne anzuhalten weiterrollen"], (1,)),
    ("competing_rule", "Eine Ampel zeigt Grün, ein Polizist gibt Ihnen ein Haltzeichen. Was tun Sie?",
     ["Ich halte an", "Ich fahre weiter, weil Grün ist"], (1,)),
    ("other_actor", "Sie werden von einem Pkw überholt. Was dürfen Sie nicht?",
     ["Meine Geschwindigkeit erhöhen", "Weiter rechts fahren"], (1,)),
    ("road_context", "Sie ziehen einen Anhänger mit Ihrem Pkw auf der Autobahn. Wie schnell dürfen Sie höchstens fahren?",
     ["80 km/h", "100 km/h", "130 km/h"], (1,)),
    ("exception", "Ein Fahrzeug hat sich links eingeordnet und blinkt links. Auf welcher Seite überholen Sie?",
     ["Rechts", "Links"], (1,)),
    ("negated_question", "Welche Aussage zum Halten am Bahnübergang ist falsch?",
     ["Auf Bahnübergängen ist das Halten erlaubt", "Halten ist auf Bahnübergängen unzulässig"], (1,)),
]


@pytest.mark.parametrize(("label", "question", "answers", "correct"), ADVERSARIAL, ids=[a[0] for a in ADVERSARIAL])
def test_adversarial_never_confidently_wrong(kb, label, question, answers, correct):
    res = solve(TheoryQuestion(question, answers), kb)
    if not res.uncertain:
        assert tuple(sorted(res.selected)) == correct, f"{label}: confidently wrong {res.selected}"


def test_adversarial_suite_answers_some(kb):
    answered = sum(not solve(TheoryQuestion(q, a), kb).uncertain for _, q, a, _ in ADVERSARIAL)
    assert answered >= 3, "the engine should answer at least some re-worded questions"


# ----------------------------------------------------------------------------- 23. learn mode is honest
def test_learn_mode_never_explains_an_unprovable_option(kb):
    session = LearnSession(LearnerStore(), kb, seed=5)
    item = session.items[0]
    q = TheoryQuestion("Was gilt für ein Phantasiefahrzeug auf dem Mond?", ["Es schwebt", "Es rollt"])
    unprovable = item.__class__(item.id + ":x", item.topic, item.subtopic, item.variant, q, (1,), sources=[])
    fb = session.submit(unprovable, {1}, now=1_800_000_000.0)
    assert all(NOT_PROVABLE in o.why for o in fb.options)


def test_learn_mode_explanations_agree_with_the_key(kb):
    session = LearnSession(LearnerStore(), kb, seed=7)
    for item in session.items[:60]:
        if item.question.number_input:
            continue
        res = solve(item.question, kb)
        negative = "negative_question" in res.kinds
        fb = session.submit(item, set(item.correct), now=1_800_000_000.0)
        for i, (opt, ev) in enumerate(zip(fb.options, res.evals, strict=True), start=1):
            ok = i in item.correct
            expected = (Verdict.FALSE if negative else Verdict.TRUE) if ok else (Verdict.TRUE if negative else Verdict.FALSE)
            if ev.verdict != expected:
                assert NOT_PROVABLE in opt.why
