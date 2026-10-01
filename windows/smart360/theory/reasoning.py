"""Theory reasoning pipeline.

INPUT -> normalisation -> question classification -> scene/temporal check -> rule retrieval -> deterministic
calculation -> per-answer evaluation (claims, signs, right of way, numbers) -> exception / negation checks ->
second pass -> confidence calibration -> RESULT (per-answer TRUE / FALSE / UNKNOWN with evidence; UNCERTAIN
whenever the evidence is not sufficient).

The engine never needs the language model. A model answer can be passed in (`llm_selected`) - it then only acts
as one more vote: disagreement makes the result UNCERTAIN, agreement never lifts a weak result."""

from __future__ import annotations

import dataclasses
import math
import re
import time
from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache

from smart360.theory import calc
from smart360.theory.kb import KnowledgeBase, get_kb
from smart360.theory.negation import Deontic, Polarity, analyze, asks_for_negative, deontic_truth
from smart360.theory.numeric_model import comparator_of, judge_number, unit_fits
from smart360.theory.priority import PriorityDecision, decide
from smart360.theory.prove_false import prove_false
from smart360.theory.retrieval import claim_frame, hybrid_retrieve, structural_conflict
from smart360.theory.scene import Scene, temporal_check
from smart360.theory.schema import Claim, KnowledgeObject, Sign
from smart360.theory.semantics import (
    action_concepts,
    actor,
    flip_opposites,
    load_lexicon,
    opposite_conflict,
    participle_base,
    precedence,
    resolve_answer,
    resolve_roles,
    separable_verbs,
    situation_conflict,
    split_compound,
    vocab_alias,
    yes_no_proposition,
)
from smart360.theory.text import (
    NUMBER_TOKEN,
    UMLAUT_FOLD,
    canon,
    content,
    cosine,
    fold,
    numbers,
    ocr_repair,
    similarity,
    stem,
    vocab_repair,
)

DEFAULT_THRESHOLD = 0.75
MATCH_MIN = 0.55  # minimum statement similarity for a claim to count
AMBIGUITY_GAP = 0.08
RETRIEVAL_LIMIT = 12  # candidate rules handed to the deterministic checks
SPECIFIC_WINDOW = 0.25  # how far below the best match a more specific, disagreeing claim is still heard
SPECIFICITY_GAP = 2  # matched situation terms more than the best claim that make a claim 'more specific'
NUMERIC_SITUATION_MIN = 0.3
SIGN_MATCH_MIN = 0.35  # cosine between an answer and a sign description
# Words that change which number applies. If the question contains one that the matched claim does not, a
# numeric answer is not decided from that claim (protects against e.g. "Pkw mit Anhänger" -> Pkw limit).
QUALIFIERS = frozenset(content(" ".join((
    "anhänger wohnanhänger lkw kraftrad bus kraftomnibus schneeketten nebel schneefall regen glätte autobahn "
    "kraftfahrstraße innerorts außerorts kinder radfahrer fußgänger dunkelheit nacht probezeit fahranfänger "
    "baustelle tunnel bahnübergang einbahnstraße kreisverkehr schienenfahrzeug").split())))  # numeric-only answers: minimum question-vs-claim situation similarity


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
    method: str = "none"  # calc | sign | priority | claim | joint | none
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
    timings: dict[str, float] = field(default_factory=dict)  # seconds: retrieval_latency, reasoning_latency

    @property
    def status(self) -> str:
        return "UNCERTAIN" if self.uncertain else "OK"


# ----------------------------------------------------------------------------- classification
_FACTOR_WORDS = {"verdoppelt": 2, "doppelt": 2, "doppelte": 2, "doppelter": 2, "verdreifacht": 3, "dreifach": 3,
                 "dreifache": 3, "halbiert": 0.5, "halbe": 0.5, "halben": 0.5}
_RESULT_FACTOR_WORDS = {"verdoppelt": 2, "verdreifacht": 3, "vervierfacht": 4, "verneunfacht": 9,
                        "halbiert": 0.5, "viertel": 0.25, "gleich": 1, "unverändert": 1, "verachtfacht": 8,
                        "versechsfacht": 6}


_KEYWORDS = ("gefahrbremsung", "notbremsung", "vollbremsung", "anhalteweg", "bremsweg", "reaktionsweg",
             "sicherheitsabstand", "verdoppelt", "verdreifacht", "halbiert")


def _repair_keywords(t: str) -> str:
    """OCR-tolerant keyword spotting: a token within one edit of a calculation keyword is replaced by it
    ('gcfahrbremsung' -> 'gefahrbremsung'). Only these few keywords - never free text."""
    from rapidfuzz.distance import Levenshtein

    out = []
    for w in t.split(" "):
        core = w.strip(".,;:?!()")
        hit = next((k for k in _KEYWORDS if core != k and len(core) >= 7
                    and Levenshtein.distance(core, k, score_cutoff=1) <= 1), None)
        out.append(w.replace(core, hit) if hit else w)
    return " ".join(out)


