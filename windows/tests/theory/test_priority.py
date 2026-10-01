"""Right-of-way engine: each scene template rotated 4x must give the hand-written outcome."""

import pytest

from smart360.theory.generator import PRIORITY_TEMPLATES, _rotate
from smart360.theory.priority import Junction, Participant, decide
from smart360.theory.scene import scene_from_dict


@pytest.mark.parametrize("name,tpl,expect", PRIORITY_TEMPLATES, ids=[t[0] for t in PRIORITY_TEMPLATES])
@pytest.mark.parametrize("rot", range(4))
def test_templates(name, tpl, expect, rot):
    d = _rotate(tpl, rot)
    for p in d["participants"]:
        p["labels"] = ["ich"] if p["id"] == "me" else ["x"]
    scene = scene_from_dict(d)
    dec = decide([p.participant for p in scene.participants], scene.junction)
    if expect == "me_waits":
        assert dec.must_wait_for("me", "x"), (name, dec)
    else:
        assert dec.must_wait_for("x", "me"), (name, dec)


def test_four_way_right_before_left_is_a_deadlock():
    ps = [Participant(id=a, kind="car", arm=a, intent="straight") for a in "NESW"]
    dec = decide(ps, Junction(kind="crossing"))
    assert dec.deadlock


def test_bent_priority_among_main_road_is_reported_uncertain():
    ps = [Participant(id="a", kind="car", arm="S", intent="left", sign="priority_road"),
          Participant(id="b", kind="car", arm="W", intent="straight", sign="priority_road")]
    dec = decide(ps, Junction(kind="crossing", main_road_arms=frozenset({"S", "W"})))
    assert dec.uncertain or dec.yields
