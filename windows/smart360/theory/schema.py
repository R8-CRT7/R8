"""Knowledge objects of the driver-theory knowledge base (Klasse B/BE).

Principle: we store RULES, CONCEPTS, NUMBERS and short OWN summaries - never copied exam questions or textbook
passages. Every object cites its sources; a law citation carries an `evidence` string that must appear verbatim
in the official law snapshot (checked by tests and by the daily knowledge watch).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SourceType = Literal["law", "authority", "exam_authority", "publisher", "driving_school", "rule_of_thumb", "other"]
# 1 = law in force, 2 = official authority, 3 = TÜV/DEKRA (official test body), 4 = DEGENER, 5 = driving-school
# literature / established rule of thumb used in the official question catalogue, 6 = other
SOURCE_PRIORITY: dict[str, int] = {
    "law": 1, "authority": 2, "exam_authority": 3, "publisher": 4, "driving_school": 5, "rule_of_thumb": 5,
    "other": 6,
}

TOPICS: dict[str, str] = {
    "01_personal": "Persönliche Voraussetzungen",
    "02_human_risk": "Risikofaktor Mensch",
    "03_legal": "Rechtliche Rahmenbedingungen",
    "04_road_system": "Straßenverkehrssystem und Bahnübergänge",
    "05_priority": "Grundregel, Vorfahrt und Verkehrsregelungen",
    "06_signs": "Verkehrszeichen und Verkehrseinrichtungen",
    "07_road_users": "Teilnehmer am Straßenverkehr - Besonderheiten und Verhalten",
    "08_speed_distance": "Geschwindigkeit, Abstand und umweltschonende Fahrweise",
    "09_manoeuvres": "Verkehrsbeobachtung und Verkehrsverhalten bei Fahrmanövern",
    "10_parking": "Ruhender Verkehr",
    "11_special": "Verhalten in besonderen Situationen und Folgen von Verkehrsverstößen",
    "12_learning": "Lebenslanges Lernen",
    "13_vehicle_technology": "Technische Bedingungen, Personen-/Güterbeförderung und umweltbewusster Umgang",
    "14_trailers": "Fahren mit Solokraftfahrzeugen und Zügen",
}


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: SourceType
    law: str | None = None  # snapshot slug, e.g. "stvo_2013"
    norm: str | None = None  # "§ 3", "Anlage 2"
    para: str | None = None  # "Abs. 3 Nr. 1" (human readable)
    evidence: str = ""  # verbatim excerpt of the law text (short) - verified against the snapshot
    ref: str | None = None  # non-law reference (publisher, URL, catalogue topic)

    @property
    def priority(self) -> int:
        return SOURCE_PRIORITY[self.type]


class Claim(BaseModel):
    """A statement the engine can evaluate an answer option against.

    `context` = words that describe the situation/question, `statement` = the behaviour/fact. `truth` says
    whether the statement is correct in that context. Paraphrases are matched by content words; negation in
    the answer flips the truth (handled by the negation engine)."""

    model_config = ConfigDict(extra="forbid")
    context: list[str] = Field(default_factory=list)
    statement: str
    truth: bool
    numbers: list[str] = Field(default_factory=list)  # numbers that must match exactly ("50 km/h")


class Versioned(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    version: int = 1
    valid_from: str | None = None  # date the rule applies from (if known)
    valid_until: str | None = None
    last_verified: str | None = None  # date the evidence was checked against the official snapshot
    sources: list[Source]
    confidence: float = Field(1.0, ge=0.0, le=1.0)

    @property
    def source_priority(self) -> int:
        return min(s.priority for s in self.sources) if self.sources else 9

    @field_validator("sources")
    @classmethod
    def _need_source(cls, v: list[Source]) -> list[Source]:
        if not v:
            raise ValueError("every knowledge object needs at least one source")
        return v


class KnowledgeObject(Versioned):
    topic: str
    subtopic: str
    title: str
    rule: str  # own short summary
    conditions: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    numeric_refs: list[str] = Field(default_factory=list)  # ids in numeric_rules.json
    concepts: list[str] = Field(default_factory=list)  # concept-graph nodes
    keywords: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    mnemonic: str = ""  # own short memory aid (learn mode)
    exam_relevance: int = Field(2, ge=1, le=3)  # 3 = typical 5-error-point topic
    difficulty: int = Field(2, ge=1, le=3)

    @field_validator("topic")
    @classmethod
    def _topic(cls, v: str) -> str:
        if v not in TOPICS:
            raise ValueError(f"unknown topic {v}")
        return v


class NumericRule(Versioned):
    topic: str
    quantity: str  # "max_speed", "min_tread_depth", ...
    value: float
    unit: str  # "km/h", "mm", "m", "kg", "‰", "ng/ml", "years", "points", "s", "%"
    applies_to: str  # own description of the situation
    comparator: Literal["max", "min", "eq", "range"] = "eq"
    value_text: str  # how the value is written in the source, e.g. "1,6 mm" - must occur in the evidence
    keywords: list[str] = Field(default_factory=list)


class Sign(Versioned):
    number: str  # "205", "1002-10"
    name: str
    category: Literal["Gefahrzeichen", "Vorschriftzeichen", "Richtzeichen", "Verkehrseinrichtung", "Zusatzzeichen"]
    meaning: str  # own short summary
    effects: list[Literal["verbot", "gebot", "gefahr", "vorfahrt", "wartepflicht", "information", "streckenverbot",
                          "aufhebung", "parken", "halten"]] = Field(default_factory=list)
    priority_effect: Literal["none", "has_priority", "must_yield", "must_stop_and_yield",
                             "priority_next_junction"] = "none"
    keywords: list[str] = Field(default_factory=list)
    confusions: list[str] = Field(default_factory=list)  # numbers of often confused signs
    exceptions: list[str] = Field(default_factory=list)


class Edge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a: str
    b: str
    relation: Literal["requires", "influences", "part_of", "exception_of", "related", "precedes"] = "related"