def classify(q: TheoryQuestion) -> tuple[set[str], dict]:
    t = fold(q.text)
    kinds: set[str] = set()
    task: dict = {}
    if asks_for_negative(q.text):
        kinds.add("negative_question")
    if q.number_input:
        kinds.add("number_input")
    speeds = [v for v, u in numbers(q.text) if u == "km/h"]
    t = _repair_keywords(t)
    emergency = bool(re.search(r"gefahr(en)?bremsung|notbremsung|vollbremsung", t))
    if "bremsweg" in t and any(w in t for w in _FACTOR_WORDS) and not speeds:
        k = next(v for w, v in _FACTOR_WORDS.items() if w in t)
        task = {"formula": "braking_distance_factor", "inputs": {"k": k}}
    elif "bremsweg" in t and len(speeds) >= 2 and re.search(r"\bstatt\b|\bändert\b|\bverändert\b|\bvon .* auf\b", t) \
            and speeds[0] > 0:
        # 'statt 30 km/h nun 90 km/h': ratio of two speeds -> factor of the braking distance
        task = {"formula": "braking_distance_factor", "inputs": {"k": speeds[1] / speeds[0]}}
    elif speeds:
        v = speeds[0]
        if "anhalteweg" in t:
            task = {"formula": "emergency_stopping_distance" if emergency else "stopping_distance", "inputs": {"v_kmh": v}}
        elif "bremsweg" in t:
            task = {"formula": "emergency_braking_distance" if emergency else "braking_distance", "inputs": {"v_kmh": v}}
        elif "reaktionsweg" in t:
            task = {"formula": "reaction_distance", "inputs": {"v_kmh": v}}
        elif re.search(r"halbe[rn]? tacho|sicherheitsabstand|mindestabstand|abstand\b.*\b(vorausfahrend|vordermann|"
                       r"vorderfahrzeug|faustregel)|faustregel\b.*\babstand", t) and "außerorts" in t.replace("ausserorts", "außerorts"):
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
        if q.sign_ids or re.search(r"\bbedeut|\bwas (zeigt|sagt|gilt bei) (das|dieses) (zeichen|schild)|\bwelche bedeutung", t):
            kinds.add("sign_meaning")
    if q.scene is not None or re.search(r"vorfahrt|zuerst|reihenfolge|durchfahren lassen|vorrang", t):
        kinds.add("priority")
    if q.has_image or q.scene is not None:
        kinds.add("image")
    if q.is_video or (q.frames and len(q.frames) > 1):
        kinds.add("video")
    kinds.add("multiselect" if len(q.answers) > 1 and not q.number_input else "single")
    return kinds, task


# ----------------------------------------------------------------------------- claim matching
_POLARITY_WORDS = {f(stem(w)) for f in (lambda x: x, lambda x: x.translate(UMLAUT_FOLD)) for w in (
    "nicht", "kein", "keine", "keinen", "nie", "niemals", "darf", "dürfen", "muss", "müssen", "kann", "können",
    "erlaubt", "verboten", "untersagt", "unzulässig", "zulässig", "braucht", "brauchen", "sollte", "nichts", "niemand")}


def _core(text: str) -> set[str]:
    """Content words + compound parts known to the KB ('Grundstücksausfahrt' -> grundstück, ausfahrt) + separable
    verbs re-joined ('schleppen ... ab' -> abschleppen)."""
    return set(_core_cached(text))


@lru_cache(maxsize=200_000)
def _core_cached(text: str) -> frozenset[str]:
    base = {w for w in content(text) if w not in _POLARITY_WORDS}
    extra: set[str] = set()
    for w in base:
        extra.update(split_compound(w))
        extra.update(participle_base(w))
        extra.update(vocab_alias(w))
    for v in separable_verbs(text):
        extra |= content(v)
    return frozenset(base | (extra - _POLARITY_WORDS))


# words that only say what kind of question it is - a question made of these names no situation
_META = frozenset(content("aussage aussagen falsch richtig richtige gilt gelten tun verhalten wann wie was welche "
                          "welcher bedeutet bedeutung zutreffend korrekt trifft zu stimmt hier dabei folgende"))


@dataclass
class _Match:
    obj: KnowledgeObject
    claim: Claim
    score: float
    verdict: Verdict
    flags: list[str]
    s_ctx: float = 0.0  # how well the claim's situation matches the question
    spec: float = 0.0  # number of question terms the claim's context names (specificity of its situation)


_CONJ = r"(solange|wenn|weil|dass|ob|bis|obwohl|falls|sofern|nachdem|bevor|damit|sodass|während|sobald)"
_SUBCLAUSE_MID = re.compile(r",\s*(" + _CONJ[1:-1] + r"|die|der|das|welche[rs]?|den|dem|deren|dessen)\b[^,]*(,|$)",
                            re.IGNORECASE)
_LEADING_CONDITION = re.compile(
    r"^\s*(" + _CONJ[1:-1] + r"|kann|können|ist|sind|hat|haben|muss|müssen|darf|dürfen|steht|stehen|wird|werden|"
    r"gibt|kommt|kommen|fährt|fahren|nähert|liegt|bleibt)\b[^,]*,\s*(.+)$", re.IGNORECASE)


def main_clause(text: str) -> str:
    """Only the main clause carries the polarity of a statement:
    'Ich darf durchfahren, solange die Schranke nicht geschlossen ist' -> 'Ich darf durchfahren'
    'Kinder, die kleiner als 150 cm sind, brauchen ...'                 -> 'Kinder brauchen ...'
    'Kann ich den Übergang nicht räumen, muss ich warten'              -> 'muss ich warten'"""
    t = text.strip()
    m = _LEADING_CONDITION.match(t)
    if m:
        t = m.group(2)
    prev = None
    while prev != t:
        prev = t
        t = _SUBCLAUSE_MID.sub(lambda mm: " " if mm.group(2) == "," else "", t, count=1)
    return re.sub(r"\s+", " ", t).strip() or text


def condition_part(text: str) -> str:
    """Everything that main_clause() removed (conditions, relative clauses)."""
    main = set(main_clause(text).lower().split())
    return " ".join(w for w in text.lower().replace(",", " ").split() if w not in main)


