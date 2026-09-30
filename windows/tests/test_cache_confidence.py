import sqlite3

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from smart360.core.confidence import ConfidenceInputs, composite_confidence
from smart360.core.models import AnswerOption, Question, QuestionType
from smart360.storage.cache import QuestionCache


def q(text, answers, image_hash=None, qtype=QuestionType.SINGLE_OR_MULTI):
    return Question(
        text=text,
        answers=tuple(AnswerOption(i + 1, a) for i, a in enumerate(answers)),
        question_type=qtype,
        image_hash=image_hash,
        has_image=image_hash is not None,
    )


BASE = q(
    "Wie verhalten Sie sich an dieser Kreuzung?",
    ["Ich lasse den Radfahrer durchfahren", "Ich fahre vor dem Radfahrer", "Ich warte auf den Gegenverkehr"],
)


@pytest.fixture
def cache(tmp_path):
    c = QuestionCache(tmp_path / "cache.db")
    yield c
    c.close()


def test_exact_hit(cache):
    cache.store(BASE, (1, 3), 0.95, "Rechts vor links", "m")
    hit = cache.lookup(BASE)
    assert hit is not None and hit.answers == (1, 3)


def test_ocr_noise_still_hits(cache):
    cache.store(BASE, (1,), 0.9, "r", "m")
    noisy = q(
        "Wie verhalten Sie sich an dieser Kreuzung ?",
        [
            "Ich lasse den Radfahrer durchfahren",
            "Ich fahre vor dem Radfahrer",
            "Ich warte auf den Gegenverkehr.",
        ],
    )
    hit = cache.lookup(noisy)
    assert hit is not None and hit.answers == (1,)


def test_shuffled_answers_remapped(cache):
    cache.store(BASE, (1, 3), 0.9, "r", "m")
    shuffled = q(BASE.text, [BASE.answers[2].text, BASE.answers[0].text, BASE.answers[1].text])
    hit = cache.lookup(shuffled)
    assert hit is not None
    assert hit.answers == (1, 2)  # "warte" is now #1, "lasse" is now #2


def test_different_number_never_hits(cache):
    a = q("Wie schnell dürfen Sie hier höchstens fahren? 50 km/h", ["50 km/h", "70 km/h", "100 km/h"])
    b = q("Wie schnell dürfen Sie hier höchstens fahren? 70 km/h", ["50 km/h", "70 km/h", "100 km/h"])
    cache.store(a, (1,), 0.9, "r", "m")
    assert cache.lookup(b) is None


def test_different_answer_numbers_never_hit(cache):
    a = q("Welcher Mindestabstand ist einzuhalten?", ["1,5 m", "2 m", "1 m"])
    b = q("Welcher Mindestabstand ist einzuhalten?", ["1,5 m", "2,5 m", "1 m"])
    cache.store(a, (1,), 0.9, "r", "m")
    assert cache.lookup(b) is None


def test_same_text_different_image_never_hits(cache):
    a = q("Wie verhalten Sie sich?", ["Bremsen", "Weiterfahren"], image_hash=0xFFFF0000FFFF0000)
    b = q("Wie verhalten Sie sich?", ["Bremsen", "Weiterfahren"], image_hash=0x0000FFFF0000FFFF)
    cache.store(a, (1,), 0.9, "r", "m")
    assert cache.lookup(b) is None
    # tiny rendering noise is fine
    c = q("Wie verhalten Sie sich?", ["Bremsen", "Weiterfahren"], image_hash=0xFFFF0000FFFF0001)
    assert cache.lookup(c) is not None


def test_image_vs_no_image_never_hits(cache):
    a = q("Wie verhalten Sie sich?", ["Bremsen", "Weiterfahren"], image_hash=0xF0F0)
    b = q("Wie verhalten Sie sich?", ["Bremsen", "Weiterfahren"])
    cache.store(a, (1,), 0.9, "r", "m")
    assert cache.lookup(b) is None


def test_different_question_type_never_hits(cache):
    a = q("Wie viel Meter?", ["x", "y"])
    b = q("Wie viel Meter?", ["x", "y"], qtype=QuestionType.NUMBER_INPUT)
    cache.store(a, (1,), 0.9, "r", "m")
    assert cache.lookup(b) is None


def test_negation_changes_are_not_hits(cache):
    a = q("Wann dürfen Sie überholen?", ["Wenn die Sicht frei ist", "Im Tunnel"])
    b = q("Wann dürfen Sie nicht überholen?", ["Wenn die Sicht frei ist", "Im Tunnel"])
    cache.store(a, (1,), 0.9, "r", "m")
    assert cache.lookup(b) is None


