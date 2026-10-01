"""Semantic normalisation layer for driving-school German.

1. canonicalize(): rewrites phrases into canonical words / concept tokens using knowledge/semantics/lexicon.json.
   Every entry has canonical_concept, valid_context, invalid_context and confidence - no free synonymy.
   Negators inside a matched phrase are consumed ('andere dürfen nicht gefährdet werden' -> NO_ENDANGERMENT),
   so the negation engine never sees them twice.
2. question_intent(): REQUIRED_ACTION, PERMISSION, PROHIBITION, PRIORITY, SPEED, DISTANCE, ...
3. conditions(): structured situation (vehicle, trailer, road context, weather/visibility, actor, age, ...)
4. resolve_answer(): short answers to W-questions are turned into a proposition together with the question
   ('Wer muss warten?' + 'Ich' -> 'Ich muss warten').
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from smart360.theory.text import fold

TOKEN = re.compile(r"\bc[a-z]+x\b")


@dataclass(frozen=True)
class LexEntry:
    id: str
    concept: str
    rewrite: str
    patterns: tuple[re.Pattern[str], ...]
    valid_context: tuple[str, ...]
    invalid_context: tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class Lexicon:
    entries: tuple[LexEntry, ...]
    token_concept: dict[str, str]
    incompatible: frozenset[frozenset[str]]
    exclusive: tuple[tuple[str, tuple[tuple[str, tuple[re.Pattern[str], ...]], ...]], ...] = ()
    opposites: tuple[tuple[tuple[str, str], ...], ...] = ()

    @property
    def action_concepts(self) -> frozenset[str]:
        return frozenset(e.concept for e in self.entries if e.id.startswith("act_"))

    def concepts_of(self, canonical_text: str) -> set[str]:
        return {self.token_concept[t] for t in TOKEN.findall(canonical_text) if t in self.token_concept}

    def incompatible_with(self, a: str, b: str) -> bool:
        return frozenset((a, b)) in self.incompatible


def _wrap(p: str) -> str:
    left = "" if p.startswith("\\b") or p.startswith("(?<") else r"(?<![a-zäöüß0-9])"
    right = "" if p.endswith("\\b") or (p.endswith(")?") and False) else r"(?![a-zäöüß0-9])"
    return left + p + right


@lru_cache(maxsize=4)
def load_lexicon(path: str | None = None) -> Lexicon:
    from smart360.theory.kb import knowledge_dir

    p = Path(path) if path else knowledge_dir() / "semantics" / "lexicon.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    entries = []
    tok: dict[str, str] = {}
    for e in data["entries"]:
        pats = tuple(re.compile(_wrap(fold(x))) for x in e["patterns"])
        entries.append(LexEntry(e["id"], e["canonical_concept"], fold(e["rewrite"]), pats,
                                tuple(fold(x) for x in e.get("valid_context", [])),
                                tuple(fold(x) for x in e.get("invalid_context", [])), float(e["confidence"])))
        for t in TOKEN.findall(fold(e["rewrite"])):
            tok[t] = e["canonical_concept"]
    inc = frozenset(frozenset(pair) for pair in data.get("incompatible", []))
    excl = tuple((g["group"], tuple((name, tuple(re.compile(_wrap(fold(x))) for x in pats))
                                    for name, pats in g["members"].items()))
                 for g in data.get("exclusive", []))
    opp = tuple(tuple((fold(x), fold(y)) for x, y in o["pairs"]) for o in data.get("opposites", []))
    return Lexicon(tuple(entries), tok, inc, excl, opp)


@dataclass(frozen=True)
class Canon:
    text: str
    concepts: frozenset[str]
    min_confidence: float
    applied: tuple[str, ...]


_NEGATOR = re.compile(r"(?<![a-zäöüß])(nicht|kein\w*|nie|niemals|keinesfalls|nichts)(?![a-zäöüß])")


def _protected(m: re.Match[str], e: LexEntry, rx: re.Pattern[str]) -> str:
    """A wildcard gap in a pattern must never swallow a negator: for an action the negation is kept in front of the
    concept ('lasse NICHT den Gegenverkehr vorbei' -> 'nicht cyieldx'), any other phrase stays as written."""
    if _NEGATOR.search(m.group(0)) and not _NEGATOR.search(rx.pattern):
        if e.id.startswith("act_") and len(_NEGATOR.findall(m.group(0))) == 1:
            return "nicht " + e.rewrite
        return m.group(0)
    return m.expand(e.rewrite) if "\\" in e.rewrite else e.rewrite


@lru_cache(maxsize=100_000)
def canonicalize(text: str, context: str = "") -> Canon:
    lex = load_lexicon()
    t = fold(text)
    ctx = t + " " + fold(context)
    applied: list[str] = []
    conf = 1.0
    for e in lex.entries:
        if e.valid_context and not any(v in ctx for v in e.valid_context):
            continue
        if e.invalid_context and any(v in ctx for v in e.invalid_context):
            continue
        new = t
        for rx in e.patterns:
            new = rx.sub(lambda m, e=e, rx=rx: _protected(m, e, rx), new)
        if new != t:
            applied.append(e.id)
            conf = min(conf, e.confidence)
            t = new
    t = re.sub(r"\s+", " ", t).strip()
    return Canon(t, frozenset(lex.concepts_of(t)), conf, tuple(applied))


def action_concepts(text: str, context: str = "") -> set[str]:
    return set(canonicalize(text, context).concepts) & load_lexicon().action_concepts


def actor(text: str) -> str | None:
    """Who does the action in a (main) clause: 'self' (ich / formal Sie as subject) or 'other' (der Pkw …)."""
    t = canonicalize(text).text
    if re.search(r"\b(ich|mich|mir|mein\w*)\b", t):
        return "self"
    if re.match(r"^(sie|wir) (müssen|muss|dürfen|darf|sollten|können|lassen|fahren|halten|warten|biegen)\b", t):
        return "self"
    if re.match(r"^(der|die|das|ein|eine|einen)\s+\w+", t) and not re.match(r"^(die|der|das) (ampel|geschwindigkeit|vorfahrt|regel|\w+ung)\b", t):
        return "other"
    return None


_PREC_CLAIM = (re.compile(r"(?:^|\b)([a-zäöüß]+)\s+(?:gehen|geht)\s+(.+?)\s+vor\b"),
               re.compile(r"([a-zäöüß]+)\s+(?:hat|haben)\s+(?:den\s+|immer\s+)?vorrang\s+vor\s+(.+)"))
_PREC_WINNER = re.compile(r"^(?:die|der|das)?\s*([a-zäöüß]+)\s+(?:hat|haben|geht|gehen)\s+(?:den\s+)?vorrang\b|^(?:die|der|das)?\s*([a-zäöüß]+)\s+(?:geht|gehen)\s+vor\b")


def precedence(claim: str, answer: str) -> bool | None:
    """'Lichtzeichen gehen Vorfahrtsschildern vor' vs 'Das Vorfahrtsschild hat Vorrang' -> False.
    None when the claim/answer is no precedence statement or the entities do not match."""
    from smart360.theory.text import content

    c = canonicalize(claim).text
    a = canonicalize(answer).text
    first = second = None
    for rx in _PREC_CLAIM:
        m = rx.search(c)
        if m:
            first, second = content(m.group(1)), content(m.group(2))
            break
    w = _PREC_WINNER.search(a)
    if not first or not w:
        return None
    win = content(w.group(1) or w.group(2))
    if win & first:
        return True
    if win & (second or set()):
        return False
    return None


_SIGN_NO = re.compile(r"\bzeichen\s+(\d{3,4}(?:[.-]\d{1,2})?(?:\s*(?:,|/|und|oder|bis)\s*\d{3,4}(?:[.-]\d{1,2})?)*)\b")
_NO = re.compile(r"\d{3,4}(?:[.-]\d{1,2})?")


@lru_cache(maxsize=100_000)
def situations(text: str) -> dict[str, frozenset[str]]:
    """Mutually exclusive situation members named in a text: police gesture (arm up / arms across), light colour,
    halt-ban type, sign number. {'POLICE_GESTURE': {'ARMS_ACROSS'}, 'SIGN': {'286'}}"""
    t = fold(text)
    out: dict[str, frozenset[str]] = {}
    for group, members in load_lexicon().exclusive:
        hit = frozenset(name for name, pats in members if any(p.search(t) for p in pats))
        if hit:
            out[group] = hit
    signs = frozenset(n for m in _SIGN_NO.finditer(t) for n in _NO.findall(m.group(1)))
    if signs:
        out["SIGN"] = signs
    return out


def situation_conflict(question: str, claim: str, answer: str = "") -> str | None:
    """The claim is about a different member of an exclusive situation than the question ('Arm hoch' claim for an
    'Arme quer' question, 'Zeichen 283' claim for a 'Zeichen 286' question). An answer that names its own situation
    ('Gelb bedeutet ...') overrides the question for that group. Returns the group or None."""
    q = {**situations(question), **situations(answer)} if answer else situations(question)
    c = situations(claim)
    for group, members in c.items():
        if group in q and not members & q[group]:
            return group
    return None


def _sides(text: str) -> list[tuple[bool, bool]]:
    words = set(re.findall(r"[a-zäöüß]+", fold(text)))
    return [(any(x in words for x, _ in pairs), any(y in words for _, y in pairs))
            for pairs in load_lexicon().opposites]


def opposite_conflict(a: str, b: str) -> bool:
    """One text says 'rechts' where the other says 'links' (and neither names both sides)."""
    for (ax, ay), (bx, by) in zip(_sides(a), _sides(b), strict=True):
        one_side_a, one_side_b = ax != ay, bx != by
        if one_side_a and one_side_b and ax != bx:
            return True
    return False


def flip_opposites(text: str) -> str:
    """'links' <-> 'rechts': compare an answer with a claim about the opposite side."""
    swap = {w: v for pairs in load_lexicon().opposites for x, y in pairs for w, v in ((x, y), (y, x))}
    return re.sub(r"[a-zäöüß]+", lambda m: swap.get(m.group(0), m.group(0)), fold(text))


# ----------------------------------------------------------------------------- word formation
_LINKERS = ("", "s", "es", "n", "en", "e")
_PARTICLES = frozenset("ab an auf aus ein zurück weiter vorbei fest los um mit nach heran hinaus vor zu".split())
_NOT_VERB = frozenset("der die das den dem des ein eine einen einem einer nicht kein keine noch schon dann "
                      "auch nur bitte sofort ich sie er es wir man mich sich".split())


@lru_cache(maxsize=1)
def _vocab() -> frozenset[str]:
    """Stems of the knowledge base (rules, claims, signs) - the parts a compound may be split into."""
    from smart360.theory.kb import get_kb
    from smart360.theory.text import content

    kb = get_kb()
    parts: list[str] = []
    for o in kb.objects.values():
        parts += [o.title, o.rule, *o.keywords, *(" ".join(c.context) + " " + c.statement for c in o.claims)]
    for sg in kb.signs.values():
        parts += [sg.name, sg.meaning, *sg.keywords]
    return frozenset(w for w in content(" ".join(parts)) if len(w) >= 4)


@lru_cache(maxsize=50_000)
def split_compound(stem_word: str) -> tuple[str, ...]:
    """'grundstucksausfahr' -> ('grundstuck', 'ausfahr') when both parts are knowledge-base stems
    (linking -s/-es/-n/-en/-e allowed). Unknown parts -> no split (no free decomposition)."""
    from smart360.theory.text import stem

    v = _vocab()
    if len(stem_word) < 8 or not stem_word.isalpha():
        return ()
    for i in range(len(stem_word) - 4, 3, -1):  # longest head first
        left, right = stem_word[:i], stem_word[i:]
        if right not in v and stem(right) not in v:
            continue
        for link in _LINKERS:
            if link and not left.endswith(link):
                continue
            head = left[: len(left) - len(link)] if link else left
            if len(head) >= 4 and (head in v or stem(head) in v):
                return (head if head in v else stem(head), right if right in v else stem(right))
    return ()


def separable_verbs(text: str) -> set[str]:
    """'Sie schleppen ein Fahrzeug ab' -> {'abschleppen'}: German separable verbs put the particle at the end
    of the clause; the finite verb is the first lower-case word after the subject."""
    out = set()
    for clause in re.split(r"[.,;:?!]", text):
        toks = clause.split()
        if len(toks) < 3 or toks[-1].lower() not in _PARTICLES:
            continue
        for t in toks[1:-1]:
            if t[:1].islower() and t.lower() not in _NOT_VERB and t.isalpha():
                out.add(toks[-1].lower() + t.lower())
                break
    return out


# ----------------------------------------------------------------------------- intents
INTENTS = (
    ("PROHIBITION", r"\b(verboten|untersagt|unzulässig|nicht erlaubt|nicht zulässig|nicht gestattet)\b|\bwas (dürfen|darf) sie (hier )?nicht\b"),
    ("FALSE_STATEMENT", r"\b(falsch|trifft nicht zu|nicht richtig|nicht korrekt)\b"),
    ("PRIORITY", r"\bwer (hat|muss|darf) (zuerst|vorfahrt|vorrang|warten)|\bwer (fährt|darf) zuerst\b|\bvorrang\b.*\?|\bvorfahrt\b.*\?"),
    ("PERMISSION", r"^(darf|dürfen)\b|\bwann (darf|dürfen)\b|\bist (das|es) erlaubt\b|\berlaubt\?"),
    ("REQUIRED_ACTION", r"\bwie (verhalten|müssen) sie\b|\bwas (müssen|tun|machen) sie\b|\bwas ist (zu tun|pflicht)\b|^(muss|müssen)\b|\bwie (reagieren|handeln)\b|\bpflicht\b"),
    ("SPEED", r"\bwie schnell\b|\bgeschwindigkeit\b.*\?|\bkm/h\b.*\?|\btempo\b"),
    ("DISTANCE", r"\bwie (weit|groß|viel) (vor|hinter|abstand)|\babstand\b|\bwie weit\b|\bentfernung\b|\bmeter\b.*\?"),
    ("DURATION", r"\bwie lange\b|\bab wann\b|\bwie oft\b|\bmonate\b"),
    ("MEANING", r"\bwas (bedeutet|zeigt|besagt)\b|\bbedeutung\b"),
    ("CAUSE", r"\bwarum\b|\bwodurch\b|\bworan liegt\b"),
    ("CONSEQUENCE", r"\bwas (kann|könnte) passieren\b|\bfolge[n]?\b|\bwie (ändert|verändert) sich\b"),
    ("RISK", r"\bgefahr\b|\brisiko\b|\bwomit müssen sie rechnen\b"),
    ("EXPECTATION", r"\bwomit (müssen|sollten) sie rechnen\b|\bwas (ist|wäre) zu erwarten\b"),
    ("PARKING", r"\bparken\b|\bhalten\b"),
    ("OVERTAKING", r"\büberhol"),
    ("EMERGENCY", r"\bunfall\b|\bpanne\b|\bliegenbleib|\berste hilfe\b"),
    ("VEHICLE_TECH", r"\breifen\b|\bbeleuchtung\b|\blicht\b|\bbremse\b|\bladung\b|\bhauptuntersuchung\b"),
    ("ENVIRONMENT", r"\bumwelt\b|\bsparsam\b|\babgas\b|\blärm\b"),
    ("MANOEUVRE", r"\babbieg|\bwenden\b|\brückwärts\b|\beinfädel|\bfahrstreifen"),
)


def question_intent(question: str) -> list[str]:
    t = fold(question)
    return [name for name, rx in INTENTS if re.search(rx, t)]


# ----------------------------------------------------------------------------- conditions
@dataclass
class Conditions:
    vehicle: set[str] = field(default_factory=set)  # pkw, lkw, kraftrad, fahrrad, mofa, bus, escooter
    trailer: bool | None = None
    road_context: str | None = None  # innerorts | außerorts | autobahn
    weather: set[str] = field(default_factory=set)  # nebel, regen, schneefall, glätte
    visibility_m: float | None = None
    actor: str | None = None  # ich | other
    age_years: float | None = None
    height_cm: float | None = None
    mass_kg: list[float] = field(default_factory=list)
    traffic_state: set[str] = field(default_factory=set)  # stau, stockt
    excluded: set[str] = field(default_factory=set)  # 'ohne X'
    negated_question: bool = False


def conditions(text: str) -> Conditions:
    from smart360.theory.text import numbers

    t = canonicalize(text).text
    c = Conditions()
    for v, rx in (("pkw", r"\bpkw\b"), ("lkw", r"\blkw\b"), ("kraftrad", r"\bkraftrad\b"), ("fahrrad", r"\bfahrrad|\bradfahrer"),
                  ("mofa", r"\bmofa"), ("bus", r"\b(bus|kraftomnibus|linienbus|schulbus)"), ("escooter", r"e-scooter|elektrokleinst")):
        if re.search(rx, t):
            c.vehicle.add(v)
    if re.search(r"\b(ohne|kein\w*) (\w+ )?anhänger", t):
        c.trailer = False
        c.excluded.add("anhänger")
    elif re.search(r"anhänger|wohnanhänger|\bzug anhänger\b", t):
        c.trailer = True
    if "autobahn" in t:
        c.road_context = "autobahn"
    elif "ausserorts" in t:
        c.road_context = "außerorts"
    elif "innerorts" in t:
        c.road_context = "innerorts"
    for w in ("nebel", "regen", "schneefall", "glätte", "glatteis", "schneeglätte", "dunkelheit", "schneematsch"):
        if w in t:
            c.weather.add(w)
    m = re.search(r"(sicht(weite)?|sehen)[^.?]{0,40}?(\d+)\s*(m|meter)\b|(\d+)\s*(m|meter)\s*(weit )?(sicht|sehen)", t)
    if m:
        c.visibility_m = float(m.group(3) or m.group(5))
    m = re.search(r"(\d+)[- ]?(jährig|jahre alt)", t)
    if m:
        c.age_years = float(m.group(1))
    for v, u in numbers(text):
        if u == "cm":
            c.height_cm = v
        if u in ("kg", "t"):
            c.mass_kg.append(v * 1000 if u == "t" else v)
    for w in ("stau", "stockt", "staut"):
        if w in t:
            c.traffic_state.add("stau")
    for m2 in re.finditer(r"\b(ohne|kein\w*)\s+(\w+)", t):
        c.excluded.add(m2.group(2))
    return c


# ----------------------------------------------------------------------------- answer roles
_WH_SUBJECT = re.compile(r"^(wer)\s+(.*?)\??$")
_WH_WHICH = re.compile(r"^welche[rs]?\s+(\w+\s+)?(.*?)\??$")
_WH_SIDE = re.compile(r"^auf welcher seite\s+(.*?)\??$")
_WH_WHERE = re.compile(r"^wo\s+(.*?)\??$")
_WH_WHEN = re.compile(r"^(wann|ab wann|unter welche[rn]? (bedingung|voraussetzung)(en)?)\s+(.*?)\??$")


def _last_question_sentence(question: str) -> tuple[str, str]:
    parts = re.split(r"(?<=[.!])\s+", question.strip())
    q = parts[-1] if parts else question
    return " ".join(parts[:-1]), q


def resolve_answer(question: str, answer: str) -> str | None:
    """Short answer to a W-question -> full proposition, or None if not applicable.

    'Wer hat Vorfahrt?' + 'Der Pkw von rechts'        -> 'Der Pkw von rechts hat Vorfahrt'
    'Wer muss warten?' + 'Ich'                         -> 'Ich muss warten'
    'Auf welcher Seite überholen Sie?' + 'Rechts'      -> 'Sie überholen rechts'
    'Wo muss es fahren?' + 'Auf dem Gehweg'            -> 'es muss fahren auf dem Gehweg'
    'Welche gelten?' + 'Die gelben'                    -> 'Die gelben gelten'
    """
    a = answer.strip().rstrip(".")
    if len(a.split()) > 7 or re.match(r"(?i)^(ja|nein)\b", a):
        return None
    _, last = _last_question_sentence(question)
    tl = last.strip().lower()
    for rx, build in (
        (_WH_SUBJECT, lambda m: f"{a} {m.group(2)}"),
        (_WH_SIDE, lambda m: f"{m.group(1)} {a}"),
        (_WH_WHERE, lambda m: f"{m.group(1)} {a}"),
        (_WH_WHEN, lambda m: f"{m.group(4)} {a}"),
        (_WH_WHICH, lambda m: f"{a} {m.group(2)}"),
    ):
        m = rx.match(tl)
        if m:
            out = re.sub(r":.*$", "", build(m)) if ":" in tl else build(m)
            out = re.sub(r"\bsie\b", "ich", out)
            out = re.sub(r"\bihr(e[nmrs]?)?\b", lambda mm: "mein" + (mm.group(1) or ""), out)
            return re.sub(r"\s+", " ", out).strip()
    return None