def _claim_verdict(claim: Claim, answer: str, pa: Polarity, numbers_text: str | None = None) -> tuple[Verdict, list[str]]:
    flags: list[str] = []
    pc = analyze(main_clause(claim.statement))
    truth = claim.truth
    # numbers are compared per unit: a different value in the same unit as a TRUE claim -> the answer is false;
    # a number the claim does not cover (other unit / claim without numbers) -> not decidable from this claim
    a_list = numbers(answer if numbers_text is None else numbers_text)
    c_list = numbers(" ".join([*claim.numbers, claim.statement]))
    if truth and not a_list and any(u for _, u in numbers(claim.statement)):
        # 'Warndreieck etwa 100 m hinter das Fahrzeug' cannot confirm 'Warndreieck direkt hinter das Fahrzeug':
        # the claim's decisive quantity is missing in the answer
        return Verdict.UNKNOWN, ["claim_quantity_missing"]
    if a_list:
        if not c_list:
            return Verdict.UNKNOWN, ["number_not_covered"]
        c_set = set(c_list)
        c_units = {u for _, u in c_list}
        differs = False
        uncovered = False
        for v, u in a_list:
            if (v, u) in c_set:
                continue
            if u in c_units:
                differs = True  # same unit, other value
            else:
                uncovered = True  # a number the claim says nothing about
        same_count = len(a_list) == len(numbers(claim.statement)) and sorted(a_list) != sorted(numbers(claim.statement))
        if differs or (same_count and not uncovered):
            a_text = answer if numbers_text is None else numbers_text
            a_val, a_unit = a_list[0]
            c_same = [(v, u) for v, u in c_list if u == a_unit] or c_list
            c_cmp = comparator_of(claim.statement, c_same[0][0], c_same[0][1])
            if c_cmp != "eq" and comparator_of(a_text, a_val, a_unit) != c_cmp:
                # 'mehr als 20 l' (threshold) vs 'mit 5 l': a different value is no contradiction by itself
                return Verdict.UNKNOWN, ["threshold_not_comparable"]
            if truth:
                return Verdict.FALSE, ["number_differs"]
            return Verdict.UNKNOWN, ["number_differs_from_false_claim"]
        if uncovered:
            return Verdict.UNKNOWN, ["number_not_covered"]
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
    # a negated CONDITION states a different rule ('Kann ich ... zügig räumen, muss ich warten' is not the rule)
    a_cond, c_cond = condition_part(answer), condition_part(claim.statement)
    if a_cond and c_cond and analyze(a_cond).negated != analyze(c_cond).negated:
        return Verdict.UNKNOWN, ["condition_polarity_differs"]
    if pa.absolutes and not set(pa.absolutes) & set(pc.absolutes):
        flags.append("absolute_quantifier")
    return (Verdict.TRUE if v else Verdict.FALSE), flags


def match_claims(kb: KnowledgeBase, question: str, answer: str, candidates: list[KnowledgeObject],
                 use_context: bool = True) -> list[_Match]:
    q_core = _core(question)
    a_core = _core(answer)
    pa = analyze(main_clause(answer))
    a_words = {w for w in a_core if not NUMBER_TOKEN.match(w)}
    numeric_only = bool(numbers(answer)) and len(a_words) <= 1
    excluded = _excluded_terms(question)
    # lex specialis: a question qualifier ('Straßenbahn') that some candidate claim covers shadows the general
    # claims that do not mention it - they cannot decide alone
    q_quals = (q_core & QUALIFIERS) - _negated_qualifiers(question)
    obj_core = {obj.id: _object_core(obj) for obj in candidates}
    specific = set().union(*(q_quals & c for c in obj_core.values())) if candidates else set()
    out: list[_Match] = []
    q_frame = claim_frame(question)
    for obj in candidates:
        # rules (objects) that never mention a question qualifier another candidate rule covers are general rules
        shadowed = specific - obj_core[obj.id]
        topic_core = _core(obj.title + " " + " ".join(obj.keywords))
        for claim in (part for c in obj.claims for part in _claim_parts(c)):
            if situation_conflict(question, " ".join(claim.context) + " " + claim.statement, answer):
                continue  # 'Arm hoch' claim for an 'Arme quer' question, 'Zeichen 283' for 'Zeichen 286'
            c_frame = claim_frame(" ".join(claim.context) + ". " + claim.statement)
            if structural_conflict(q_frame, c_frame):
                # innerorts question vs außerorts claim, Lkw question vs Pkw-only claim - unless the answer names
                # its own situation and that one fits the claim ('Außerorts gilt ...')
                a_frame = claim_frame(answer)
                if not (a_frame.road_context or a_frame.vehicle_context - {"trailer"}) or \
                        structural_conflict(a_frame, c_frame):
                    continue
            if numeric_only:
                # "100 km/h", "unter 50 m": the words say nothing - the SITUATION (question vs claim) decides
                if not all(unit_fits(question, u) for _, u in numbers(answer) if u):
                    continue  # 'Wie weit ...?' is never answered by a km/h rule
                c_nums = numbers(" ".join(claim.numbers) or claim.statement)
                if not {u for _, u in c_nums} & {u for _, u in numbers(answer)}:
                    continue
                c_all = {w for w in _core(" ".join(claim.context) + " " + claim.statement) if not NUMBER_TOKEN.match(w)}
                s_sit = cosine({w for w in q_core if not NUMBER_TOKEN.match(w)}, c_all)
                if s_sit < NUMERIC_SITUATION_MIN:
                    continue
                verdict, flags = _claim_verdict(claim, answer, pa)
                if verdict != Verdict.UNKNOWN and "number_differs" not in flags:
                    flags = [f for f in flags if f != "negation_flip"]
                    # a bare value has no polarity of its own: it fills the question's slot, so the claim's own
                    # negation ('darf bis 15 m nicht geparkt werden') must not flip it - same value = claim's truth
                    verdict = Verdict.TRUE if claim.truth else Verdict.FALSE
                flags = [*flags, "numeric_answer"]
                missing = _uncovered_qualifiers((q_core & QUALIFIERS) - _negated_qualifiers(question), c_all)
                excluded = _negated_qualifiers(question) & c_all
                if excluded:  # question says 'ohne Anhänger' but the claim is about the trailer case
                    flags.append("qualifier_excluded")
                    s_sit *= 0.25
                if missing:  # the question names a situation (Anhänger, Lkw, Nebel ...) this claim does not cover
                    flags.append("qualifier_missing")
                    s_sit *= 0.5 ** len(missing)
                out.append(_Match(obj, claim, s_sit, verdict, flags))
                continue
            s_stmt = similarity(a_core, _core(claim.statement))
            flipped = False
            if s_stmt < MATCH_MIN and opposite_conflict(answer, claim.statement):
                # 'Links' vs 'Schienenfahrzeuge sind rechts zu überholen': same proposition, opposite side
                s_stmt = similarity(_core(flip_opposites(answer)), _core(claim.statement))
                flipped = True
            if s_stmt < MATCH_MIN:
                continue
            ctx = _core(" ".join(claim.context)) if claim.context else set()
            if (ctx - _excluded_terms(" ".join(claim.context))) & excluded:
                continue  # the question rules out a situation this claim assumes ('Blaulicht ohne Martinshorn')
            if not q_core - _META:  # 'Welche Aussage ist falsch?' - the question names no situation to compare
                s_ctx = 0.5
            else:
                s_ctx = max(similarity(q_core, ctx), similarity(q_core, _core(claim.statement))) if ctx else 0.5
            if use_context and claim.context and s_ctx < 0.2 and ctx:
                # the answer may name its own situation ('Ein Verbot für Radverkehr gilt ...'): judged by that
                # situation when it names a distinctive context term of the claim (one the rule's other claims lack)
                distinct = ctx - _object_common_ctx(obj) - _core(obj.title)
                if distinct & a_core:
                    s_ctx = max(s_ctx, similarity(a_core, ctx))
            if use_context and claim.context and s_ctx < 0.2:
                continue  # the claim belongs to a different situation
            # same proposition? actor and action concepts must agree (lexicon); precedence order must agree
            a_act, c_act = action_concepts(main_clause(answer)), action_concepts(main_clause(claim.statement))
            contrary = flipped or opposite_conflict(answer, claim.statement)  # 'links' vs 'rechts'
            if a_act and c_act and not a_act & c_act:
                lex = load_lexicon()
                if not any(lex.incompatible_with(x, y) for x in a_act for y in c_act):
                    continue  # different actions - this claim says nothing about the answer
                contrary = True
            a_actor, c_actor = actor(main_clause(answer)), actor(main_clause(claim.statement))
            if a_actor and c_actor and a_actor != c_actor:
                continue
            score = s_stmt * ((0.5 + 0.5 * s_ctx) if use_context else 1.0)
            # specificity: answer words the claim does not cover ('Feldweg') lower the score, so the more
            # specific claim wins over a general one that only matches part of the answer
            covered = len(a_core & (_core(claim.statement) | ctx)) / len(a_core) if a_core else 1.0
            score *= covered ** 2
            c_full = _core(" ".join(claim.context) + " " + claim.statement)
            # condition binding: a special case inside the rule ('In Einbahnstraßen ...') the question does not name
            unmet = (c_full & QUALIFIERS) - q_core - a_core - topic_core
            prec = precedence(claim.statement, answer)
            if prec is not None:
                verdict, flags = (Verdict.TRUE if prec == claim.truth else Verdict.FALSE), ["precedence"]
            elif contrary:
                # the answer does something the claim's action excludes ('anhalten' vs 'weiterfahren')
                affirms = not pa.negated and pa.deontic in (Deontic.NONE, Deontic.OBLIGATORY, Deontic.PERMITTED)
                c_pol = analyze(main_clause(claim.statement))
                c_affirms = not c_pol.negated and c_pol.deontic in (Deontic.NONE, Deontic.OBLIGATORY)
                verdict = Verdict.FALSE if (claim.truth and affirms and c_affirms) else Verdict.UNKNOWN
                flags = ["contrary_action"]
            else:
                verdict, flags = _claim_verdict(claim, answer, pa)
            if obj.exceptions and "absolute_quantifier" in flags:
                flags.append("exception_risk")
            if shadowed:
                flags = [*flags, "qualifier_missing"]
                score *= 0.5
            if unmet and verdict != Verdict.UNKNOWN:
                verdict, flags = Verdict.UNKNOWN, [*flags, "condition_unmet"]
                score *= 0.5
            out.append(_Match(obj, claim, score, verdict, flags, s_ctx, _term_count(q_core & ctx)))
    out.sort(key=lambda m: -m.score)
    return out


