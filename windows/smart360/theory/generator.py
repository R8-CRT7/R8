"""Synthetic question variants generated from RULES (never copied exam questions).

Variant types: base, paraphrase, negation (statement negated -> truth flips), negative_question ("Welche
Aussage ist falsch?"), number_change, unit_error, exception (absolute claim that ignores an exception),
distractor (true claim of a neighbouring rule in the wrong situation is NOT used - only false claims),
multiselect, ocr_noise, context (same rule, other wording of the situation), calc (formulas), sign,
priority (scene templates with hand-written expected outcomes, rotated), licence (hand-written table).

IMPORTANT: the ground truth comes from the knowledge data / hand-written tables, not from the engine. Because
the engine uses the same knowledge base, synthetic accuracy measures ROBUSTNESS (wording, negation, OCR noise,
numbers, multiselect) - not knowledge breadth. Knowledge breadth is measured by the independent golden set."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any

from smart360.theory import calc
from smart360.theory.kb import KnowledgeBase
from smart360.theory.reasoning import TheoryQuestion
from smart360.theory.scene import scene_from_dict
from smart360.theory.schema import Claim, KnowledgeObject


@dataclass
class TheoryItem:
    id: str
    topic: str
    subtopic: str
    variant: str
    question: TheoryQuestion
    correct: tuple[int, ...]
    number_answer: str | None = None
    sources: list[str] = field(default_factory=list)
    expect_uncertain_ok: bool = False  # e.g. exception variants: UNCERTAIN is an acceptable outcome
    exam_relevance: int = 2
    difficulty: int = 2


SYNONYMS = [
    ("radfahrer", "Radfahrende"), ("fußgänger", "zu Fuß Gehende"), ("fahrzeug", "Kfz"), ("anhalten", "stoppen"),
    ("überholen", "vorbeifahren"), ("geschwindigkeit", "Tempo"), ("kreuzung", "Straßenkreuzung"),
    ("einmündung", "Straßeneinmündung"), ("abstand", "Distanz"), ("rechtzeitig", "frühzeitig"),
    ("vorsichtig", "behutsam"), ("bremsbereit", "bremsbereit"), ("verringern", "reduzieren"),
]

OCR_CONFUSIONS = [("ä", "a"), ("ü", "u"), ("ö", "o"), ("rn", "m"), ("l", "I"), ("ß", "ss"), ("e", "c")]


def _paraphrase(text: str, rng: random.Random) -> str:
    out = text
    for a, b in SYNONYMS:
        if a in out.lower() and rng.random() < 0.7:
            out = re.sub(a, b, out, count=1, flags=re.IGNORECASE)
    return out


def _ocr_noise(text: str, rng: random.Random, rate: float = 0.08) -> str:
    chars = list(text)
    for i, ch in enumerate(chars):
        if rng.random() < rate:
            for a, b in OCR_CONFUSIONS:
                if ch == a and len(a) == 1:
                    chars[i] = b
                    break
    return "".join(chars)


_NEG_INSERT = re.compile(r"\b(darf|dürfen|muss|müssen|ist|sind|hat|haben|kann|können|lasse|fahre|gibt|gilt|gelten|wird|werden)\b",
                         re.IGNORECASE)


def negate(statement: str) -> str | None:
    """Insert 'nicht' after the first finite verb ('darf überholen' -> 'darf nicht überholen')."""
    if re.search(r"\b(nicht|kein\w*|nie)\b", statement, re.IGNORECASE):
        return re.sub(r"\s*\bnicht\b", "", statement, count=1, flags=re.IGNORECASE)
    m = _NEG_INSERT.search(statement)
    if not m:
        return None
    return statement[: m.end()] + " nicht" + statement[m.end():]


def _stem_question(obj: KnowledgeObject, claim: Claim) -> str:
    ctx = ", ".join(claim.context) if claim.context else obj.title
    return f"{obj.title} ({ctx}). Welche Aussagen sind richtig?"


def _change_number(statement: str, rng: random.Random) -> str | None:
    m = re.search(r"(\d+(?:,\d+)?)", statement)
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    nv = v * rng.choice([0.5, 0.8, 1.2, 1.5, 2]) if v else 5
    nv_txt = (f"{nv:.1f}".rstrip("0").rstrip(".")).replace(".", ",")
    if nv_txt == m.group(1):
        return None
    return statement[: m.start()] + nv_txt + statement[m.end():]


def claim_items(kb: KnowledgeBase, seed: int = 7, per_object: int = 12) -> list[TheoryItem]:
    rng = random.Random(seed)
    items: list[TheoryItem] = []
    by_sub: dict[str, list[KnowledgeObject]] = {}
    for o in kb.objects.values():
        by_sub.setdefault(o.subtopic, []).append(o)
    for obj in kb.objects.values():
        trues = [c for c in obj.claims if c.truth]
        falses = [c for c in obj.claims if not c.truth]
        if not trues or not falses:
            continue
        n = 0
        for variant in ("base", "paraphrase", "negation", "negative_question", "multiselect", "ocr_noise",
                        "number_change", "unit_error", "exception", "context"):
            for rep in range(2 if variant in ("base", "paraphrase", "ocr_noise", "multiselect") else 1):
                if n >= per_object:
                    break
                it = _make_variant(obj, trues, falses, variant, rng, f"{obj.id}:{variant}:{rep}")
                if it is not None:
                    items.append(it)
                    n += 1
    return items


def _make_variant(obj: KnowledgeObject, trues: list[Claim], falses: list[Claim], variant: str,
                  rng: random.Random, iid: str) -> TheoryItem | None:
    t = rng.choice(trues)
    f_pool = list(falses)
    rng.shuffle(f_pool)
    opts: list[tuple[str, bool]] = [(t.statement, True)] + [(f.statement, False) for f in f_pool[:2]]
    stem = _stem_question(obj, t)
    uncertain_ok = False
    if variant == "paraphrase":
        opts = [(_paraphrase(s, rng), v) for s, v in opts]
    elif variant == "negation":
        neg = negate(t.statement)
        if neg is None:
            return None
        opts[0] = (neg, False)
        if len(trues) > 1:
            opts.append((rng.choice([c for c in trues if c is not t]).statement, True))
        else:
            negf = negate(f_pool[0].statement)
            if negf is None:
                return None
            opts[1] = (negf, True)
    elif variant == "negative_question":
        stem = f"{obj.title} ({', '.join(t.context) or obj.title}). Welche Aussage ist falsch?"
        opts = [(s, v) for s, v in opts]
    elif variant == "multiselect":
        extra = [c for c in trues if c is not t]
        if not extra:
            return None
        opts.append((rng.choice(extra).statement, True))
    elif variant == "ocr_noise":
        stem = _ocr_noise(stem, rng)
        opts = [(_ocr_noise(s, rng), v) for s, v in opts]
    elif variant == "number_change":
        if not t.numbers:
            return None
        changed = _change_number(t.statement, rng)
        if changed is None:
            return None
        opts = [(changed, False), (t.statement, True), *opts[1:2]]
    elif variant == "unit_error":
        if not re.search(r"\d+\s*km/h", t.statement):
            return None
        opts = [(re.sub(r"(\d+)\s*km/h", r"\1 m", t.statement, count=1), False), (t.statement, True), *opts[1:2]]
    elif variant == "exception":
        if not obj.exceptions:
            return None
        opts.append((f"Das gilt immer und ausnahmslos: {t.statement}", False))
        uncertain_ok = True
    elif variant == "context":
        stem = f"Situation: {', '.join(t.context) or obj.title}. Wie verhalten Sie sich richtig?"
    rng.shuffle(opts)
    want_false = variant == "negative_question"
    correct = tuple(i for i, (_, v) in enumerate(opts, start=1) if v != want_false)
    if not correct:
        return None
    q = TheoryQuestion(stem, [s for s, _ in opts], ocr_confidence=0.7 if variant == "ocr_noise" else 1.0)
    return TheoryItem(iid, obj.topic, obj.subtopic, variant, q, correct, sources=[obj.id],
                      expect_uncertain_ok=uncertain_ok, exam_relevance=obj.exam_relevance, difficulty=obj.difficulty)


# ----------------------------------------------------------------------------- calculation items
CALC_STEMS = {
    "reaction_distance": "Wie lang ist nach der Faustformel der Reaktionsweg bei {v} km/h?",
    "braking_distance": "Wie lang ist nach der Faustformel der Bremsweg (normale Bremsung) bei {v} km/h?",
    "emergency_braking_distance": "Wie lang ist der Bremsweg bei einer Gefahrbremsung aus {v} km/h (Faustformel)?",
    "stopping_distance": "Wie lang ist der Anhalteweg bei {v} km/h (Faustformel, normale Bremsung)?",
    "emergency_stopping_distance": "Wie lang ist der Anhalteweg bei einer Gefahrbremsung aus {v} km/h?",
}


def _fmt(x: float) -> str:
    return (f"{x:.2f}".rstrip("0").rstrip(".")).replace(".", ",")


def calc_items(seed: int = 11) -> list[TheoryItem]:
    rng = random.Random(seed)
    items = []
    for fid, stem in CALC_STEMS.items():
        for v in range(20, 161, 5):
            truth = calc.FORMULAS[fid].fn(v)
            wrong = {calc.FORMULAS[o].fn(v) for o in CALC_STEMS if o != fid} - {truth}
            wrong_l = sorted(wrong)[:2] or [truth * 2]
            for variant in ("calc", "calc_units", "number_input", "calc_ocr"):
                opts = [(f"{_fmt(truth)} m", True)] + [(f"{_fmt(w)} m", False) for w in wrong_l]
                if variant == "calc_units":
                    opts.append((f"{_fmt(truth)} km/h", False))
                q_text = stem.format(v=v)
                if variant == "calc_ocr":
                    q_text = _ocr_noise(q_text, rng, 0.04)
                rng.shuffle(opts)
                if variant == "number_input":
                    q = TheoryQuestion(q_text, [], number_input=True)
                    items.append(TheoryItem(f"CALC:{fid}:{v}:{variant}", "08_speed_distance", "anhalteweg", variant,
                                            q, (), number_answer=_fmt(truth), sources=[fid], exam_relevance=2))
                    continue
                q = TheoryQuestion(q_text, [s for s, _ in opts])
                corr = tuple(i for i, (_, ok) in enumerate(opts, start=1) if ok)
                items.append(TheoryItem(f"CALC:{fid}:{v}:{variant}", "08_speed_distance", "anhalteweg", variant, q,
                                        corr, sources=[fid], exam_relevance=2))
    for k, word, result in ((2, "verdoppelt", "vervierfacht"), (3, "verdreifacht", "verneunfacht")):
        for variant in ("calc_factor", "calc_factor_neg"):
            opts = [(f"Er {result} sich", True), ("Er verdoppelt sich", k != 2 and False), ("Er bleibt gleich", False)]
            if k == 2:
                opts = [(f"Er {result} sich", True), ("Er verdoppelt sich", False), ("Er bleibt gleich", False)]
            q = TheoryQuestion(f"Wie ändert sich der Bremsweg, wenn sich die Geschwindigkeit {word}?",
                               [s for s, _ in opts])
            items.append(TheoryItem(f"CALC:factor:{k}:{variant}", "08_speed_distance", "bremsweg_faktor", variant, q,
                                    (1,), sources=["braking_distance_factor"]))
    return items


# ----------------------------------------------------------------------------- licence items (hand table)
LICENCE_TABLE = [  # towing zGM kg, trailer zGM kg, expected class - from FeV § 6 Abs. 1 (written by hand)
    (1800, 700, "B"), (2000, 750, "B"), (2000, 1000, "B"), (2500, 1000, "B"), (2600, 900, "B"),
    (2200, 1500, "B96"), (2500, 1700, "B96"), (3000, 1200, "B96"), (2000, 2250, "B96"),
    (2800, 2000, "BE"), (3500, 1500, "BE"), (3000, 3500, "BE"), (2500, 2500, "BE"),
]


def licence_items() -> list[TheoryItem]:
    items = []
    for tw, tr, cls in LICENCE_TABLE:
        for variant, stem in (
            ("licence", f"Ihr Pkw hat eine zulässige Gesamtmasse von {tw} kg, der Anhänger {tr} kg. Welche Fahrerlaubnisklasse benötigen Sie mindestens?"),
            ("licence_paraphrase", f"Zugfahrzeug: zulässige Gesamtmasse {tw} kg; Anhänger: zulässige Gesamtmasse {tr} kg. Welche Klasse ist mindestens erforderlich?"),
        ):
            opts = ["Klasse B", "Klasse B96", "Klasse BE"]
            q = TheoryQuestion(stem, opts)
            corr = (opts.index(f"Klasse {cls}") + 1,)
            items.append(TheoryItem(f"LIC:{tw}:{tr}:{variant}", "14_trailers", "fahrerlaubnis_anhaenger", variant,
                                    q, corr, sources=["FEV6"], exam_relevance=3))
    return items


# ----------------------------------------------------------------------------- sign items
def sign_items(kb: KnowledgeBase, seed: int = 13) -> list[TheoryItem]:
    rng = random.Random(seed)
    items = []
    for s in kb.signs.values():
        rivals = [kb.signs[c] for c in s.confusions if c in kb.signs]
        if not rivals:
            continue
        for variant in ("sign", "sign_paraphrase", "sign_ocr"):
            opts = [(s.meaning, True)] + [(r.meaning, False) for r in rivals[:2]]
            if variant == "sign_paraphrase":
                opts = [(_paraphrase(m, rng), v) for m, v in opts]
            rng.shuffle(opts)
            q_text = f"Was bedeutet das Zeichen {s.number}?"
            if variant == "sign_ocr":
                opts = [(_ocr_noise(m, rng, 0.05), v) for m, v in opts]
            q = TheoryQuestion(q_text, [m for m, _ in opts], sign_ids=[s.number])
            corr = tuple(i for i, (_, v) in enumerate(opts, start=1) if v)
            items.append(TheoryItem(f"SIGN:{s.number}:{variant}", "06_signs", f"zeichen_{s.number}", variant, q, corr,
                                    sources=[s.id], exam_relevance=2))
    return items


# ----------------------------------------------------------------------------- priority scene templates
# Hand-written situations with the expected waiting relation (from the StVO, written independently of the
# engine). Each is rotated through 4 orientations and 3 label sets.
PRIORITY_TEMPLATES: list[tuple[str, dict, Any]] = [
    ("rvl_basic", {"junction": {"kind": "crossing", "main_road_arms": [], "roundabout_yield": True},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "straight"},
                      {"id": "x", "kind": "car", "arm": "E", "intent": "straight"}]}, "me_waits"),
    ("rvl_from_left", {"junction": {"kind": "crossing", "main_road_arms": []},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "straight"},
                      {"id": "x", "kind": "car", "arm": "W", "intent": "straight"}]}, "other_waits"),
    ("left_vs_oncoming", {"junction": {"kind": "crossing", "main_road_arms": []},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "left"},
                      {"id": "x", "kind": "car", "arm": "N", "intent": "straight"}]}, "me_waits"),
    ("oncoming_left_turner", {"junction": {"kind": "crossing", "main_road_arms": []},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "straight"},
                      {"id": "x", "kind": "car", "arm": "N", "intent": "left"}]}, "other_waits"),
    ("yield_sign", {"junction": {"kind": "crossing", "main_road_arms": ["E", "W"]},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "straight", "sign": "yield"},
                      {"id": "x", "kind": "car", "arm": "W", "intent": "straight"}]}, "me_waits"),
    ("priority_road", {"junction": {"kind": "crossing", "main_road_arms": ["N", "S"]},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "straight", "sign": "priority_road"},
                      {"id": "x", "kind": "car", "arm": "E", "intent": "straight", "sign": "yield"}]}, "other_waits"),
    ("stop_sign", {"junction": {"kind": "crossing", "main_road_arms": ["E", "W"]},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "right", "sign": "stop"},
                      {"id": "x", "kind": "car", "arm": "W", "intent": "straight"}]}, "me_waits"),
    ("property_exit", {"junction": {"kind": "t_junction", "main_road_arms": []},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "right", "from_property": True},
                      {"id": "x", "kind": "car", "arm": "W", "intent": "straight"}]}, "me_waits"),
    ("emergency", {"junction": {"kind": "crossing", "main_road_arms": ["N", "S"]},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "straight", "sign": "priority_road"},
                      {"id": "x", "kind": "emergency", "arm": "E", "intent": "straight", "emergency_active": True}]}, "me_waits"),
    ("police_stop", {"junction": {"kind": "crossing", "main_road_arms": []},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "straight", "police": "stop"},
                      {"id": "x", "kind": "car", "arm": "W", "intent": "straight", "police": "go"}]}, "me_waits"),
    ("red_light", {"junction": {"kind": "crossing", "main_road_arms": ["N", "S"]},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "straight", "signal": "red", "sign": "priority_road"},
                      {"id": "x", "kind": "car", "arm": "E", "intent": "straight", "signal": "green"}]}, "me_waits"),
    ("turn_right_pedestrian", {"junction": {"kind": "crossing", "main_road_arms": []},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "right"},
                      {"id": "x", "kind": "pedestrian", "arm": "S", "intent": "straight", "crossing_arm": "E"}]}, "me_waits"),
    ("turn_right_cyclist", {"junction": {"kind": "crossing", "main_road_arms": []},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "right"},
                      {"id": "x", "kind": "bicycle", "arm": "S", "intent": "straight", "on_bike_path_straight": True}]}, "me_waits"),
    ("roundabout_inside", {"junction": {"kind": "roundabout", "main_road_arms": [], "roundabout_yield": True},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "right"},
                      {"id": "x", "kind": "car", "arm": "W", "intent": "left", "in_roundabout": True}]}, "me_waits"),
    ("crosswalk", {"junction": {"kind": "crossing", "main_road_arms": []},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "straight"},
                      {"id": "x", "kind": "pedestrian", "arm": "N", "intent": "straight", "crossing_arm": "N", "on_crosswalk": True}]}, "me_waits"),
    ("tram_right", {"junction": {"kind": "crossing", "main_road_arms": []},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "straight"},
                      {"id": "x", "kind": "tram", "arm": "E", "intent": "straight"}]}, "me_waits"),
    ("cyclist_from_left", {"junction": {"kind": "crossing", "main_road_arms": []},
     "participants": [{"id": "me", "kind": "me", "arm": "S", "intent": "straight"},
                      {"id": "x", "kind": "bicycle", "arm": "W", "intent": "straight"}]}, "other_waits"),
]
LABELS = {"car": ["blauen Pkw", "roten Pkw", "grünen Pkw"], "emergency": ["Einsatzfahrzeug"] * 3,
          "pedestrian": ["Fußgänger"] * 3, "bicycle": ["Radfahrer"] * 3, "tram": ["Straßenbahn"] * 3}
ROT = {"N": "E", "E": "S", "S": "W", "W": "N"}


def _rotate(d: dict, times: int) -> dict:
    import copy

    d = copy.deepcopy(d)
    for _ in range(times):
        d["junction"]["main_road_arms"] = [ROT[a] for a in d["junction"].get("main_road_arms", [])]
        for p in d["participants"]:
            p["arm"] = ROT[p["arm"]]
            if p.get("crossing_arm"):
                p["crossing_arm"] = ROT[p["crossing_arm"]]
    return d


def priority_items() -> list[TheoryItem]:
    items = []
    for name, tpl, expect in PRIORITY_TEMPLATES:
        for rot in range(4):
            for li in range(3):
                d = _rotate(tpl, rot)
                kind = next(p["kind"] for p in d["participants"] if p["id"] == "x")
                label = LABELS.get(kind, LABELS["car"])[li]
                for p in d["participants"]:
                    p["labels"] = ["ich"] if p["id"] == "me" else [label]
                d["confidence"] = 0.95
                scene = scene_from_dict(d)
                opts = [f"Ich muss den {label} durchfahren lassen" if kind != "pedestrian" else "Ich muss den Fußgänger durchgehen lassen",
                        f"Der {label} muss mich durchfahren lassen" if kind != "pedestrian" else "Der Fußgänger muss mich durchfahren lassen"]
                corr = (1,) if expect == "me_waits" else (2,)
                q = TheoryQuestion("Wie verhalten Sie sich an dieser Kreuzung?", opts, has_image=True, scene=scene)
                items.append(TheoryItem(f"PRIO:{name}:{rot}:{li}", "05_priority", name, "priority", q, corr,
                                        sources=[name], exam_relevance=3))
    return items


def all_items(kb: KnowledgeBase, seed: int = 7) -> list[TheoryItem]:
    return claim_items(kb, seed) + calc_items() + licence_items() + sign_items(kb) + priority_items()
