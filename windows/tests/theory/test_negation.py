"""Negation engine regression tests: NICHT, KEIN, DÜRFEN, MÜSSEN, KÖNNEN, IMMER, NUR, VERBOTEN, ERLAUBT, AUSNAHME."""

import pytest

from smart360.theory.negation import Deontic, analyze, asks_for_negative, deontic_truth
from smart360.theory.reasoning import condition_part, main_clause
from smart360.theory.text import ocr_repair


@pytest.mark.parametrize("text,deontic,negated", [
    ("Ich darf überholen", Deontic.PERMITTED, False),
    ("Ich darf nicht überholen", Deontic.FORBIDDEN, False),
    ("Überholen ist verboten", Deontic.FORBIDDEN, False),
    ("Überholen ist nicht verboten", Deontic.PERMITTED, False),
    ("Überholen ist erlaubt", Deontic.PERMITTED, False),
    ("Ich muss warten", Deontic.OBLIGATORY, False),
    ("Ich muss nicht warten", Deontic.NOT_OBLIGATORY, False),
    ("Ich brauche nicht zu warten", Deontic.NOT_OBLIGATORY, False),
    ("Ich kann bremsen", Deontic.POSSIBLE, False),
    ("Es kommt kein Gegenverkehr", Deontic.NONE, True),
    ("Fußgänger gehen nicht", Deontic.NONE, True),
])
def test_deontic_and_negation(text, deontic, negated):
    p = analyze(text)
    assert p.deontic == deontic
    assert p.negated == negated


def test_absolutes_and_exceptions_are_detected():
    assert analyze("Das gilt immer").absolutes
    assert analyze("Nur Radfahrer dürfen hier fahren").absolutes
    assert analyze("Ausnahme: Linienbusse").exceptions


@pytest.mark.parametrize("q,neg", [
    ("Was ist hier nicht erlaubt?", True), ("Welche Aussage ist falsch?", True), ("Was ist verboten?", True),
    ("Welches Verhalten ist richtig?", False), ("Was müssen Sie tun?", False),
])
def test_question_asks_for_negative(q, neg):
    assert asks_for_negative(q) == neg


def test_deontic_truth_table():
    assert deontic_truth(Deontic.FORBIDDEN, Deontic.FORBIDDEN, True) is True
    assert deontic_truth(Deontic.FORBIDDEN, Deontic.PERMITTED, True) is False
    assert deontic_truth(Deontic.OBLIGATORY, Deontic.NOT_OBLIGATORY, True) is False


def test_main_clause_and_condition():
    assert main_clause("Ich darf noch schnell durchfahren, solange die Schranke nicht ganz geschlossen ist") == \
        "Ich darf noch schnell durchfahren"
    assert main_clause("Kann ich den Bahnübergang nicht zügig räumen, muss ich vor dem Andreaskreuz warten") == \
        "muss ich vor dem Andreaskreuz warten"
    assert main_clause("Kinder bis 12 Jahre, die kleiner als 150 cm sind, brauchen eine Rückhalteeinrichtung") == \
        "Kinder bis 12 Jahre brauchen eine Rückhalteeinrichtung"
    assert "nicht" in condition_part("Kann ich den Bahnübergang nicht zügig räumen, muss ich warten")


def test_ocr_repair_only_touches_polarity_and_conjunction_words():
    t, n = ocr_repair("Ich darf langsam durchrolIcn, wenn kcin Querverkehr kommt, soIange ich rnuss")
    assert "kein" in t and "solange" in t and "muss" in t and "durchrolIcn" in t
    assert n == 3
    same, n0 = ocr_repair("sein mein dein klein nein")
    assert n0 == 0 and same == "sein mein dein klein nein"