def _term_count(words: set[str]) -> float:
    """Number of situation terms: the parts of a split compound ('bahn', 'ubergang' of 'bahnubergang') are one term."""
    return float(sum(not any(w != o and w in o for o in words) for w in words))


@lru_cache(maxsize=4096)
def _object_core_cached(obj_id: str, text: str) -> frozenset[str]:
    return frozenset(_core(text))


@lru_cache(maxsize=4096)
def _common_ctx_cached(obj_id: str, contexts: tuple[str, ...]) -> frozenset[str]:
    cores = [_core(c) for c in contexts if c]
    return frozenset(set.intersection(*cores)) if cores else frozenset()


def _object_common_ctx(obj: KnowledgeObject) -> frozenset[str]:
    """Context words shared by all claims of a rule ('E-Scooter') - they do not distinguish situations."""
    return _common_ctx_cached(obj.id, tuple(" ".join(c.context) for c in obj.claims))


def _object_core(obj: KnowledgeObject) -> frozenset[str]:
    text = " ".join([obj.title, *obj.keywords, *(" ".join(c.context) + " " + c.statement for c in obj.claims)])
    return _object_core_cached(obj.id, text)


_CLAUSE_SPLIT = re.compile(r",(?!\s*(?:" + _CONJ[1:-1] + r"|die|der|das|um|ohne|aber|sondern|denn)\b)\s*|\s+und\s+",
                           re.IGNORECASE)
_SUBJECT_START = re.compile(r"^(ich|sie|er|es|wir|man|der|die|das|den|dem|ein|eine|einen|kein\w*|mein\w*|alle\w*)\b",
                            re.IGNORECASE)


def clauses(answer: str) -> list[str]:
    """'Ich warte und lasse den Gegenverkehr vorbei' -> ['Ich warte', 'ich lasse den Gegenverkehr vorbei'].
    Only 'ich ...' answers are split; the 'ich' subject is carried over to clauses without a subject."""
    parts = [p.strip() for p in _CLAUSE_SPLIT.split(answer) if p and p.strip()]
    if len(parts) < 2 or parts[0].split(" ", 1)[0].lower() != "ich":
        return [answer]
    words = [len({w for w in _core(p) if not NUMBER_TOKEN.match(w)}) for p in parts]
    if min(words) < 1 or sum(words) < 3:
        return [answer]
    return [parts[0], *(p if _SUBJECT_START.match(p) else f"ich {p}" for p in parts[1:])]


def _uncovered_qualifiers(quals: set[str], claim_words: set[str]) -> set[str]:
    """Question qualifiers the claim does not cover. The head of a compound covers it ('Wohnanhänger' is an
    'Anhänger': a claim about Anhänger covers the Wohnanhänger question)."""
    have = claim_words & QUALIFIERS
    return {x for x in quals - claim_words if not any(x != h and x.endswith(h) for h in have)}


