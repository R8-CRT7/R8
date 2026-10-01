"""Tutor: mastery is never 'mastered' after one correct answer, spaced repetition, planner, exam, root causes."""

import pytest

from smart360.tutor.errors import RootCause, learner_mistake
from smart360.tutor.exam import ExamItem, ExamRules, class_b_rules, score_exam
from smart360.tutor.learn import UNVERIFIED_NOTE, ExamSession, LearnSession
from smart360.tutor.mastery import DAY, compute
from smart360.tutor.planner import SubtopicInfo, plan
from smart360.tutor.store import Attempt, LearnerStore

T0 = 1_800_000_000.0


def _a(i, correct, ts, variant="base", unsure=False, sub="s"):
    return Attempt(ts, f"it{i}", "t", sub, variant, correct, difficulty=2, unsure=unsure)


def test_one_correct_answer_is_never_mastery():
    st = compute("s", [_a(1, True, T0)], T0 + 60)
    assert st.score <= 50 and not st.mastered


def test_same_variant_repeated_is_capped():
    atts = [_a(i, True, T0 + i * DAY, variant="base") for i in range(10)]
    st = compute("s", atts, T0 + 10 * DAY)
    assert st.score <= 70


def test_varied_correct_answers_over_days_reach_mastery():
    vs = ["base", "paraphrase", "negation", "multiselect", "context"]
    atts = [_a(i, True, T0 + i * 2 * DAY, variant=vs[i % 5]) for i in range(10)]
    st = compute("s", atts, T0 + 19 * DAY)
    assert st.mastered


def test_mistake_lowers_mastery_and_shortens_interval():
    vs = ["base", "paraphrase", "negation", "multiselect"]
    good = [_a(i, True, T0 + i * 2 * DAY, variant=vs[i % 4]) for i in range(8)]
    s1 = compute("s", good, T0 + 15 * DAY)
    s2 = compute("s", [*good, _a(99, False, T0 + 15 * DAY)], T0 + 15 * DAY)
    assert s2.score < s1.score
    assert s2.stability_days < s1.stability_days


def test_unsure_correct_counts_less():
    vs = ["base", "paraphrase", "negation", "multiselect"]
    sure = compute("s", [_a(i, True, T0 + i * DAY, variant=vs[i]) for i in range(4)], T0 + 4 * DAY)
    unsure = compute("s", [_a(i, True, T0 + i * DAY, variant=vs[i], unsure=True) for i in range(4)], T0 + 4 * DAY)
    assert unsure.score < sure.score


def test_retention_decays_and_review_becomes_due():
    vs = ["base", "paraphrase", "negation"]
    atts = [_a(i, True, T0 + i * DAY, variant=vs[i]) for i in range(3)]
    soon = compute("s", atts, T0 + 3 * DAY)
    later = compute("s", atts, T0 + 60 * DAY)
    assert later.retention < soon.retention
    assert soon.due_at is not None and soon.due_at < T0 + 60 * DAY


def test_planner_puts_knowledge_gaps_first():
    infos = [SubtopicInfo("a", "t", 3), SubtopicInfo("b", "t", 1)]
    st = {"b": compute("b", [_a(i, True, T0 + i * DAY, variant=v, sub="b") for i, v in enumerate(
        ["base", "paraphrase", "negation", "context", "multiselect", "base"])], T0 + 6 * DAY)}
    tasks = plan(infos, st, T0 + 6 * DAY)
    assert tasks[0].subtopic == "a" and tasks[0].priority_class == 1


def test_planner_recurring_mistakes_class_2():
    infos = [SubtopicInfo("a", "t", 1)]
    atts = [_a(i, i % 2 == 0, T0 + i * DAY, variant=f"v{i}", sub="a") for i in range(6)]
    st = {"a": compute("a", atts, T0 + 6 * DAY)}
    st["a"].score = 50
    tasks = plan(infos, st, T0 + 6 * DAY)
    assert tasks[0].priority_class in (1, 2)


@pytest.mark.parametrize("question,answers,chosen,expected,cause", [
    ("Was ist hier nicht erlaubt?", ["A", "B", "C"], {1}, {2}, RootCause.NEGATION_ERROR),
    ("Welche Aussagen sind richtig?", ["Ich darf überholen", "Ich muss warten"], {2}, {1, 2}, RootCause.MULTISELECT_ERROR),
    ("Wie lang ist der Anhalteweg?", [], set(), set(), RootCause.CALCULATION_ERROR),
])
def test_learner_root_causes(question, answers, chosen, expected, cause):
    d = learner_mistake(question, answers, chosen, expected, numeric=not answers)
    assert d.cause == cause and d.repair


def test_exam_scoring_rules():
    rules = ExamRules(30, 10, True, None, "test")
    items = [ExamItem(f"q{i}", 5 if i < 2 else 2, {1}) for i in range(30)]
    two_fives = {f"q{i}": ({2} if i < 2 else {1}) for i in range(30)}
    assert not score_exam(items, two_fives, rules).passed  # 10 points but two 5-point errors
    one_five = {f"q{i}": ({2} if i in (0, 5, 6) else {1}) for i in range(30)}
    r = score_exam(items, one_five, rules)
    assert r.error_points == 9 and r.passed
    partial = {f"q{i}": {1, 2} for i in range(30)}
    assert score_exam(items, partial, rules).error_points == 2 * 5 + 28 * 2  # exact multiselect match only


def test_exam_rules_are_flagged_unverified():
    r = class_b_rules()
    assert r.questions == 30 and "NICHT amtlich verifiziert" in r.source


@pytest.fixture()
def session(kb):
    return LearnSession(LearnerStore(), kb, seed=1)


def test_learn_session_full_loop(session):
    item = session.next_item(now=T0)
    assert item is not None
    fb = session.submit(item, set(item.correct), item.number_answer, response_ms=4000, now=T0)
    assert fb.correct and fb.diagnosis is None
    assert fb.mastery_after >= fb.mastery_before and fb.mastery_after <= 50
    assert fb.rule or fb.source
    if not item.question.number_input:
        assert len(fb.options) == len(item.question.answers)
        assert all(o.why for o in fb.options)
    wrong = {i for i in range(1, len(item.question.answers) + 1)} - set(item.correct) or {99}
    fb2 = session.submit(item, wrong, "999", now=T0 + 10)
    assert not fb2.correct and fb2.diagnosis is not None
    assert fb2.similar is None or fb2.similar.id != item.id


def test_unverified_rule_shows_warning(session, kb):
    item = next(i for i in session.items if "HUM_ALCOHOL" in i.sources)
    fb = session.submit(item, set(item.correct), now=T0)
    assert UNVERIFIED_NOTE in fb.warnings


def test_exam_session(session):
    ex = ExamSession.start(session.items, seed=3)
    assert len(ex.items) == 30
    for it in ex.items:
        ex.answer(it.id, set(it.correct), it.number_answer if it.question.number_input else None)
    store = LearnerStore()
    res = ex.finish(store)
    assert res.passed and res.error_points == 0
    assert len(store.attempts()) == 30
