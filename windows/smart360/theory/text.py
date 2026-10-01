"""German text normalisation for theory questions: case, umlauts, numbers/units, OCR noise, content words."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

# Very common German function words: ignored when comparing content. Negators and modal verbs are NOT in
# here - they carry meaning and are handled by the negation engine.
STOPWORDS = frozenset(
    """
    der die das den dem des ein eine einer eines einem einen und oder aber auch so wie als im in am an auf aus bei
    mit nach von vor zu zum zur über unter um durch für gegen ohne bis ich sie er es wir ihr man sich mich mir
    ist sind war wird werden wurde haben hat habe hatte sein ihre ihren seinem seiner seine dieser diese dieses
    diesem diesen jetzt dann da hier dort wenn weil dass ob was welche welcher welches wer wo wohin woran
    worauf wie viel viele beim vom ins zum einem einer eines sollten sollen würden würde ja schon noch nun nur_ etwa
    """.split()
)

OCR_FIXES = (
    (re.compile(r"\bkm\s*/\s*[nb]\b"), "km/h"),
    (re.compile(r"\bkmlh\b"), "km/h"),
    (re.compile(r"(?<=\d)\s*,\s*(?=\d)"), ","),
)

UNIT_ALIASES = {
    "kmh": "km/h", "km/std": "km/h", "stundenkilometer": "km/h", "meter": "m", "metern": "m", "metres": "m",
    "zentimeter": "cm", "millimeter": "mm", "promille": "‰", "sekunden": "s", "sekunde": "s", "kilogramm": "kg",
    "tonnen": "t", "tonne": "t", "jahre": "jahre", "jahren": "jahre", "jahr": "jahre", "prozent": "%",
    "minuten": "min", "minute": "min", "monaten": "monate", "monat": "monate", "monate": "monate",
    "tagen": "tage", "tag": "tage", "tage": "tage", "wochen": "wochen", "woche": "wochen",
    "stunden": "stunden", "stunde": "stunden", "punkten": "punkte", "punkt": "punkte", "kilometer": "km",
}
NUMBER_WORDS = {"ein": 1, "eine": 1, "einen": 1, "einer": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6,
                "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12, "fünfzehn": 15,
                "zwanzig": 20, "dreissig": 30, "vierzig": 40, "fünfzig": 50, "hundert": 100}
_UNIT_WORDS = r"(minuten?|stunden?|tagen?|tage|tag|wochen?|monaten?|monate|monat|jahren?|jahre|jahr|meter|metern|sekunden?|punkten?|punkte|kilometer)"
# durations are compared in one unit
_DURATION = {"wochen": (7.0, "tage"), "stunden": (60.0, "min")}


@lru_cache(maxsize=200_000)
def fold(text: str) -> str:
    """Lower case, unify quotes/dashes, keep umlauts (they distinguish words), collapse spaces."""
    t = unicodedata.normalize("NFC", text).lower()
    t = t.replace("ß", "ss").replace("–", "-").replace("—", "-").replace("„", '"').replace("“", '"')
    for rx, repl in OCR_FIXES:
        t = rx.sub(repl, t)
    return re.sub(r"\s+", " ", t).strip()


def ascii_fold(text: str) -> str:
    """For fuzzy matching of OCR text where umlauts may be lost: ä->a etc."""
    return fold(text).translate(str.maketrans("äöü", "aou"))


_NUM = re.compile(r"(\d+(?:[.,]\d+)?)\s*(km/h|km|‰|%|mm|cm|m|kg|t|s|jahre|monate|min|tage|wochen|stunden|ng/ml|punkte)?(?![a-zäöü])")


def numbers(text: str) -> list[tuple[float, str]]:
    """[(value, unit)] - German decimal comma, unit aliases ("Meter" -> m)."""
    return list(_numbers(text))


@lru_cache(maxsize=100_000)
def _numbers(text: str) -> tuple[tuple[float, str], ...]:
    t = fold(text)
    t = re.sub(rf"\b({'|'.join(NUMBER_WORDS)})\s+{_UNIT_WORDS}\b",
               lambda m: f"{NUMBER_WORDS[m.group(1)]} {m.group(2)}", t)
    for alias, unit in sorted(UNIT_ALIASES.items(), key=lambda x: -len(x[0])):
        t = re.sub(rf"(?<=\d)\s*{re.escape(alias)}\b", f" {unit}", t)
    out = []
    for m in _NUM.finditer(t):
        raw = m.group(1).replace(".", "").replace(",", ".") if re.match(r"^\d{1,3}(\.\d{3})+$", m.group(1)) \
            else m.group(1).replace(",", ".")
        try:
            v, u = float(raw), m.group(2) or ""
        except ValueError:
            continue
        if u in _DURATION:
            f, u = _DURATION[u]
            v *= f
        out.append((v, u))
    return tuple(out)


_STEM_SUFFIXES = ("ungen", "ung", "en", "er", "es", "em", "e", "n", "s")


@lru_cache(maxsize=50_000)
def stem(word: str) -> str:
    """Tiny German stemmer: enough to match 'Radfahrer'/'Radfahrern', 'überholen'/'überholt'."""
    w = word
    if len(w) > 5 and w.endswith("t") and not w.endswith("st"):
        w = w[:-1]
    for suf in _STEM_SUFFIXES:
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def canon(text: str) -> str:
    """Folded text after semantic normalisation (knowledge/semantics/lexicon.json)."""
    from smart360.theory.semantics import canonicalize

    return canonicalize(text).text


def words(text: str) -> list[str]:
    return re.findall(r"[a-zäöü0-9/‰%]+", canon(text))


_UMLAUT = str.maketrans("äöü", "aou")
UMLAUT_FOLD = _UMLAUT


def content(text: str, keep: frozenset[str] = frozenset()) -> set[str]:
    """Stemmed content words (stop words removed; negators/modals kept - they matter). Umlauts are folded
    after stemming so that inflected forms meet ('einfährt' / 'einfahren' -> 'einfahr')."""
    return {stem(w).translate(_UMLAUT) for w in words(text) if (w not in STOPWORDS or w in keep) and len(w) > 1}


NUMBER_TOKEN = re.compile(r"^(\d+([.,]\d+)?|km/h|km|m|cm|mm|kg|t|s|‰|%|jahre|monate|minuten)$")

# --------------------------------------------------------------------------- OCR repair of polarity words
# Only words that flip or qualify meaning, and only with typical OCR confusions - a general spell checker would
# invent meaning. 'kcin' -> 'kein', 'nlcht' -> 'nicht', 'rnuss' -> 'muss'.
POLARITY_LEXICON = ("nicht", "kein", "keine", "keinen", "keiner", "keinem", "keines", "nie", "niemals", "darf",
                    "dürfen", "muss", "müssen", "verboten", "erlaubt", "immer", "ausnahme", "ausnahmen", "unzulässig",
                    "zulässig", "solange", "wenn", "falls", "sofern", "sobald", "während", "bevor", "nachdem")
_OCR_EQUIV = [("rn", "m"), ("c", "e"), ("l", "i"), ("I", "i"), ("1", "i"), ("|", "i"), ("0", "o"), ("u", "ü"),
              ("a", "ä"), ("o", "ö"), ("ii", "ü"), ("l", "I")]


def _ocr_variants(word: str) -> set[str]:
    out = {word}
    for a, b in _OCR_EQUIV:
        for x, y in ((a, b), (b, a)):
            i = word.find(x)
            while i != -1:
                out.add(word[:i] + y + word[i + len(x):])
                i = word.find(x, i + 1)
    return out


_POLARITY_BY_VARIANT: dict[str, str] = {}
for _w in POLARITY_LEXICON:
    for _v in _ocr_variants(_w):
        _POLARITY_BY_VARIANT.setdefault(_v, _w)
for _w in POLARITY_LEXICON:  # real words always map to themselves
    _POLARITY_BY_VARIANT[_w] = _w


def ocr_repair(text: str) -> tuple[str, int]:
    """Repair OCR-damaged polarity words (one typical confusion). Returns (text, number of repairs)."""
    n = 0

    def fix(m: re.Match[str]) -> str:
        nonlocal n
        w = m.group(0)
        low = w.lower()
        rep = _POLARITY_BY_VARIANT.get(low)
        if rep is None or rep == low:
            return w
        n += 1
        return rep if w[:1].islower() else rep.capitalize()

    return re.sub(r"[A-Za-zÄÖÜäöüß|01]+", fix, text), n


def cosine(a: set[str], b: set[str]) -> float:
    """Set cosine: penalises words of either side that the other side lacks (situation matching)."""
    if not a or not b:
        return 0.0
    return len(a & b) / (len(a) * len(b)) ** 0.5


def similarity(a: set[str], b: set[str]) -> float:
    """Overlap coefficient weighted towards the smaller set (answers are short)."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / min(len(a), len(b)) * (0.6 + 0.4 * inter / max(len(a), len(b)))