def _excluded_terms(text: str) -> set[str]:
    """Content words the question explicitly excludes: 'ohne Martinshorn', 'kein Gehweg' (one word after)."""
    out: set[str] = set()
    for m in re.finditer(r"\b(ohne|kein\w*)\s+(\w+)", canon(text)):
        out |= content(m.group(2))
    return out


def _negated_qualifiers(text: str) -> set[str]:
    """Qualifiers the question explicitly excludes: 'ohne Anhänger', 'kein Lkw'."""
    out: set[str] = set()
    for m in re.finditer(r"\b(ohne|kein\w*)\s+(\w+)", fold(text)):
        out |= content(m.group(2)) & QUALIFIERS
    return out


_YES_NO_Q = re.compile(r"^\s*(darf|dürfen|muss|müssen|ist|sind|kann|können|reicht|gilt|gelten|braucht|brauchen|"
                       r"hat|haben|besteht|sollten?|wird|werden)\b", re.IGNORECASE)
_YES_NO_A = re.compile(r"^\s*(ja|nein)\b[\s,.:;-]*(.*)$", re.IGNORECASE)


def _answer_proposition(question: str, answer: str) -> tuple[str, str]:
    """Yes/no questions: 'Dürfen Sie hier halten?' + 'Nein' -> 'ich darf nicht hier halten' (semantics.Proposition).
    The answer alone ('Ja, wenn ich blinke') says nothing without the question."""
    p = yes_no_proposition(question, answer)
    if p is None:
        return answer, "plain"
    return p.text, "yes_no"


def _yes_no_reason(answer: str) -> str:
    qa = _YES_NO_A.match(answer)
    return qa.group(2).strip() if qa else ""


_NICHT_SONDERN = re.compile(r"^(?P<neg>.*?\b(?:nicht|kein\w*)\b.*?),?\s+sondern\s+(?P<pos>.+)$", re.IGNORECASE)
_LEADING_PRONOUN_REPLY = re.compile(r"^\s*(nichts|niemand|keine[rsn]?)\s*[,:;-]\s*(?=\S)", re.IGNORECASE)


@lru_cache(maxsize=4096)
def _split_claim(statement: str) -> tuple[str, ...]:
    m = _NICHT_SONDERN.match(statement)
    return (m.group("neg").rstrip(" ,"), m.group("pos")) if m else ()


def _claim_parts(claim: Claim) -> list[Claim]:
    """'X ordnet nicht an, A zu tun, sondern warnt' -> 'X ordnet nicht an, A zu tun' + 'warnt': the negation
    binds to the first predicate only; both parts keep the claim's truth."""
    parts = _split_claim(claim.statement)
    if not parts:
        return [claim]
    return [claim.model_copy(update={"statement": p}) for p in parts]


_STATEMENT_Q = re.compile(r"\b(aussagen?|trifft|treffen|zutreffend|richtig|falsch|stimmt|stimmen)\b", re.IGNORECASE)
_SLOT_START = frozenset("auf an am in im bei beim vor hinter neben über unter zwischen nach bis ab mit ohne für zum zur "
                        "innerhalb außerhalb".split())


def _slot_proposition(question: str, answer: str) -> str | None:
    """A short answer without polarity of its own to a W-question that has a polarity ('unzulässig', 'muss',
    'darf nicht') -> the proposition built with the question, else None."""
    if not _is_short(answer) or numbers(answer) or _STATEMENT_Q.search(question):
        return None
    words = answer.split()
    if not (words[0].lower() in _SLOT_START or (len(words) <= 3 and not _SUBJECT_START.match(answer))):
        return None
    pa = analyze(answer)
    if pa.negated or pa.deontic != Deontic.NONE or action_concepts(answer):
        return None
    pq = analyze(question)
    if not pq.negated and pq.deontic == Deontic.NONE:
        return None
    return resolve_answer(question, answer)


def _is_short(answer: str) -> bool:
    return len({w for w in _core(answer) if not NUMBER_TOKEN.match(w)}) <= 4


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
    for other in decisive[1:]:
        # a less similar but clearly more situation-specific claim disagrees: the general rule may not apply here
        # (exception). Never pick a side - UNKNOWN.
        if (best.score - other.score <= SPECIFIC_WINDOW and other.verdict != best.verdict
                and other.spec - best.spec >= SPECIFICITY_GAP):
            return Verdict.UNKNOWN, best, ["more_specific_rule_disagrees"]
    if "number_differs" in best.flags:
        # 'bis 10 dürfen' says nothing against 'bis 8 müssen': a claim of the same rule that names the answer's own
        # quantity and disagrees makes the number comparison unsafe
        for other in decisive[1:]:
            if (best.score - other.score <= SPECIFIC_WINDOW and other.obj.id == best.obj.id
                    and other.verdict != best.verdict and "number_differs" not in other.flags):
                return Verdict.UNKNOWN, best, [*best.flags, "exact_quantity_claim_disagrees"]
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


_RAW_NEG = re.compile(r"\b(nicht|kein\w*|nie|niemals|verboten|untersagt|unzulässig)\b")


def _negative(text: str) -> bool:
    p = analyze(text)
    return p.negated != (p.deontic in (Deontic.FORBIDDEN, Deontic.NOT_OBLIGATORY))


