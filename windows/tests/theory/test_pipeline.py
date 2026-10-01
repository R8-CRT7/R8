"""End-to-end reasoning pipeline, including the false-confident regressions found during development."""

import pytest

from smart360.theory.reasoning import DEFAULT_THRESHOLD, TheoryQuestion, Verdict, solve
from smart360.theory.scene import scene_from_dict, temporal_check

CASES = [
    ("Wie hoch ist die zulässige Höchstgeschwindigkeit für Pkw außerhalb geschlossener Ortschaften?",
     ["100 km/h", "80 km/h", "120 km/h"], (1,)),
    ("Wie hoch ist die zulässige Höchstgeschwindigkeit für Pkw mit Anhänger außerhalb geschlossener Ortschaften?",
     ["100 km/h", "80 km/h", "60 km/h"], (2,)),
    ("Ab welcher Sichtweite durch Nebel dürfen Sie höchstens 50 km/h fahren?", ["unter 50 m", "unter 100 m"], (1,)),
    ("Wie verhalten Sie sich an einem Kreisverkehr mit Zeichen 215 und Zeichen 205?",
     ["Ich darf beim Einfahren nicht blinken", "Der Verkehr auf der Kreisfahrbahn hat Vorfahrt",
      "Ich habe beim Einfahren Vorfahrt"], (1, 2)),
    ("Was ist hier nicht erlaubt? Sie fahren in einem verkehrsberuhigten Bereich.",
     ["Mit 30 km/h fahren", "Mit Schrittgeschwindigkeit fahren"], (1,)),
    ("Wann muss ein neuer Pkw erstmals zur Hauptuntersuchung?", ["nach 36 Monaten", "nach 24 Monaten"], (1,)),
]


@pytest.mark.parametrize("q,answers,expected", CASES)
def test_known_questions(kb, q, answers, expected):
    r = solve(TheoryQuestion(q, answers), kb)
    assert not r.uncertain, r.reasons
    assert r.selected == expected


@pytest.mark.parametrize("q,answers,wrong", [
    # 'ohne Anhänger' must not pick the trailer limit
    ("Mit welcher Höchstgeschwindigkeit darf ein Pkw ohne Anhänger außerorts fahren?", ["80 km/h", "100 km/h"], (1,)),
    # negation inside a condition must not flip the main statement
    ("Die Schranken senken sich. Was tun Sie?", ["Vor dem Andreaskreuz warten", "Schnell noch durchfahren"], (1, 2)),
    # yes/no questions: 'Ja, wenn ...' only means something with the question
    ("Dürfen Sie auf dem Seitenstreifen der Autobahn halten, um zu telefonieren?",
     ["Nein, Halten ist auch auf dem Seitenstreifen verboten", "Ja, wenn ich das Warnblinklicht einschalte"], (1, 2)),
])
def test_former_false_confident_cases_never_return(kb, q, answers, wrong):
    r = solve(TheoryQuestion(q, answers), kb)
    assert r.uncertain or r.selected != wrong


def test_feldweg_specific_rule_beats_general_rule(kb):
    r = solve(TheoryQuestion("Rechts vor links. Welche Aussagen sind richtig?",
                             ["Wer aus einem Feldweg von rechts kommt, hat Vorfahrt", "Wer von rechts kommt, hat Vorfahrt"]), kb)
    e1 = r.evals[0]
    assert e1.verdict in (Verdict.FALSE, Verdict.UNKNOWN)


def test_unverified_rules_never_give_a_confident_answer(kb):
    r = solve(TheoryQuestion("Zugfahrzeug 1500 kg, Anhänger 1000 kg. Welche Fahrerlaubnisklasse benötigen Sie?",
                             ["Klasse B", "Klasse BE"]), kb)
    assert r.uncertain
    assert any("not verified" in x for x in r.reasons)


def test_number_answer_is_deterministic(kb):
    r = solve(TheoryQuestion("Wie lang ist der Anhalteweg bei 50 km/h nach der Faustformel?", [], number_input=True), kb)
    assert r.number_answer == "40" and not r.uncertain


def test_uncertain_results_are_capped_below_threshold(kb):
    r = solve(TheoryQuestion("Was ist ein Flux-Kompensator?", ["A", "B"]), kb)
    assert r.uncertain and r.confidence < DEFAULT_THRESHOLD


def test_language_model_disagreement_makes_it_uncertain(kb):
    q = TheoryQuestion("Wie hoch ist die zulässige Höchstgeschwindigkeit für Pkw innerhalb geschlossener Ortschaften?",
                       ["50 km/h", "60 km/h"])
    assert not solve(q, kb).uncertain
    assert solve(q, kb, llm_selected=(2,)).uncertain


def test_trace_contains_all_pipeline_stages(kb):
    r = solve(TheoryQuestion("Was gilt am Zebrastreifen?", ["An Fußgängerüberwegen darf nicht überholt werden"]), kb)
    stages = [s for s, _ in r.trace]
    for s in ("normalization", "classification", "retrieval", "semantic_check_A", "semantic_check_B",
              "semantic_check_C", "exception_check", "negation_check", "second_pass", "confidence"):
        assert s in stages


def test_picture_question_without_scene_is_uncertain(kb):
    r = solve(TheoryQuestion("Wie verhalten Sie sich an dieser Kreuzung?", ["Ich warte", "Ich fahre"], has_image=True), kb)
    assert r.uncertain


def test_dynamic_question_with_single_frame_is_incomplete():
    d = {"junction": {"kind": "crossing"}, "participants": [{"id": "me", "kind": "me", "arm": "S", "labels": ["ich"]}]}
    tc = temporal_check("Wie verändert sich die Situation, wenn das Fahrzeug weiterfährt?", [scene_from_dict(d)], is_video=True)
    assert not tc.complete


def test_priority_scene_question(kb):
    d = {"junction": {"kind": "crossing", "main_road_arms": []}, "confidence": 0.95,
         "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "straight", "labels": ["ich"]},
                          {"id": "x", "kind": "car", "arm": "E", "intent": "straight", "labels": ["blauen Pkw"]}]}
    r = solve(TheoryQuestion("Wie verhalten Sie sich?", ["Ich muss den blauen Pkw durchfahren lassen",
                                                          "Der blaue Pkw muss mich durchfahren lassen"],
                             has_image=True, scene=scene_from_dict(d)), kb)
    assert r.selected == (1,) and not r.uncertain
