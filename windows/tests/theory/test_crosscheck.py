"""The theory cross-check can only make the assistant more conservative."""

from smart360.theory.crosscheck import crosscheck

QTEXT = "Wie hoch ist die zulässige Höchstgeschwindigkeit für Pkw innerhalb geschlossener Ortschaften?"


def test_agree():
    assert crosscheck(QTEXT, ["50 km/h", "60 km/h"], False, 1.0, False, (1,), None).verdict == "agree"


def test_disagree_blocks():
    cc = crosscheck(QTEXT, ["50 km/h", "60 km/h"], False, 1.0, False, (2,), None)
    assert cc.verdict == "disagree" and cc.should_block


def test_unknown_question_does_not_block():
    cc = crosscheck("Was ist ein Flux-Kompensator?", ["A", "B"], False, 1.0, False, (1,), None)
    assert cc.verdict == "theory_uncertain" and not cc.should_block


def test_number_question():
    q = "Wie lang ist der Anhalteweg bei 50 km/h nach der Faustformel?"
    assert crosscheck(q, [], True, 1.0, False, (), "40").verdict == "agree"
    assert crosscheck(q, [], True, 1.0, False, (), "25").should_block


def test_engine_hook_only_adds_uncertainty():
    from dataclasses import replace

    from smart360.core.models import Prediction, PredictionSource
    from smart360.engine.engine import Engine, EngineSettings

    class FakeQ:
        question_id = "q"
        text = QTEXT
        answers = [type("A", (), {"text": "50 km/h"})(), type("A", (), {"text": "60 km/h"})()]
        question_type = None
        ocr_confidence = 1.0
        has_image = False

    eng = Engine.__new__(Engine)
    eng.settings = EngineSettings(theory_crosscheck=True)
    eng.tracer = None
    p = Prediction("q", (2,), 0.95, 0.95, "ai", False, PredictionSource.AI)
    out = eng._theory_crosscheck(FakeQ(), p)
    assert out.uncertain and "Regel-Engine widerspricht" in out.reason
    ok = eng._theory_crosscheck(FakeQ(), replace(p, answers=(1,)))
    assert not ok.uncertain and ok.confidence == p.confidence


def test_unverified_knowledge_never_makes_the_crosscheck_block(monkeypatch):
    """Even a (hypothetical) confident theory result is ignored when it rests on an unverified rule."""
    from smart360.theory import crosscheck as cc
    from smart360.theory.kb import get_kb
    from smart360.theory.reasoning import AnswerEval, TheoryResult, Verdict

    unverified = next(i for i, s in get_kb().status.items() if s == "unverified")
    fake = TheoryResult((2,), None, [AnswerEval(1, Verdict.FALSE, "claim", [unverified]),
                                     AnswerEval(2, Verdict.TRUE, "claim", [unverified])],
                        0.95, False, [], set(), {}, [])
    monkeypatch.setattr(cc, "solve", lambda *a, **k: fake)
    res = cc.crosscheck("Frage?", ["A", "B"], False, 1.0, False, (1,), None)
    assert res.verdict == "theory_uncertain" and not res.should_block
