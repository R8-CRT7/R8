"""Adaptive difficulty levels, mastery that requires generalisation, and the learn-mode step order."""

import pytest

from smart360.tutor.learn import LearnSession
from smart360.tutor.levels import LEVEL_OF_VARIANT, level_of, target_level
from smart360.tutor.mastery import DAY, compute
from smart360.tutor.store import Attempt, LearnerStore

T0 = 1_800_000_000.0


def _a(item, variant, correct, ts):
    return Attempt(ts, item, "t", "s", variant, correct, difficulty=2)


def test_levels_cover_the_generator_variants(kb):
    from smart360.theory.generator import all_items

    variants = {i.variant for i in all_items(kb)}
    assert variants <= set(LEVEL_OF_VARIANT)
    assert {level_of(i) for i in all_items(kb)} == {1, 2, 3, 4, 5, 6}


def test_target_level_progression():
    assert target_level([]) == 1
    h = [_a("i1", "base", True, T0)]
    assert target_level(h) == 2
    h.append(_a("i2", "paraphrase", True, T0 + 60))
    assert target_level(h) == 3
    h.append(_a("i3", "multiselect", False, T0 + 120))
    assert target_level(h) == 3  # stay on the level that was failed
    h.append(_a("i4", "negation", False, T0 + 180))
    assert target_level(h) == 2  # two mistakes in a row -> one level down


def test_same_wording_gives_little_progress():
    same = [_a("i1", "base", True, T0 + k * 60) for k in range(6)]
    varied = [_a(f"i{k}", v, True, T0 + k * 2 * DAY) for k, v in
              enumerate(["base", "paraphrase", "multiselect", "exception", "calc_factor", "priority"])]
    s_same = compute("s", same, T0 + 400)
    s_var = compute("s", varied, T0 + 10 * DAY + 60)
    assert s_same.score < 50
    assert s_var.score > s_same.score + 20


def test_mastered_needs_levels_and_delayed_retest():
    quick = [_a(f"i{k}", v, True, T0 + k * 60) for k, v in enumerate(["base", "paraphrase", "multiselect", "exception"])]
    assert compute("s", quick, T0 + 300).score <= 79  # no delayed retest yet
    later = [*quick, _a("i9", "context", True, T0 + 3 * DAY)]
    assert compute("s", later, T0 + 3 * DAY + 60).score >= compute("s", quick, T0 + 300).score


@pytest.fixture()
def session(kb):
    return LearnSession(LearnerStore(), kb, seed=3)


def test_mistake_feedback_starts_with_the_concept(session):
    item = next(i for i in session.items if i.variant == "base" and len(i.question.answers) > 1 and i.sources
                and i.sources[0] in session.kb.objects)
    wrong = {i for i in range(1, len(item.question.answers) + 1)} - set(item.correct)
    fb = session.submit(item, wrong, now=T0)
    assert not fb.correct
    keys = [k for k, _ in fb.steps]
    assert keys[0] == "Konzept" and keys[1] == "Regel"
    assert keys.index("Regel") < keys.index("Neue Variante") if "Neue Variante" in keys else True
    assert fb.similar is None or (fb.similar.id != item.id and fb.similar.subtopic == item.subtopic)
    assert fb.review_at is not None and fb.review_at <= T0 + 3600
    assert fb.level == level_of(item)


def test_success_moves_to_the_next_level(session):
    item = next(i for i in session.items if i.variant == "base" and i.sources and i.sources[0] in session.kb.objects)
    fb = session.submit(item, set(item.correct), item.number_answer, now=T0)
    assert fb.correct and fb.next_level == 2
    assert fb.similar is None or fb.similar.id != item.id


def test_unverified_rules_are_learning_material_only(session):
    item = next(i for i in session.items if "HUM_ALCOHOL" in i.sources)
    fb = session.submit(item, set(item.correct), now=T0)
    assert fb.learning_only and fb.warnings