# --------------------------------------------------------------------------- OCR repair against the domain vocabulary
_SINGLE_EQUIV = [(a, b) for a, b in _OCR_EQUIV] + [(b, a) for a, b in _OCR_EQUIV]


def _neighbours(word: str) -> set[str]:
    out = set()
    for x, y in _SINGLE_EQUIV:
        i = word.find(x)
        while i != -1:
            out.add(word[:i] + y + word[i + len(x):])
            i = word.find(x, i + 1)
    return out


def vocab_repair(text: str, vocab: frozenset[str]) -> tuple[str, int, list[str]]:
    """Repair OCR-damaged words that are 1-2 typical confusions away from a known domain word
    ('Fcldweg' -> 'Feldweg', 'vcrbotcn' -> 'verboten'). Returns (text, repairs, words still unknown)."""
    fixed = 0
    unknown: list[str] = []

    def fix(m: re.Match[str]) -> str:
        nonlocal fixed
        w = m.group(0)
        low = w.lower()
        if len(low) < 4 or low in vocab or low.replace("ß", "ss") in vocab:
            return w
        one = _neighbours(low)
        hit = next((c for c in one if c in vocab), None)
        if hit is None and len(low) >= 6:
            hit = next((c2 for c in one for c2 in _neighbours(c) if c2 in vocab), None)
        if hit is None:
            unknown.append(w)
            return w
        fixed += 1
        return hit if w[:1].islower() else hit[:1].upper() + hit[1:]

    return re.sub(r"[A-Za-zÄÖÜäöüß|]+", fix, text), fixed, unknown