def _eval_sign(kb: KnowledgeBase, q: TheoryQuestion) -> list[AnswerEval]:
    num = _target_sign(kb, q)
    if num is None:
        return []
    target = kb.signs[num]
    rivals = [kb.signs[c] for c in target.confusions if c in kb.signs]
    evals = []

    def desc(sg: Sign, official: bool) -> str:
        # name, curated meaning, keywords - plus, as a fallback, the official evidence text of the sign
        return " ".join([sg.name, sg.meaning, *sg.keywords, *((x.evidence for x in sg.sources if x.evidence)
                                                              if official else ())])

    def fit(a_core: set[str], excl: set[str], a_acts: set[str], sg: Sign, official: bool = False) -> tuple[float, float]:
        d = _core(desc(sg, official))
        if (excl - sign_excl(sg)) & _core(f"{sg.name} {sg.meaning}") or any(
                lex.incompatible_with(x, y) for x in a_acts for y in action_concepts(f"{sg.name}. {sg.meaning}")):
            return 0.0, 0.0  # 'ohne anhalten' contradicts a sign whose meaning is 'anhalten'
        name = _core(sg.name)
        if a_core and a_core == name:
            return 2.0, 1.0  # the official name itself
        cov = len(a_core & d) / len(a_core) if a_core else 0.0
        if len(a_core) <= 6 and action_concepts(f"{sg.name}. {sg.meaning}") - a_acts:
            cov *= 0.5  # a short answer that omits what the sign orders ('Vorfahrt gewähren', 'anhalten')
        return cov, cosine(a_core, d)

    def sign_excl(sg: Sign) -> set[str]:
        return _excluded_terms(f"{sg.name} {sg.meaning}")

    lex = load_lexicon()
    for i, a in enumerate(q.answers, start=1):
        a_core = _core(a)
        a_acts = action_concepts(a)
        excl = _excluded_terms(a)
        a_core = a_core - excl
        f_t = fit(a_core, excl, a_acts, target)
        scored = sorted(((fit(a_core, excl, a_acts, r), r) for r in rivals), key=lambda x: (-x[0][0], -x[0][1]))
        f_r = scored[0][0] if scored else (0.0, 0.0)
        if max(f_t[0], f_r[0]) < 0.5:  # curated wording does not cover the answer: try the official text
            f_t = fit(a_core, excl, a_acts, target, True)
            scored = sorted(((fit(a_core, excl, a_acts, r, True), r) for r in rivals),
                            key=lambda x: (-x[0][0], -x[0][1]))
            f_r = scored[0][0] if scored else (0.0, 0.0)
        s_t, s_r = f_t[0], f_r[0]
        if abs(s_t - s_r) < AMBIGUITY_GAP:  # same coverage: the tighter description decides
            s_t, s_r = f_t[1], f_r[1]
        if max(f_t[0], f_r[0]) < 0.5 or max(f_t[1], f_r[1]) < SIGN_MATCH_MIN / 2 or abs(s_t - s_r) < AMBIGUITY_GAP:
            evals.append(AnswerEval(i, Verdict.UNKNOWN, "sign", [f"SIGN_{num}"], "Bedeutung nicht eindeutig zuzuordnen",
                                    max(s_t, s_r)))
            continue
        matched = target if s_t > s_r else scored[0][1]
        v = s_t > s_r
        # negation relative to the matched meaning ("darf nicht halten" in the meaning itself is no negation)
        pa_ = analyze(a)
        has_polarity = pa_.negated or pa_.deontic != Deontic.NONE
        if has_polarity and not excl:
            canon_diff = _negative(a) != _negative(matched.meaning)
            raw_diff = bool(_RAW_NEG.search(fold(a))) != bool(_RAW_NEG.search(fold(matched.meaning)))
            if canon_diff != raw_diff:  # normalised and literal reading disagree (OCR noise, paraphrase)
                evals.append(AnswerEval(i, Verdict.UNKNOWN, "sign", [f"SIGN_{num}"],
                                        "Verneinung nicht eindeutig", min(1.0, max(f_t[0], f_r[0])), ["polarity_unclear"]))
                continue
            if canon_diff:
                v = not v  # only an answer that itself says 'nicht/verboten/darf' can contradict the meaning
        evals.append(AnswerEval(i, Verdict.TRUE if v else Verdict.FALSE, "sign", [f"SIGN_{num}"],
                                f"Zeichen {num} ({target.name}): {target.meaning}", min(1.0, max(f_t[0], f_r[0]))))
    return evals


