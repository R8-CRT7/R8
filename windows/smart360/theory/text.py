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
    "tonnen": "t", "tonne": "t", "jahre": "jahre", "jahren": "jahre", "prozent": "%",
}


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


_NUM = re.compile(r"(\d+(?:[.,]\d+)?)\s*(km/h|‰|%|mm|cm|m|kg|t|s|jahre|ng/ml|punkte?)?(?![a-zäöü])")


def numbers(text: str) -> list[tuple[float, str]]:
    """[(value, unit)] - German decimal comma, unit aliases ("Meter" -> m)."""
    t = fold(text)
    for alias, unit in UNIT_ALIASES.items():
        t = re.sub(rf"(?<=\d)\s*{re.escape(alias)}\b", f" {unit}", t)
    out = []
    for m in _NUM.finditer(t):
        raw = m.group(1).replace(".", "").replace(",", ".") if re.match(r"^\d{1,3}(\.\d{3})+$", m.group(1)) \
            else m.group(1).replace(",", ".")
        try:
            out.append((float(raw), m.group(2) or ""))
        except ValueError:
            continue
    return out


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


# Synonyms used in exam questions -> one canonical token (applied before tokenising)
SYNONYMS: tuple[tuple[re.Pattern[str], str], ...] = tuple((re.compile(p), r) for p, r in (
    (r"\baußerhalb geschlossener ortschaften?\b|\bausserhalb geschlossener ortschaften?\b|\baußerorts\b|\bausserorts\b", "außerorts"),
    (r"\binnerhalb geschlossener ortschaften?\b|\binnerorts\b", "innerorts"),
    (r"\bzebrastreifens?\b|\bfußgängerüberwege?n?s?\b|\bfussgängerüberwege?n?s?\b|\bzeichen 293\b", "fußgängerüberweg"),
    (r"\bpersonenkraftwagens?\b|\bpkws?\b", "pkw"),
    (r"\blastkraftwagens?\b|\blkws?\b", "lkw"),
    (r"\bmotorrad\w*|\bkrafträder\w*|\bkraftrad\w*", "kraftrad"),
    (r"\bampel\w*|\blichtzeichenanlage\w*|\blichtzeichen\b", "ampel"),
    (r"\bstoppschild\w*|\bstop-schild\w*|\bzeichen 206\b", "stoppschild"),
    (r"\bhandys?\b|\bmobiltelefon\w*|\bsmartphones?\b", "handy"),
    (r"\bblinker[ns]?\b|\bfahrtrichtungsanzeiger[ns]?\b", "blinker"),
    (r"\bmartinshorn\b|\beinsatzhorn\b", "einsatzhorn"),
    (r"\bblaulicht\b|\bblaue[sm]? blinklicht\b", "blaulicht"),
    (r"\bwarnblinker\b|\bwarnblinkanlage\b|\bwarnblinklicht\b", "warnblinklicht"),
    (r"\btüv\b|\bhauptuntersuchung\w*", "hauptuntersuchung"),
    (r"\bwohnwagen\w*|\bwohnanhänger\w*", "wohnanhänger"),
    (r"\bspielstraße\w*|\bverkehrsberuhigte[nmr]? bereich\w*", "verkehrsberuhigt"),
    (r"\btempo[- ]?30[- ]zone\w*", "tempo30zone"),
))


def canon(text: str) -> str:
    t = fold(text)
    for rx, repl in SYNONYMS:
        t = rx.sub(repl, t)
    return t


def words(text: str) -> list[str]:
    return re.findall(r"[a-zäöü0-9/‰%]+", canon(text))


_UMLAUT = str.maketrans("äöü", "aou")


def content(text: str, keep: frozenset[str] = frozenset()) -> set[str]:
    """Stemmed content words (stop words removed; negators/modals kept - they matter). Umlauts are folded
    after stemming so that inflected forms meet ('einfährt' / 'einfahren' -> 'einfahr')."""
    return {stem(w).translate(_UMLAUT) for w in words(text) if (w not in STOPWORDS or w in keep) and len(w) > 1}


NUMBER_TOKEN = re.compile(r"^(\d+([.,]\d+)?|km/h|m|cm|mm|kg|t|s|‰|%|jahre|monate|minuten)$")


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
