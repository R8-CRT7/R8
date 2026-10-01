"""Error root causes - for the learner's mistakes and for the engine's own mistakes.

A mistake is not just 'question wrong'. The cause decides the repair:
  root cause -> repair action -> regression test -> new variants -> re-check later."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from smart360.theory.negation import analyze, asks_for_negative


class RootCause(StrEnum):
    OCR_ERROR = "OCR_ERROR"
    KNOWLEDGE_MISSING = "KNOWLEDGE_MISSING"
    RULE_SELECTION_ERROR = "RULE_SELECTION_ERROR"
    NEGATION_ERROR = "NEGATION_ERROR"
    CALCULATION_ERROR = "CALCULATION_ERROR"
    IMAGE_UNDERSTANDING_ERROR = "IMAGE_UNDERSTANDING_ERROR"
    MULTISELECT_ERROR = "MULTISELECT_ERROR"
    OUTDATED_RULE = "OUTDATED_RULE"
    AMBIGUOUS_QUESTION = "AMBIGUOUS_QUESTION"
    MODEL_REASONING_ERROR = "MODEL_REASONING_ERROR"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"


REPAIR = {
    RootCause.OCR_ERROR: "OCR-Normalisierung/Kalibrierung prüfen, Störung als Testvariante aufnehmen",
    RootCause.KNOWLEDGE_MISSING: "Regel mit Quelle ergänzen, Claims + Varianten erzeugen",
    RootCause.RULE_SELECTION_ERROR: "Kontext/Keywords der Regel schärfen, Verwechslungsregel als Distraktor-Test",
    RootCause.NEGATION_ERROR: "Negationsfall als Regressionstest, Lernkarte 'Signalwörter' wiederholen",
    RootCause.CALCULATION_ERROR: "Formel/Einheit prüfen, Rechenvariante als Test",
    RootCause.IMAGE_UNDERSTANDING_ERROR: "Szenenmodell prüfen, Bildvariante als Test",
    RootCause.MULTISELECT_ERROR: "jede Antwort einzeln prüfen üben; Mehrfachauswahl-Test",
    RootCause.OUTDATED_RULE: "Rechtsstand prüfen (Knowledge Watch), Regel versionieren",
    RootCause.AMBIGUOUS_QUESTION: "als mehrdeutig markieren, UNCERTAIN statt Antwort",
    RootCause.MODEL_REASONING_ERROR: "Regelpfad statt Modellantwort, Gegenprüfung erzwingen",
    RootCause.SOURCE_CONFLICT: "Quellenhierarchie anwenden (Gesetz vor Lehrbuch), Konflikt dokumentieren",
}


@dataclass(frozen=True)
class Diagnosis:
    cause: RootCause
    detail: str
    repair: str


def learner_mistake(question: str, answers: list[str], chosen: set[int], expected: set[int],
                    numeric: bool = False, image: bool = False) -> Diagnosis:
    """Why did the learner get it wrong? Heuristics in order of how clear the evidence is."""
    if numeric:
        return _d(RootCause.CALCULATION_ERROR, "Rechenaufgabe falsch gelöst")
    neg_q = asks_for_negative(question)
    wrong = chosen - expected
    missed = expected - chosen
    if neg_q and chosen and not (chosen & expected):
        return _d(RootCause.NEGATION_ERROR, "Frage nach dem FALSCHEN/VERBOTENEN - die richtigen Aussagen gewählt")
    if any(analyze(answers[i - 1]).negated or analyze(answers[i - 1]).deontic.value in ("forbidden", "not_obligatory")
           for i in wrong | missed if 0 < i <= len(answers)):
        return _d(RootCause.NEGATION_ERROR, "Signalwort (nicht/kein/darf nicht/muss nicht) übersehen")
    if chosen and expected and (chosen < expected or chosen > expected):
        return _d(RootCause.MULTISELECT_ERROR,
                  "nur ein Teil der richtigen Antworten" if chosen < expected else "zusätzlich eine falsche Antwort")
    if image:
        return _d(RootCause.IMAGE_UNDERSTANDING_ERROR, "Situation im Bild falsch eingeschätzt")
    return _d(RootCause.KNOWLEDGE_MISSING, "Regel nicht sicher bekannt")


def engine_mistake(result, expected: set[int], expected_number: str | None = None) -> Diagnosis:  # type: ignore[no-untyped-def]
    """Why did the ENGINE get it wrong (result = TheoryResult)?"""
    flags = {f for e in result.evals for f in e.flags}
    if result.factors.get("ocr", 1.0) < 0.6:
        return _d(RootCause.OCR_ERROR, "niedrige OCR-Konfidenz")
    if "numeric" in result.kinds or expected_number is not None:
        return _d(RootCause.CALCULATION_ERROR, "Rechenweg/Einheit")
    if "conflicting_rules" in flags:
        return _d(RootCause.SOURCE_CONFLICT, "zwei Regeln widersprechen sich")
    if "negation_flip" in flags or "negative_question" in result.kinds:
        return _d(RootCause.NEGATION_ERROR, "Negation/Frage nach dem Falschen")
    if "image" in result.kinds:
        return _d(RootCause.IMAGE_UNDERSTANDING_ERROR, "Szenenmodell")
    sel = set(result.selected)
    if sel and expected and (sel < expected or sel > expected):
        return _d(RootCause.MULTISELECT_ERROR, "Teilmenge/Obermenge der richtigen Antworten")
    if any(e.method == "none" for e in result.evals):
        return _d(RootCause.KNOWLEDGE_MISSING, "keine passende Regel")
    if any("disagrees" in r for r in result.reasons):
        return _d(RootCause.MODEL_REASONING_ERROR, "Sprachmodell widerspricht")
    return _d(RootCause.RULE_SELECTION_ERROR, "falsche Regel gewählt")


def _d(cause: RootCause, detail: str) -> Diagnosis:
    return Diagnosis(cause, detail, REPAIR[cause])
