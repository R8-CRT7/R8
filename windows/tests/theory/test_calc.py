import pytest

from smart360.theory import calc


@pytest.mark.parametrize("fid,v,expected", [
    ("reaction_distance", 50, 15), ("braking_distance", 50, 25), ("stopping_distance", 50, 40),
    ("emergency_braking_distance", 100, 50), ("emergency_stopping_distance", 100, 80),
    ("reaction_distance", 70, 21), ("stopping_distance", 80, 88), ("safe_distance_half_speedometer", 100, 50),
])
def test_formulas(fid, v, expected):
    r = calc.compute(fid, v_kmh=v)
    assert r.matches(expected) and r.unit == "m"
    assert r.steps, "every calculation documents its steps"


def test_factor():
    assert calc.compute("braking_distance_factor", k=2).value == 4
    assert calc.compute("braking_distance_factor", k=3).value == 9


def test_rules_of_thumb_are_labelled_as_such():
    assert calc.FORMULAS["stopping_distance"].source_type == "rule_of_thumb"


def test_licence_decision_uses_unverified_fev_values(kb):
    d = calc.licence_for_combination(1500, 700)
    assert d.licence == "B"
    assert kb.status["FEV6_B_MAX_ZGM"] == "unverified"