def test_negation_in_long_question_never_hits(cache):
    long = (
        "Sie fahren auf einer Landstraße bei Nacht und Regen hinter einem langsam fahrenden Traktor her. "
        "Der Gegenverkehr ist nur schwer einzuschätzen und die Fahrbahn ist nass. Wann dürfen Sie überholen?"
    )
    a = q(long, ["Wenn die Sicht frei ist", "Im Tunnel"])
    b = q(long.replace("dürfen Sie", "dürfen Sie nicht"), ["Wenn die Sicht frei ist", "Im Tunnel"])
    cache.store(a, (1,), 0.9, "r", "m")
    assert cache.lookup(b) is None
    # but OCR character noise in the long question still hits
    c = q(long.replace("Traktor", "Traktcr"), ["Wenn die Sicht frei ist", "Im Tunnel"])
    assert cache.lookup(c) is not None


def test_extra_answer_never_hits(cache):
    cache.store(BASE, (1,), 0.9, "r", "m")
    more = q(BASE.text, [a.text for a in BASE.answers] + ["Ich hupe"])
    assert cache.lookup(more) is None


def test_persistence(tmp_path):
    c1 = QuestionCache(tmp_path / "c.db")
    c1.store(BASE, (2,), 0.9, "r", "m", topic="Vorfahrt")
    c1.close()
    c2 = QuestionCache(tmp_path / "c.db")
    hit = c2.lookup(BASE)
    assert hit and hit.answers == (2,) and hit.topic == "Vorfahrt"
    c2.close()


def test_corrupted_cache_recovers(tmp_path):
    p = tmp_path / "c.db"
    p.write_bytes(b"this is not a sqlite database" * 100)
    c = QuestionCache(p)
    assert c.recovered_from_corruption
    assert len(c) == 0
    c.store(BASE, (1,), 0.9, "r", "m")
    assert c.lookup(BASE)
    assert any(x.name.startswith("c.db.corrupt-") for x in tmp_path.iterdir())
    c.close()


def test_eviction(tmp_path):
    c = QuestionCache(tmp_path / "c.db", max_entries=5)
    for i in range(12):
        c.store(q(f"Frage Nummer {i} über etwas", ["a", "b"]), (1,), 0.9, "r", "m")
    assert len(c) == 5
    c.close()


def test_store_rejects_out_of_range(cache):
    with pytest.raises(ValueError):
        cache.store(BASE, (7,), 0.9, "r", "m")


words = st.text(alphabet="abcdefghijklmnopqrstuvwxyzäöü ", min_size=12, max_size=60)


@settings(max_examples=150, deadline=None)
@given(words, words)
def test_property_unrelated_questions_do_not_collide(t1, t2):
    """Random different questions must not produce a hit unless they are near-identical."""
    from rapidfuzz import fuzz

    from smart360.core.models import normalize_text

    c = QuestionCache(":memory:")
    a = q(t1, ["Antwort eins", "Antwort zwei"])
    b = q(t2, ["Antwort eins", "Antwort zwei"])
    c.store(a, (1,), 0.9, "r", "m")
    hit = c.lookup(b)
    if hit is not None:
        assert fuzz.ratio(normalize_text(t1), normalize_text(t2)) >= 97
    c.close()


# ----------------------------------------------------------------------------- confidence


def test_confidence_all_good():
    r = composite_confidence(ConfidenceInputs(model=0.96))
    assert r.value > 0.95


def test_bad_ocr_caps():
    r = composite_confidence(ConfidenceInputs(model=0.99, ocr=0.3))
    assert r.value <= 0.60 and r.capped_by == "ocr"


def test_uncertain_caps_below_threshold():
    r = composite_confidence(ConfidenceInputs(model=0.99, model_uncertain=True), manual_threshold=0.75)
    assert r.value < 0.75


def test_image_clarity_only_counts_with_image():
    a = composite_confidence(ConfidenceInputs(model=0.9, image_clarity=0.1, has_image=False))
    b = composite_confidence(ConfidenceInputs(model=0.9, image_clarity=0.1, has_image=True))
    assert a.value > b.value


@settings(max_examples=300, deadline=None)
@given(*(st.floats(0, 1) for _ in range(5)), st.booleans(), st.booleans())
def test_confidence_bounded_and_monotone(m, o, lay, c, qm, unc, img):
    r = composite_confidence(ConfidenceInputs(m, o, lay, c, qm, None, unc, img))
    assert 0.0 <= r.value <= 1.0
    better = composite_confidence(ConfidenceInputs(min(1, m + 0.1), o, lay, c, qm, None, unc, img))
    assert better.value >= r.value - 1e-9


def test_nan_is_safe():
    r = composite_confidence(ConfidenceInputs(model=float("nan")))
    assert 0 <= r.value <= 0.1


def test_sqlite_available():
    assert sqlite3.sqlite_version
