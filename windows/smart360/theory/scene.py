"""Scene model for picture and video questions.

A picture is first turned into a structured scene (by a vision model or by hand in tests), and only then are the
answers evaluated. Video/dynamic questions carry several frames; one frame alone is never treated as complete
when the question depends on motion (approach, speed, new hazards)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from smart360.theory.priority import Junction, Participant
from smart360.theory.text import fold

# JSON schema the vision model has to fill (structured output). Kept small and explicit.
SCENE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["junction", "participants", "traffic_signs", "signals", "road_markings", "visibility", "confidence"],
    "properties": {
        "junction": {"type": "object", "additionalProperties": False,
                     "required": ["kind", "main_road_arms", "roundabout_yield"],
                     "properties": {"kind": {"enum": ["crossing", "t_junction", "roundabout", "level_crossing", "none"]},
                                    "main_road_arms": {"type": "array", "items": {"enum": ["N", "E", "S", "W"]}},
                                    "roundabout_yield": {"type": "boolean"}}},
        "participants": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "kind", "labels", "arm", "intent"],
            "properties": {
                "id": {"type": "string"},
                "kind": {"enum": ["me", "car", "truck", "motorcycle", "bus", "tram", "bicycle", "pedestrian",
                                  "emergency"]},
                "labels": {"type": "array", "items": {"type": "string"}},  # "blauer Pkw", "Radfahrer"
                "arm": {"enum": ["N", "E", "S", "W"]},
                "intent": {"enum": ["straight", "left", "right", "unknown"]},
                "sign": {"enum": ["none", "priority_road", "yield", "stop", "priority_next"]},
                "signal": {"enum": ["none", "green", "red", "yellow", "red_yellow", "green_arrow_sign"]},
                "police": {"enum": ["none", "go", "stop"]},
                "from_property": {"type": "boolean"},
                "emergency_active": {"type": "boolean"},
                "in_roundabout": {"type": "boolean"},
                "crossing_arm": {"enum": ["N", "E", "S", "W", None]},
                "on_crosswalk": {"type": "boolean"},
                "on_bike_path_straight": {"type": "boolean"},
                "moving": {"type": "boolean"},
            }}},
        "traffic_signs": {"type": "array", "items": {"type": "string"}},  # sign numbers, e.g. "205", "1002-10"
        "signals": {"type": "array", "items": {"type": "string"}},
        "road_markings": {"type": "array", "items": {"type": "string"}},
        "visibility": {"enum": ["good", "reduced", "poor", "unknown"]},
        "possible_conflicts": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


@dataclass
class SceneParticipant:
    participant: Participant
    labels: list[str] = field(default_factory=list)
    is_me: bool = False
    intent_known: bool = True


@dataclass
class Scene:
    junction: Junction
    participants: list[SceneParticipant]
    traffic_signs: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    road_markings: list[str] = field(default_factory=list)
    visibility: str = "unknown"
    confidence: float = 0.5
    t: float = 0.0  # seconds (video frames)

    def me(self) -> SceneParticipant | None:
        return next((p for p in self.participants if p.is_me), None)

    def find(self, text: str) -> list[SceneParticipant]:
        """Participants an answer text refers to ('den blauen Pkw', 'der Radfahrer', 'ich')."""
        t = fold(text)
        hits = []
        for p in self.participants:
            if p.is_me and re.search(r"\b(ich|mich|mir|mein\w*)\b", t):
                hits.append(p)
                continue
            for lab in p.labels:
                core = [w for w in fold(lab).split() if len(w) > 2]
                if core and all(w[:-1] in t for w in core):
                    hits.append(p)
                    break
        return hits


def scene_from_dict(d: dict[str, Any], t: float = 0.0) -> Scene:
    j = d.get("junction") or {}
    kind = j.get("kind", "crossing")
    junction = Junction(
        kind="crossing" if kind == "none" else kind,
        main_road_arms=frozenset(j.get("main_road_arms", [])),
        roundabout_yield=bool(j.get("roundabout_yield", True)),
    )
    parts = []
    for p in d.get("participants", []):
        kind_p = p.get("kind", "car")
        intent = p.get("intent", "straight")
        part = Participant(
            id=p["id"], kind="car" if kind_p == "me" else kind_p, arm=p.get("arm", "S"),
            intent="straight" if intent == "unknown" else intent,
            sign=p.get("sign", "none"), signal=p.get("signal", "none"), police=p.get("police", "none"),
            from_property=bool(p.get("from_property", False)), emergency_active=bool(p.get("emergency_active", False)),
            in_roundabout=bool(p.get("in_roundabout", False)), crossing_arm=p.get("crossing_arm"),
            on_crosswalk=bool(p.get("on_crosswalk", False)),
            on_bike_path_straight=bool(p.get("on_bike_path_straight", False)),
        )
        parts.append(SceneParticipant(part, list(p.get("labels", [])), kind_p == "me", intent != "unknown"))
    return Scene(junction, parts, list(d.get("traffic_signs", [])), list(d.get("signals", [])),
                 list(d.get("road_markings", [])), d.get("visibility", "unknown"), float(d.get("confidence", 0.5)), t)


DYNAMIC_CUES = ("film", "video", "nähert sich", "naehert sich", "kommt näher", "beschleunigt", "bremst",
                "im weiteren verlauf", "gleich", "plötzlich", "ploetzlich", "entwickelt sich", "bewegt sich")


@dataclass(frozen=True)
class TemporalCheck:
    complete: bool
    reason: str


def temporal_check(question: str, frames: list[Scene] | None, is_video: bool = False) -> TemporalCheck:
    """A single frame is not enough for a question about motion; missing frames -> not complete."""
    t = fold(question)
    dynamic = is_video or any(c in t for c in DYNAMIC_CUES)
    n = len(frames or [])
    if not dynamic:
        return TemporalCheck(True, "static question")
    if n < 2:
        return TemporalCheck(False, "dynamic situation but fewer than 2 frames - motion/approach unknown")
    if any(not p.intent_known for f in frames or [] for p in f.participants):
        return TemporalCheck(False, "intent of a participant unknown in at least one frame")
    return TemporalCheck(True, f"{n} frames")
