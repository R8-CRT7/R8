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
    worauf wie viel viele einem einer eines sollten sollen würden würde ja schon noch nun nur_ etwa
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


def words(text: str) -> list[str]:
    return re.findall(r"[a-zäöü0-9/‰%]+", fold(text))


def content(text: str, keep: frozenset[str] = frozenset()) -> set[str]:
    """Stemmed content words (stop words removed; negators/modals kept - they matter)."""
    return {stem(w) for w in words(text) if (w not in STOPWORDS or w in keep) and len(w) > 1}


def similarity(a: set[str], b: set[str]) -> float:
    """Overlap coefficient weighted towards the smaller set (answers are short)."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / min(len(a), len(b)) * (0.6 + 0.4 * inter / max(len(a), len(b)))
