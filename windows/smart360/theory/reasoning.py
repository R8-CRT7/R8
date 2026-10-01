"""Theory reasoning pipeline.

INPUT -> normalisation -> question classification -> scene/temporal check -> rule retrieval -> deterministic
calculation -> per-answer evaluation (claims, signs, right of way, numbers) -> exception / negation checks ->
second pass -> confidence calibration -> RESULT (per-answer TRUE / FALSE / UNKNOWN with evidence; UNCERTAIN
whenever the evidence is not sufficient).

The engine never needs the language model. A model answer can be passed in (`llm_selected`) - it then only acts
as one more vote: disagreement makes the result UNCERTAIN, agreement never lifts a weak result."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import StrEnum

from smart360.theory import calc
from smart360.theory.kb import KnowledgeBase, get_kb
from smart360.theory.negation import Deontic, Polarity, analyze, asks_for_negative, deontic_truth
from smart360.theory.priority import PriorityDecision, decide
from smart360.theory.scene import Scene, temporal_check
from smart360.theory.schema import Claim, KnowledgeObject
from smart360.theory.text import NUMBER_TOKEN, content, cosine, fold, numbers, similarity, stem

DEFAULT_THRESHOLD = 0.75
MATCH_MIN = 0.55  # minimum statement similarity for a claim to count
AMBIGUITY_GAP = 0.08
NUMERIC_SITUATION_MIN = 0.3
# Words that change which number applies. If the question contains one that the matched claim does not, a
# numeric answer is not decided from that claim (protects against e.g. "Pkw mit Anhänger" -> Pkw limit).
QUALIFIERS = frozenset(content(" ".join((
    "anhänger wohnanhänger lkw kraftrad bus kraftomnibus schneeketten nebel schneefall regen glätte autobahn "
    "kraftfahrstraße innerorts außerorts kinder radfahrer fußgänger dunkelheit nacht probezeit fahranfänger "
    "baustelle tunnel bahnübergang einbahnstraße kreisverkehr").split())))  # numeric-only answers: minimum question-vs-claim situation similarity


class Verdict(StrEnum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


@dataclass
class TheoryQuestion:
    text: str
    answers: list[str]
    number_input: bool = False
    ocr_confidence: float = 1.0
    has_image: bool = False
    scene: Scene | None = None
    frames: list[Scene] | None = None
    is_video: bool = False
    sign_ids: list[str] = field(default_factory=list)


@dataclass
class AnswerEval:
    index: int
    verdict: Verdict
    method: str = "none"  # calc | sign | priority | claim | none
    evidence: list[str] = field(default_factory=list)
    explanation: str = ""
    score: float = 0.0
    flags: list[str] = field(default_factory=list)


@dataclass
class TheoryResult:
    selected: tuple[int, ...]
    number_answer: str | None
    evals: list[AnswerEval]
    confidence: float
    uncertain: bool
    reasons: list[str]
    kinds: set[str]
    factors: dict[str, float]
    trace: list[tuple[str, str]]

    @property
    def status(self) -> str:
        return "UNCERTAIN" if self.uncertain else "OK"


# ----------------------------------------------------------------------------- classification
_FACTOR_WORDS = {"verdoppelt": 2, "doppelt": 2, "doppelte": 2, "doppelter": 2, "verdreifacht": 3, "dreifach": 3,
                 "dreifache": 3, "halbiert": 0.5, "halbe": 0.5, "halben": 0.5}
_RESULT_FACTOR_WORDS = {"verdoppelt": 2, "verdreifacht": 3, "vervierfacht": 4, "verneunfacht": 9,
                        "halbiert": 0.5, "viertel": 0.25, "gleich": 1, "unverändert": 1, "verachtfacht": 8,
                        "versechsfacht": 6}


def classify(q: TheoryQuestion) -> tuple[set[str], dict]:
    t = fold(q.text)
    kinds: set[str] = set()
    task: dict = {}
    if asks_for_negative(q.text):
        kinds.add("negative_question")
    if q.number_input:
        kinds.add("number_input")
    speeds = [v for v, u in numbers(q.text) if u == "km/h"]
    emergency = bool(re.search(r"gefahr(en)?bremsung|notbremsung|vollbremsung", t))
    if "bremsweg" in t and any(w in t for w in _FACTOR_WORDS) and not speeds:
        k = next(v for w, v in _FACTOR_WORDS.items() if w in t)
        task = {"formula": "braking_distance_factor", "inputs": {"k": k}}
    elif speeds:
        v = speeds[0]
        if "anhalteweg" in t:
            task = {"formula": "emergency_stopping_distance" if emergency else "stopping_distance", "inputs": {"v_kmh": v}}
        elif "bremsweg" in t:
            task = {"formula": "emergency_braking_distance" if emergency else "braking_distance", "inputs": {"v_kmh": v}}
        elif "reaktionsweg" in t:
            task = {"formula": "reaction_distance", "inputs": {"v_kmh": v}}
        elif re.search(r"halbe[rn]? tacho|sicherheitsabstand|mindestabstand", t) and "außerorts" in t.replace("ausserorts", "außerorts"):
            task = {"formula": "safe_distance_half_speedometer", "inputs": {"v_kmh": v}}
        elif re.search(r"(\d+)\s*sekunden?", t) and re.search(r"zurück|fahren sie|legen sie", t):
            secs = float(re.search(r"(\d+(?:[.,]\d+)?)\s*sekunden?", t).group(1).replace(",", "."))  # type: ignore[union-attr]
            task = {"formula": "distance_in_time", "inputs": {"v_kmh": v, "t_s": secs}}
    if task:
        kinds.add("numeric")
    kg = [v for v, u in numbers(q.text) if u in ("kg", "t")]
    if re.search(r"fahrerlaubnis|führerschein|klasse", t) and kg:
        kinds.add("licence")
        masses = [v * 1000 if u == "t" else v for v, u in numbers(q.text) if u in ("kg", "t")]
        task = task or {"licence": masses}
    if q.sign_ids or re.search(r"\b(zeichen|schild|verkehrszeichen)\b", t):
        kinds.add("sign")
    if q.scene is not None or re.search(r"vorfahrt|zuerst|reihenfolge|durchfahren lassen|vorrang", t):
        kinds.add("priority")
    if q.has_image or q.scene is not None:
        kinds.add("image")
    if q.is_video or (q.frames and len(q.frames) > 1):
        kinds.add("video")
    kinds.add("multiselect" if len(q.answers) > 1 and not q.number_input else "single")
    return kinds, task


# ----------------------------------------------------------------------------- claim matching
_POLARITY_WORDS = {stem(w) for w in (
    "nicht", "kein", "keine", "keinen", "nie", "niemals", "darf", "dürfen", "muss", "müssen", "kann", "können",
    "erlaubt", "verboten", "untersagt", "unzulässig", "zulässig", "braucht", "brauchen", "sollte", "nichts")}


def _core(text: str) -> set[str]:
    return {w for w in content(text) if w not in _POLARITY_WORDS}


@dataclass
class _Match:
    obj: KnowledgeObject
    claim: Claim
    score: float
    verdict: Verdict
    flags: list[str]


def _claim_verdict(claim: Claim, answer: str, pa: Polarity) -> tuple[Verdict, list[str]]:
    flags: list[str] = []
    pc = analyze(claim.statement)
    truth = claim.truth
    # numbers are compared per unit: a different value in the same unit as a TRUE claim -> the answer is false;
    # a number the claim does not cover (other unit / claim without numbers) -> not decidable from this claim
    a_nums = {(v, u) for v, u in numbers(answer)}
    c_nums = {(v, u) for v, u in numbers(" ".join(claim.numbers) or claim.statement)}
    if a_nums:
        if not c_nums:
            return Verdict.UNKNOWN, ["number_not_covered"]
        differs = covered = False
        for v, u in a_nums:
            same_unit = {cv for cv, cu in c_nums if cu == u}
            if same_unit:
                covered = True
                differs |= v not in same_unit
        if not covered:
            return Verdict.UNKNOWN, ["unit_mismatch"]
        if differs:
            if truth:
                return Verdict.FALSE, ["number_differs"]
            return Verdict.UNKNOWN, ["number_differs_from_false_claim"]
    if Deontic.NONE not in (pa.deontic, pc.deontic):
        r = deontic_truth(pc.deontic, pa.deontic, truth)
        if r is None:
            return Verdict.UNKNOWN, ["modality_not_comparable"]
        v = r
    elif pa.deontic != Deontic.NONE:  # claim states a behaviour/fact, answer says it is allowed/required/forbidden
        affirm = pa.deontic in (Deontic.PERMITTED, Deontic.OBLIGATORY, Deontic.POSSIBLE)
        v = truth if affirm else not truth
        if pa.deontic == Deontic.POSSIBLE:
            flags.append("weak_modality")
    elif pc.deontic != Deontic.NONE:
        affirm = pc.deontic in (Deontic.PERMITTED, Deontic.OBLIGATORY, Deontic.POSSIBLE)
        v = truth if affirm else not truth
    else:
        v = truth
    if pa.negated != pc.negated:
        v = not v
        flags.append("negation_flip")
    if pa.absolutes and not set(pa.absolutes) & set(pc.absolutes):
        flags.append("absolute_quantifier")
    return (Verdict.TRUE if v else Verdict.FALSE), flags


def match_claims(kb: KnowledgeBase, question: str, answer: str, candidates: list[KnowledgeObject],
                 use_context: bool = True) -> list[_Match]:
    q_core = _core(question)
    a_core = _core(answer)
    pa = analyze(answer)
    a_words = {w for w in a_core if not NUMBER_TOKEN.match(w)}
    numeric_only = bool(numbers(answer)) and len(a_words) <= 1
    out: list[_Match] = []
    for obj in candidates:
        for claim in obj.claims:
            if numeric_only:
                # "100 km/h", "unter 50 m": the words say nothing - the SITUATION (question vs claim) decides
                c_nums = numbers(" ".join(claim.numbers) or claim.statement)
                if not {u for _, u in c_nums} & {u for _, u in numbers(answer)}:
                    continue
                c_all = {w for w in _core(" ".join(claim.context) + " " + claim.statement) if not NUMBER_TOKEN.match(w)}
                s_sit = cosine({w for w in q_core if not NUMBER_TOKEN.match(w)}, c_all)
                if s_sit < NUMERIC_SITUATION_MIN:
                    continue
                verdict, flags = _claim_verdict(claim, answer, pa)
                flags = [*flags, "numeric_answer"]
                missing = (q_core & QUALIFIERS) - c_all
                if missing:  # the question names a situation (Anhänger, Lkw, Nebel ...) this claim does not cover
                    flags.append("qualifier_missing")
                    s_sit *= 0.5 ** len(missing)
                out.append(_Match(obj, claim, s_sit, verdict, flags))
                continue
            s_stmt = similarity(a_core, _core(claim.statement))
            if s_stmt < MATCH_MIN:
                continue
            ctx = _core(" ".join(claim.context)) if claim.context else set()
            s_ctx = max(similarity(q_core, ctx), similarity(q_core, _core(claim.statement))) if ctx else 0.5
            if use_context and claim.context and s_ctx < 0.2:
                continue  # the claim belongs to a different situation
            score = s_stmt * ((0.5 + 0.5 * s_ctx) if use_context else 1.0)
            verdict, flags = _claim_verdict(claim, answer, pa)
            if obj.exceptions and "absolute_quantifier" in flags:
                flags.append("exception_risk")
            out.append(_Match(obj, claim, score, verdict, flags))
    out.sort(key=lambda m: -m.score)
    return out


def _decide_claims(matches: list[_Match]) -> tuple[Verdict, _Match | None, list[str]]:
    """Best DECISIVE match wins - unless an undecidable claim is clearly closer, or two decisive claims within
    the ambiguity gap disagree (-> UNKNOWN, conflicting_rules)."""
    if not matches:
        return Verdict.UNKNOWN, None, ["no_matching_rule"]
    decisive = [m for m in matches if m.verdict != Verdict.UNKNOWN]
    if not decisive:
        return Verdict.UNKNOWN, matches[0], list(matches[0].flags)
    best = decisive[0]
    if matches[0].score - best.score > AMBIGUITY_GAP:
        return Verdict.UNKNOWN, matches[0], [*matches[0].flags, "closest_rule_undecidable"]
    for other in decisive[1:]:
        if best.score - other.score > AMBIGUITY_GAP:
            break
        if other.verdict != best.verdict:
            return Verdict.UNKNOWN, best, ["conflicting_rules"]
    if "exception_risk" in best.flags or "qualifier_missing" in best.flags:
        return Verdict.UNKNOWN, best, [*best.flags]
    return best.verdict, best, list(best.flags)


# ----------------------------------------------------------------------------- numeric / licence / sign / priority
_FACTOR_ANSWER = re.compile("|".join(_RESULT_FACTOR_WORDS))


def _eval_numeric(task: dict, answers: list[str]) -> tuple[list[AnswerEval], calc.CalcResult | None]:
    if "formula" not in task:
        return [], None
    res = calc.compute(task["formula"], **task["inputs"])
    evals = []
    for i, a in enumerate(answers, start=1):
        if task["formula"] == "braking_distance_factor":
            m = _FACTOR_ANSWER.search(fold(a))
            if not m:
                evals.append(AnswerEval(i, Verdict.UNKNOWN, "calc", [res.formula_id], "kein Faktor erkannt"))
                continue
            ok = math.isclose(_RESULT_FACTOR_WORDS[m.group(0)], res.value)
            evals.append(AnswerEval(i, Verdict.TRUE if ok else Verdict.FALSE, "calc", [res.formula_id],
                                    f"Bremsweg × {res.value:g} (quadratisch)", 1.0))
            continue
        nums = [(v, u) for v, u in numbers(a) if u in ("m", "")] or numbers(a)
        if not nums:
            evals.append(AnswerEval(i, Verdict.UNKNOWN, "calc", [res.formula_id], "keine Zahl in der Antwort"))
            continue
        flags = []
        units = {u for _, u in nums if u}
        if units and res.unit not in units:
            flags.append("unit_mismatch")
            evals.append(AnswerEval(i, Verdict.FALSE, "calc", [res.formula_id],
                                    f"falsche Einheit (Ergebnis in {res.unit})", 1.0, flags))
            continue
        ok = any(res.matches(v) for v, _ in nums)
        evals.append(AnswerEval(i, Verdict.TRUE if ok else Verdict.FALSE, "calc", [res.formula_id],
                                "; ".join(res.steps), 1.0, flags))
    return evals, res


def _eval_licence(task: dict, answers: list[str]) -> list[AnswerEval]:
    masses = task.get("licence") or []
    if len(masses) < 2:
        return []
    dec = calc.licence_for_combination(masses[0], masses[1])
    evals = []
    for i, a in enumerate(answers, start=1):
        m = re.search(r"\b(?:klasse\s*)?(b\s*96|be|b)\b", fold(a))
        if not m:
            evals.append(AnswerEval(i, Verdict.UNKNOWN, "calc", list(dec.rule_ids), "keine Klasse erkannt"))
            continue
        cls = m.group(1).replace(" ", "").upper()
        ok = cls == dec.licence or (cls == "BE" and dec.licence == "B96" and False)
        evals.append(AnswerEval(i, Verdict.TRUE if ok else Verdict.FALSE, "calc", list(dec.rule_ids),
                                f"benötigt: Klasse {dec.licence} ({dec.reason})", 1.0))
    return evals


def _target_sign(kb: KnowledgeBase, q: TheoryQuestion) -> str | None:
    if q.sign_ids:
        return q.sign_ids[0] if q.sign_ids[0] in kb.signs else None
    m = re.search(r"zeichen\s*(\d{3,4}(?:-\d+)?)", fold(q.text))
    return m.group(1) if m and m.group(1) in kb.signs else None


def _eval_sign(kb: KnowledgeBase, q: TheoryQuestion) -> list[AnswerEval]:
    num = _target_sign(kb, q)
    if num is None:
        return []
    target = kb.signs[num]
    rivals = [kb.signs[c] for c in target.confusions if c in kb.signs]
    evals = []
    for i, a in enumerate(q.answers, start=1):
        a_core = _core(a)
        pa = analyze(a)
        s_t = similarity(a_core, _core(f"{target.name} {target.meaning} {' '.join(target.keywords)}"))
        s_r = max((similarity(a_core, _core(f"{r.name} {r.meaning} {' '.join(r.keywords)}")) for r in rivals), default=0)
        if max(s_t, s_r) < MATCH_MIN or abs(s_t - s_r) < AMBIGUITY_GAP:
            evals.append(AnswerEval(i, Verdict.UNKNOWN, "sign", [f"SIGN_{num}"], "Bedeutung nicht eindeutig zuzuordnen",
                                    max(s_t, s_r)))
            continue
        v = s_t > s_r
        if pa.negated:
            v = not v
        evals.append(AnswerEval(i, Verdict.TRUE if v else Verdict.FALSE, "sign", [f"SIGN_{num}"],
                                f"Zeichen {num} ({target.name}): {target.meaning}", max(s_t, s_r)))
    return evals


_ME_WAITS = re.compile(r"\bich (muss|lasse|warte|gewähre|halte)\b|\bmuss ich\b|\blasse ich\b|\bwarte ich\b")
_OTHER_WAITS = re.compile(r"\b(muss|müssen|lässt|lassen) (mich|mir)\b|\bvor mir\b|\bich darf vor\b|\bich habe vorfahrt\b|\bich darf (vor|als erste)|\bmuss warten\b|\bmüssen warten\b")
_FIRST = re.compile(r"\b(als erste[rs]?|zuerst)\b")


def _eval_priority(q: TheoryQuestion) -> tuple[list[AnswerEval], PriorityDecision | None]:
    scene = q.scene
    if scene is None or not scene.participants:
        return [], None
    dec = decide([p.participant for p in scene.participants], scene.junction)
    me = scene.me()
    evals = []
    for i, a in enumerate(q.answers, start=1):
        t = fold(a)
        refs = [p for p in scene.find(a) if not p.is_me]
        ev = AnswerEval(i, Verdict.UNKNOWN, "priority", sorted({y.rule_id for y in dec.yields}))
        if me is None:
            ev.explanation = "eigenes Fahrzeug nicht im Szenenmodell"
        elif _FIRST.search(t) and not refs:
            subject_me = bool(re.search(r"\bich\b", t))
            first = dec.first()
            if dec.deadlock or dec.uncertain:
                ev.explanation = "; ".join(dec.uncertain) or "Reihenfolge unklar"
            elif subject_me:
                ev.verdict = Verdict.TRUE if first == [me.participant.id] or me.participant.id in first else Verdict.FALSE
                ev.explanation = f"Zuerst fahren: {', '.join(first)}"
        elif refs:
            other = refs[0].participant.id
            pair_unc = [u for u in dec.uncertain if me.participant.id in u and other in u]
            if pair_unc or dec.deadlock:
                ev.explanation = "; ".join(pair_unc or dec.uncertain)
            elif _OTHER_WAITS.search(t):
                ev.verdict = Verdict.TRUE if dec.must_wait_for(other, me.participant.id) else Verdict.FALSE
            elif _ME_WAITS.search(t) or re.search(r"durchfahren lassen|vorlassen|vorfahrt gewähren|warten", t):
                ev.verdict = Verdict.TRUE if dec.must_wait_for(me.participant.id, other) else Verdict.FALSE
            if analyze(a).negated and ev.verdict != Verdict.UNKNOWN:
                ev.verdict = Verdict.FALSE if ev.verdict == Verdict.TRUE else Verdict.TRUE
            why = [f"{y.waits} wartet auf {y.for_} ({y.reason})" for y in dec.yields if me.participant.id in (y.waits, y.for_)]
            ev.explanation = ev.explanation or "; ".join(why)
        ev.score = 1.0 if ev.verdict != Verdict.UNKNOWN else 0.0
        evals.append(ev)
    return evals, dec


# ----------------------------------------------------------------------------- pipeline
SOURCE_WEIGHT = {1: 1.0, 2: 0.96, 3: 0.93, 4: 0.9, 5: 0.86, 6: 0.6, 9: 0.5}


def solve(q: TheoryQuestion, kb: KnowledgeBase | None = None, threshold: float = DEFAULT_THRESHOLD,
          llm_selected: tuple[int, ...] | None = None) -> TheoryResult:
    kb = kb or get_kb()
    trace: list[tuple[str, str]] = []
    reasons: list[str] = []
    norm_q = fold(q.text)
    trace.append(("normalization", norm_q[:200]))
    kinds, task = classify(q)
    trace.append(("classification", ", ".join(sorted(kinds))))

    # scene / temporal
    image_conf = 1.0
    if "image" in kinds or "video" in kinds:
        image_conf = q.scene.confidence if q.scene else 0.35
        tc = temporal_check(q.text, q.frames or ([q.scene] if q.scene else None), q.is_video)
        trace.append(("scene", f"scene={'yes' if q.scene else 'no'} temporal={tc.reason}"))
        if not tc.complete:
            reasons.append(tc.reason)
            image_conf = min(image_conf, 0.3)
        if q.scene is None and "image" in kinds:
            reasons.append("picture question without a scene model")

    # rule retrieval (question + all answers)
    retrieved = kb.retrieve(q.text + " " + " ".join(q.answers), limit=12)
    candidates = [o for _, o in retrieved]
    trace.append(("retrieval", ", ".join(o.id for o in candidates[:8])))

    n = len(q.answers)
    evals: dict[int, AnswerEval] = {}
    number_answer = None
    calc_used = False

    # deterministic calculation
    num_evals, calc_res = _eval_numeric(task, q.answers) if task else ([], None)
    if calc_res is not None:
        calc_used = True
        trace.append(("calculation", " | ".join(calc_res.steps)))
        if q.number_input:
            number_answer = f"{calc_res.value:g}".replace(".", ",")
    for e in num_evals:
        evals[e.index] = e
    for e in _eval_licence(task, q.answers) if "licence" in kinds else []:
        evals.setdefault(e.index, e)
        calc_used = True

    # signs / right of way (structured evidence first)
    if "sign" in kinds:
        for e in _eval_sign(kb, q):
            if e.verdict != Verdict.UNKNOWN or e.index not in evals:
                evals.setdefault(e.index, e)
    prio_dec = None
    if q.scene is not None:
        p_evals, prio_dec = _eval_priority(q)
        for e in p_evals:
            if e.verdict != Verdict.UNKNOWN:
                evals[e.index] = e
        if prio_dec is not None:
            trace.append(("priority", f"order={prio_dec.order} uncertain={prio_dec.uncertain}"))

    # claims (semantic checks A: question context + answer)
    claim_matches: dict[int, _Match | None] = {}
    for i, a in enumerate(q.answers, start=1):
        if i in evals and evals[i].verdict != Verdict.UNKNOWN:
            continue
        matches = match_claims(kb, q.text, a, candidates)
        verdict, best, flags = _decide_claims(matches)
        claim_matches[i] = best
        if best is not None:
            evals[i] = AnswerEval(i, verdict, "claim", [best.obj.id], _explain(best), best.score, flags)
        else:
            evals.setdefault(i, AnswerEval(i, Verdict.UNKNOWN, "none", [], "keine passende Regel gefunden", 0.0,
                                           flags))
    trace.append(("semantic_check_A", " ".join(f"{i}:{e.verdict}" for i, e in sorted(evals.items()))))

    # semantic check B: answer alone against all rules of the retrieved topics (no situation weighting)
    disagreements = 0
    for i, best in claim_matches.items():
        if best is None or evals[i].verdict == Verdict.UNKNOWN:
            continue
        alt = match_claims(kb, q.text, q.answers[i - 1], [best.obj], use_context=False)
        alt_v, _, _ = _decide_claims(alt)
        if alt_v not in (evals[i].verdict, Verdict.UNKNOWN):
            disagreements += 1
            evals[i].flags.append("pass_disagreement")
            evals[i].verdict = Verdict.UNKNOWN
    trace.append(("semantic_check_B", f"disagreements={disagreements}"))

    # semantic check C: numbers / units in the answers against numeric rules of the matched objects
    for e in evals.values():
        if "unit_mismatch" in e.flags and e.method == "claim":
            e.verdict = Verdict.FALSE if e.verdict == Verdict.TRUE else e.verdict
    trace.append(("semantic_check_C", "units checked"))

    # exception + negation checks
    neg_q = "negative_question" in kinds
    exc = [i for i, e in evals.items() if "exception_risk" in e.flags or "absolute_quantifier" in e.flags]
    trace.append(("exception_check", f"risky answers={exc}"))
    trace.append(("negation_check", f"question asks for wrong/forbidden options={neg_q}"))

    ordered = [evals[i] for i in range(1, n + 1)]
    want = Verdict.FALSE if neg_q else Verdict.TRUE
    selected = tuple(e.index for e in ordered if e.verdict == want)

    # second pass
    unknown = [e.index for e in ordered if e.verdict == Verdict.UNKNOWN]
    if unknown:
        reasons.append(f"answers without sufficient evidence: {unknown}")
    if not q.number_input and n > 1 and not selected:
        reasons.append("no answer selected - an exam question has at least one correct answer")
    if q.number_input and number_answer is None:
        reasons.append("number question without a deterministic calculation")
    if llm_selected is not None and tuple(sorted(llm_selected)) != tuple(sorted(selected)):
        reasons.append(f"language model disagrees ({sorted(llm_selected)} vs {sorted(selected)})")
    if prio_dec is not None and (prio_dec.deadlock or prio_dec.uncertain) and any(e.method == "priority" for e in ordered):
        reasons.append("right-of-way not fully decidable")
    if q.ocr_confidence < 0.6:
        reasons.append("low OCR confidence")
    unverified = sorted({x for e in ordered if e.verdict != Verdict.UNKNOWN for x in e.evidence
                         if not kb.verified(x)})
    if unverified:
        reasons.append(f"rule not verified against an official law text: {unverified}")
    trace.append(("second_pass", "; ".join(reasons) or "ok"))

    # confidence calibration
    decided = [e for e in ordered if e.verdict != Verdict.UNKNOWN]
    coverage = len(decided) / n if n else (1.0 if number_answer else 0.0)
    match = min((e.score for e in decided if e.method == "claim"), default=1.0)
    used = [kb.objects[x] for e in decided for x in e.evidence if x in kb.objects]
    source = min((SOURCE_WEIGHT.get(o.source_priority, 0.6) * o.confidence for o in used), default=1.0)
    agreement = 1.0 if disagreements == 0 and not any("disagrees" in r for r in reasons) else 0.4
    exception_risk = 0.75 if exc else 1.0
    ambiguity = 0.6 if any("conflicting_rules" in e.flags for e in ordered) else 1.0
    calc_cert = 1.0 if calc_used or not task else 0.5
    factors = {
        "ocr": max(0.01, q.ocr_confidence), "image": image_conf, "rule_coverage": max(0.01, coverage),
        "match": max(0.01, min(1.0, match)), "source": source, "calculation": calc_cert, "agreement": agreement,
        "exception_risk": exception_risk, "ambiguity": ambiguity,
    }
    weights = {"ocr": 1.0, "image": 1.5, "rule_coverage": 2.5, "match": 1.5, "source": 1.0, "calculation": 1.0,
               "agreement": 2.0, "exception_risk": 1.0, "ambiguity": 1.0}
    conf = math.exp(sum(weights[k] * math.log(v) for k, v in factors.items()) / sum(weights.values()))
    uncertain = bool(reasons) or conf < threshold
    if uncertain:
        conf = min(conf, threshold - 0.01)  # same safety cap as the app's confidence engine
    trace.append(("confidence", f"{conf:.3f} " + " ".join(f"{k}={v:.2f}" for k, v in factors.items())))
    return TheoryResult(selected, number_answer, ordered, round(conf, 4), uncertain, reasons, kinds, factors, trace)


def _explain(m: _Match) -> str:
    o = m.obj
    src = o.sources[0]
    where = f"{src.law} {src.norm} {src.para or ''}".strip() if src.law else (src.ref or src.type)
    return f"{o.title}: {o.rule} [{where}]"
