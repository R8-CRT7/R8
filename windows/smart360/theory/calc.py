"""Deterministic calculation engine - arithmetic is never left to the language model.

Every formula is registered with inputs, the formula text, the rounding rule and its source. The classic
'Faustformeln' (reaction/braking distance, half speedometer) are NOT law: they are the rules of thumb taught in
German driving schools and used in the official theory questions (source type `rule_of_thumb`, priority 5).
Legal limits (masses, speeds, distances) live in knowledge/numeric_rules.json with verbatim law evidence."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Formula:
    id: str
    name: str
    inputs: tuple[str, ...]
    formula: str
    unit: str
    rounding: str
    source_type: str
    source: str
    fn: Callable[..., float]


@dataclass(frozen=True)
class CalcResult:
    formula_id: str
    value: float
    unit: str
    inputs: dict[str, float]
    steps: tuple[str, ...] = field(default_factory=tuple)

    def matches(self, value: float, unit: str = "", tol: float = 0.051) -> bool:
        if unit and self.unit and _norm_unit(unit) != _norm_unit(self.unit):
            return False
        return math.isclose(value, self.value, abs_tol=tol, rel_tol=1e-6)


def _norm_unit(u: str) -> str:
    return {"meter": "m", "metern": "m", "kmh": "km/h"}.get(u.lower().strip(), u.lower().strip())


RULE_OF_THUMB = "Faustformel der Fahrschulausbildung / amtliche Theoriefragen (kein Gesetzestext)"

FORMULAS: dict[str, Formula] = {}


def _register(f: Formula) -> Formula:
    FORMULAS[f.id] = f
    return f


_register(Formula(
    "reaction_distance", "Reaktionsweg (1 s Reaktionszeit)", ("v_kmh",), "(v / 10) * 3", "m",
    "exakt, keine Rundung (Prüfungsantworten sind exakte Werte)", "rule_of_thumb", RULE_OF_THUMB,
    lambda v_kmh: v_kmh / 10 * 3))
_register(Formula(
    "braking_distance", "Bremsweg (normale Bremsung)", ("v_kmh",), "(v / 10)²", "m",
    "exakt", "rule_of_thumb", RULE_OF_THUMB, lambda v_kmh: (v_kmh / 10) ** 2))
_register(Formula(
    "emergency_braking_distance", "Bremsweg bei Gefahrbremsung", ("v_kmh",), "(v / 10)² / 2", "m",
    "exakt", "rule_of_thumb", RULE_OF_THUMB, lambda v_kmh: (v_kmh / 10) ** 2 / 2))
_register(Formula(
    "stopping_distance", "Anhalteweg (Reaktionsweg + Bremsweg)", ("v_kmh",), "(v/10)*3 + (v/10)²", "m",
    "exakt", "rule_of_thumb", RULE_OF_THUMB, lambda v_kmh: v_kmh / 10 * 3 + (v_kmh / 10) ** 2))
_register(Formula(
    "emergency_stopping_distance", "Anhalteweg bei Gefahrbremsung", ("v_kmh",), "(v/10)*3 + (v/10)²/2", "m",
    "exakt", "rule_of_thumb", RULE_OF_THUMB, lambda v_kmh: v_kmh / 10 * 3 + (v_kmh / 10) ** 2 / 2))
_register(Formula(
    "safe_distance_half_speedometer", "Sicherheitsabstand außerorts ('halber Tacho')", ("v_kmh",), "v / 2", "m",
    "exakt", "rule_of_thumb", RULE_OF_THUMB, lambda v_kmh: v_kmh / 2))
_register(Formula(
    "two_second_distance", "Abstand in 2 Sekunden", ("v_kmh",), "v / 3,6 * 2", "m",
    "auf 1 Nachkommastelle", "rule_of_thumb", "Zwei-Sekunden-Regel (Fahrschulausbildung)",
    lambda v_kmh: round(v_kmh / 3.6 * 2, 1)))
_register(Formula(
    "distance_per_second", "Weg pro Sekunde", ("v_kmh",), "v / 3,6", "m",
    "auf 1 Nachkommastelle", "rule_of_thumb", "Physik: 1 m/s = 3,6 km/h", lambda v_kmh: round(v_kmh / 3.6, 1)))
_register(Formula(
    "distance_in_time", "Weg in t Sekunden", ("v_kmh", "t_s"), "v / 3,6 * t", "m",
    "auf 1 Nachkommastelle", "rule_of_thumb", "Physik: s = v · t", lambda v_kmh, t_s: round(v_kmh / 3.6 * t_s, 1)))
_register(Formula(
    "braking_distance_factor", "Faktor des Bremswegs bei k-facher Geschwindigkeit", ("k",), "k²", "×",
    "exakt", "rule_of_thumb", "Bremsweg wächst quadratisch mit der Geschwindigkeit", lambda k: k ** 2))
_register(Formula(
    "kmh_to_ms", "km/h in m/s", ("v_kmh",), "v / 3,6", "m/s", "auf 2 Nachkommastellen", "rule_of_thumb",
    "Physik", lambda v_kmh: round(v_kmh / 3.6, 2)))
_register(Formula(
    "share_of_half_speedometer", "Abstand als Anteil des halben Tachowerts", ("distance_m", "v_kmh"),
    "Abstand / (v / 2)", "", "auf 2 Nachkommastellen", "law",
    "BKatV: Abstandsverstöße werden in Zehnteln des halben Tachowertes bemessen",
    lambda distance_m, v_kmh: round(distance_m / (v_kmh / 2), 2)))


def compute(formula_id: str, **inputs: float) -> CalcResult:
    f = FORMULAS[formula_id]
    missing = [i for i in f.inputs if i not in inputs]
    if missing:
        raise ValueError(f"{formula_id}: missing inputs {missing}")
    for k, v in inputs.items():
        if v < 0 or math.isnan(v):
            raise ValueError(f"{formula_id}: invalid input {k}={v}")
    value = float(f.fn(**{k: inputs[k] for k in f.inputs}))
    steps = (f"{f.name}: {f.formula}", f"Eingaben: {inputs}", f"Ergebnis: {_fmt(value)} {f.unit}".strip())
    return CalcResult(formula_id, value, f.unit, dict(inputs), steps)


def _fmt(x: float) -> str:
    return (f"{x:.2f}".rstrip("0").rstrip(".")).replace(".", ",")


# ----------------------------------------------------------------------------- licence for a combination
@dataclass(frozen=True)
class LicenceDecision:
    licence: str  # "B", "B96", "BE", "beyond BE (C1E/CE ...)"
    reason: str
    rule_ids: tuple[str, ...]


def licence_for_combination(towing_zgm_kg: float, trailer_zgm_kg: float = 0.0) -> LicenceDecision:
    """Which licence is needed for a towing vehicle (zulässige Gesamtmasse) + trailer (FeV § 6 Abs. 1).

    Values are read from the numeric knowledge base (FEV6_*), so they stay tied to the verified law text."""
    from smart360.theory.kb import numeric_value

    b_max = numeric_value("FEV6_B_MAX_ZGM")  # 3500 kg
    light_trailer = numeric_value("FEV6_B_LIGHT_TRAILER")  # 750 kg
    b96_max = numeric_value("FEV6_B96_MAX_COMBINATION")  # 4250 kg
    be_trailer_max = numeric_value("FEV6_BE_MAX_TRAILER")  # 3500 kg
    if towing_zgm_kg > b_max:
        return LicenceDecision("beyond B", "Zugfahrzeug über der Grenze der Klasse B", ("FEV6_B_MAX_ZGM",))
    if trailer_zgm_kg <= light_trailer:
        return LicenceDecision("B", "Anhänger bis 750 kg zulässige Gesamtmasse", ("FEV6_B_LIGHT_TRAILER",))
    total = towing_zgm_kg + trailer_zgm_kg
    if total <= b_max:
        return LicenceDecision("B", "Kombination bis 3500 kg zulässige Gesamtmasse", ("FEV6_B_MAX_ZGM",))
    if total <= b96_max:
        return LicenceDecision("B96", "Kombination über 3500 kg bis 4250 kg (Schlüsselzahl 96)",
                               ("FEV6_B96_MAX_COMBINATION",))
    if trailer_zgm_kg <= be_trailer_max:
        return LicenceDecision("BE", "Anhänger über 750 kg bis 3500 kg, Kombination über 4250 kg",
                               ("FEV6_BE_MAX_TRAILER",))
    return LicenceDecision("beyond BE", "Anhänger über 3500 kg", ("FEV6_BE_MAX_TRAILER",))