_ME_WAITS = re.compile(r"\bich (muss|lasse|warte|gewähre|halte)\b|\bmuss ich\b|\blasse ich\b|\bwarte ich\b")
_OTHER_WAITS = re.compile(r"\b(muss|müssen|lässt|lassen) (mich|mir)\b|\bvor mir\b|\bich darf vor\b|\bich habe vorfahrt\b|\bich darf (vor|als erste)")
_WAIT_VERB = re.compile(r"durchfahren lassen|durchgehen lassen|vorlassen|vorfahrt gewähren|\bwarten\b|\bwartet\b")
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
        others = [p for p in scene.participants if not p.is_me]
        if not refs and len(others) == 1 and _WAIT_VERB.search(t) and not _FIRST.search(t):
            refs = others  # 'Ich muss warten' with exactly one other road user: the reference is unambiguous
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
            elif _ME_WAITS.search(t) or (_WAIT_VERB.search(t) and re.search(r"\bich\b", t)):
                ev.verdict = Verdict.TRUE if dec.must_wait_for(me.participant.id, other) else Verdict.FALSE
            elif _WAIT_VERB.search(t):  # subject is the other road user: 'Der blaue Pkw muss warten'
                ev.verdict = Verdict.TRUE if dec.must_wait_for(other, me.participant.id) else Verdict.FALSE
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
    t_start = time.perf_counter()
    kb = kb or get_kb()
    trace: list[tuple[str, str]] = []
    reasons: list[str] = []
    fixed_q, n_fix = ocr_repair(q.text)
    fixed_a = [ocr_repair(a) for a in q.answers]
    n_fix += sum(n for _, n in fixed_a)
    unreadable: dict[int, list[str]] = {}
    if q.ocr_confidence < 1.0 or n_fix:
        vocab = kb.vocabulary
        fixed_q, n_q, _ = vocab_repair(fixed_q, vocab)
        repaired = []
        for i, (a, _) in enumerate(fixed_a, start=1):
            a2, n_a, unk = vocab_repair(a, vocab)
            n_fix += n_a
            repaired.append(a2)
            if unk and q.ocr_confidence < 0.9:
                unreadable[i] = unk
        n_fix += n_q
        fixed_a = [(a, 0) for a in repaired]
    if n_fix:
        q = dataclasses.replace(q, text=fixed_q, answers=[a for a, _ in fixed_a])
        trace.append(("ocr_repair", f"{n_fix} word(s) repaired"))
    if unreadable:
        trace.append(("ocr_unreadable", "; ".join(f"{i}: {', '.join(w)}" for i, w in unreadable.items())))
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

    # rule retrieval (question + all answers): hybrid - lexical + semantic + concept graph, ranked by structure.
    # Retrieval only proposes candidate rules; every verdict below comes from the deterministic checks.
    t_ret = time.perf_counter()
    hybrid = hybrid_retrieve(q.text + " " + " ".join(q.answers), kb, limit=RETRIEVAL_LIMIT)
    candidates = [c.obj for c in hybrid]
    retrieval_latency = time.perf_counter() - t_ret
    trace.append(("retrieval", ", ".join(f"{c.obj.id}[{'+'.join(sorted(c.channels))}]" for c in hybrid[:8])))

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
    if "sign_meaning" in kinds:
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
    eval_text: dict[int, str] = {}
    for i, a_raw in enumerate(q.answers, start=1):
        if i in evals and evals[i].verdict != Verdict.UNKNOWN:
            continue
        # 'Nichts, erst ab 2 m ist ...': the leading pronoun answers the question, it does not negate the clause
        a = _LEADING_PRONOUN_REPLY.sub("", a_raw) if len(a_raw.split()) > 3 else a_raw
        slot = None
        a_eval, a_mode = _answer_proposition(q.text, a)
        if a_mode == "yes_no":
            verdict, best, flags = _decide_claims(match_claims(kb, q.text, a_eval, candidates))
            flags = [*flags, "yes_no"]
            reason = _yes_no_reason(a)
            if reason and len(_core(reason)) >= 2 and not re.match(r"(wenn|falls|sofern|solange|weil)\b", reason, re.I):
                r_verdict, r_best, _ = _decide_claims(match_claims(kb, q.text, reason, candidates))
                if r_verdict != Verdict.UNKNOWN and verdict not in (Verdict.UNKNOWN, r_verdict):
                    verdict, flags = Verdict.UNKNOWN, [*flags, "yes_no_reason_conflict"]
                elif verdict == Verdict.UNKNOWN and r_verdict != Verdict.UNKNOWN:
                    verdict, best, flags = r_verdict, r_best, [*flags, "yes_no_by_reason"]
        else:
            a = resolve_roles(q.text, a)  # 'Es muss ...' -> 'Ein Kind muss ...', 'dort' -> 'an der Haltestelle'
            if a != a_raw:
                eval_text[i] = a
            matches = match_claims(kb, q.text, a, candidates)
            verdict, best, flags = _decide_claims(matches)
            slot = _slot_proposition(q.text, a)
            if slot:
                # 'Wo ist das Halten unzulässig?' + 'Auf Bahnübergängen': the polarity is the question's - the bare
                # slot answer must not be compared with 'unzulässig' in the claim on its own
                s_verdict, s_best, s_flags = _decide_claims(match_claims(kb, q.text, slot, candidates))
                if s_verdict != Verdict.UNKNOWN or verdict != Verdict.UNKNOWN:
                    verdict, best, flags = s_verdict, s_best or best, [*s_flags, "slot_answer"]
            parts = clauses(a)
            if len(parts) > 1:
                # composition: 'A und B' is true only if every clause is; one false clause makes it false
                sub = [_decide_claims(match_claims(kb, q.text, c, candidates)) for c in parts]
                if any(v == Verdict.FALSE for v, _, _ in sub):
                    if verdict == Verdict.TRUE:
                        verdict, flags = Verdict.UNKNOWN, [*flags, "clause_conflict"]
                    elif verdict == Verdict.UNKNOWN:
                        v, b, f = next(x for x in sub if x[0] == Verdict.FALSE)
                        verdict, best, flags = v, b, [*f, "clause_false"]
                elif verdict == Verdict.UNKNOWN and all(v == Verdict.TRUE for v, _, _ in sub):
                    weakest = min((x[1] for x in sub if x[1] is not None), key=lambda m: m.score, default=best)
                    verdict, best, flags = Verdict.TRUE, weakest, ["clauses_true"]
            if verdict == Verdict.UNKNOWN and _is_short(a):
                # short answer to a W-question: read it together with the question as one proposition
                prop = resolve_answer(q.text, a)
                if prop:
                    r_verdict, r_best, r_flags = _decide_claims(match_claims(kb, q.text, prop, candidates))
                    if r_best is not None and (best is None or r_verdict != Verdict.UNKNOWN):
                        verdict, best, flags = r_verdict, r_best, [*r_flags, "resolved_answer"]
        claim_matches[i] = best
        if "slot_answer" in flags and slot:
            eval_text[i] = slot
        elif a_mode == "yes_no":
            eval_text[i] = a_eval
        if best is not None:
            evals[i] = AnswerEval(i, verdict, "claim", [best.obj.id], _explain(best), best.score, flags)
        else:
            evals.setdefault(i, AnswerEval(i, Verdict.UNKNOWN, "none", [], "keine passende Regel gefunden", 0.0,
                                           flags))
    for i in unreadable:
        if i in evals:
            evals[i].verdict = Verdict.UNKNOWN
            evals[i].flags.append("ocr_unreadable")
    trace.append(("semantic_check_A", " ".join(f"{i}:{e.verdict}" for i, e in sorted(evals.items()))))

    # semantic check B: answer alone against all rules of the retrieved topics (no situation weighting)
    disagreements = 0
    for i, best in claim_matches.items():
        if best is None or evals[i].verdict == Verdict.UNKNOWN:
            continue
        alt = match_claims(kb, q.text, eval_text.get(i, q.answers[i - 1]), [best.obj], use_context=False)
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

    # semantic check D (joint answer interpretation): mutually exclusive answers, exam elimination
    joint = _joint_answers(q, evals, n, "negative_question" in kinds)
    trace.append(("semantic_check_D", joint or "no joint inference"))

    # semantic check E: explicit counter-proofs from verified rules for options nothing matched directly
    proofs = []
    if not q.number_input:
        for i, e in evals.items():
            if e.verdict != Verdict.UNKNOWN or "ocr_unreadable" in e.flags or i > n:
                continue
            pf = prove_false(q.text, q.answers[i - 1], candidates, kb)
            if pf is not None:
                e.verdict, e.method, e.evidence = Verdict.FALSE, "prove_false", [pf.evidence]
                e.explanation, e.flags = pf.explanation, [*e.flags, pf.kind]
                proofs.append(f"{i}:{pf.kind}")
        # numeric condition model: a bare number judged only by verified facts whose conditions the question names
        for i, e in evals.items():
            if e.verdict != Verdict.UNKNOWN or i > n or "ocr_unreadable" in e.flags:
                continue
            a_txt = q.answers[i - 1]
            if not numbers(a_txt) or len({w for w in _core(a_txt) if not NUMBER_TOKEN.match(w)}) > 2:
                continue
            ok, fact = judge_number(q.text, a_txt, kb)
            if ok is not None and fact is not None:
                e.verdict = Verdict.TRUE if ok else Verdict.FALSE
                e.method, e.evidence = "numeric_model", [fact.source.split("#")[0]]
                e.explanation = f"Zahlenregel ({fact.quantity}, {fact.value:g} {fact.unit}) für diese Situation"
                e.flags = [*e.flags, "numeric_condition_model"]
                proofs.append(f"{i}:numeric")
    trace.append(("semantic_check_E", ", ".join(proofs) or "no counter-proof"))

    # exception + negation checks
    neg_q = "negative_question" in kinds
    exc = [i for i, e in evals.items() if "exception_risk" in e.flags or "absolute_quantifier" in e.flags]
    trace.append(("exception_check", f"risky answers={exc}"))
    trace.append(("negation_check", f"question asks for wrong/forbidden options={neg_q}"))

    ordered = [evals[i] for i in range(1, n + 1)]
    want = Verdict.FALSE if neg_q else Verdict.TRUE
    # a slot answer was read together with the question ('Wo ist das Halten unzulässig?' + 'Auf Bahnübergängen'),
    # so its verdict already carries the question's polarity - it must not be inverted a second time
    selected = tuple(e.index for e in ordered
                     if e.verdict == (Verdict.TRUE if "slot_answer" in e.flags else want))

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
    total = time.perf_counter() - t_start
    timings = {"retrieval_latency": retrieval_latency, "reasoning_latency": max(0.0, total - retrieval_latency)}
    return TheoryResult(selected, number_answer, ordered, round(conf, 4), uncertain, reasons, kinds, factors, trace,
                        timings)


_WHO_FIRST = re.compile(r"\bwer (hat|hätte|hatte)( \w+){0,6} (vorfahrt|vorrang)\b|"
                        r"\bwelche \w+ (hat|hätte) (den )?vorrang\b|\bwer (darf|fährt) (hier |jetzt )?zuerst\b",
                        re.IGNORECASE)


def _party(answer: str) -> set[str]:
    """The party an answer to 'Wer hat Vorrang?' names: 'Ich, weil ...' -> {ich}; 'Der Pkw von rechts' -> {pkw, rechts}."""
    head = re.split(r",|\bweil\b|\bda\b|\bdenn\b", answer, maxsplit=1)[0].strip().lower()
    if re.match(r"^ich\b", head):
        return {"ich"}
    return _core(head)


def _affirmative(text: str) -> bool:
    p = analyze(main_clause(text))
    return not p.negated and p.deontic in (Deontic.NONE, Deontic.OBLIGATORY, Deontic.PERMITTED)


def _joint_answers(q: TheoryQuestion, evals: dict[int, AnswerEval], n: int, negative: bool) -> str:
    """Answers are read together with each other, not only with the question:
    1. an answer whose action excludes the action of an answer already shown TRUE ('vor dem Andreaskreuz warten'
       vs 'schnell noch durchfahren') cannot be correct as well -> FALSE;
    2. 'Wer hat Vorfahrt?': only one party can have it - 'Ich ...' is FALSE when another party was shown to have it.
    No elimination ('the last undecided answer must be the correct one'): it turns a single hidden wrong FALSE
    verdict into a confident wrong selection (measured on the internal golden set)."""
    if q.number_input or n < 2 or any(i not in evals for i in range(1, n + 1)):
        return ""
    lex = load_lexicon()
    notes = []
    true_idx = [i for i, e in evals.items() if e.verdict == Verdict.TRUE and e.method in ("claim", "sign", "priority")
                and "excluded_by_answer" not in e.flags]
    if not negative:
        for j, e in evals.items():
            if e.verdict != Verdict.UNKNOWN:
                continue
            aj = q.answers[j - 1]
            acts_j = action_concepts(main_clause(aj))
            for i in true_idx:
                ai = q.answers[i - 1]
                acts_i = action_concepts(main_clause(ai))
                same_actor = actor(ai) == actor(aj) or None in (actor(ai), actor(aj))
                if (acts_i and acts_j and not acts_i & acts_j and same_actor and _affirmative(ai) and _affirmative(aj)
                        and any(lex.incompatible_with(x, y) for x in acts_i for y in acts_j)):
                    e.verdict, e.method, e.evidence = Verdict.FALSE, "joint", list(evals[i].evidence)
                    e.explanation = f"schließt Antwort {i} aus: {evals[i].explanation}"
                    e.flags.append("excluded_by_answer")
                    notes.append(f"{j} excluded by {i}")
                    break
        if _WHO_FIRST.search(q.text):
            for j, e in evals.items():
                pj = _party(q.answers[j - 1])
                if e.verdict != Verdict.UNKNOWN or not pj:
                    continue
                if any((pi := _party(q.answers[i - 1])) and not pi & pj for i in true_idx):
                    e.verdict, e.method = Verdict.FALSE, "joint"
                    e.explanation = "Vorrang kann nur eine Seite haben - eine andere Antwort ist belegt."
                    e.flags.append("excluded_by_answer")
                    notes.append(f"{j} excluded (one party has right of way)")
    return "; ".join(notes)


def _explain(m: _Match) -> str:
    o = m.obj
    src = o.sources[0]
    where = f"{src.law} {src.norm} {src.para or ''}".strip() if src.law else (src.ref or src.type)
    return f"{o.title}: {o.rule} [{where}]"
