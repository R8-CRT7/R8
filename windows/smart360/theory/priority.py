"""Rule-based right-of-way (Vorfahrt) engine.

Input is a scene model (participants, where they come from, where they go, signs/signals facing them). The
engine derives who has to wait for whom by APPLYING the rules in their legal order - it does not look up known
answers:

    police (§ 36) > blue light + siren (§ 38) > rail vehicles at level crossings (§ 19) > traffic lights (§ 37)
    > priority signs (§ 8, Zeichen 205/206/301/306) > leaving a property / lowered kerb (§ 10)
    > turning rules (§ 9: left turners let oncoming traffic pass; turning traffic lets pedestrians and cyclists
      going straight pass) > right before left (§ 8 Abs. 1).

Geometry: each arm (N, E, S, W) has an entry and an exit point on a circle (right-hand traffic). Two paths
conflict when their chords cross or share the exit. Situations the model cannot decide safely (e.g. conflicts
between two vehicles both following a bent priority road, four-way deadlocks) are reported as UNCERTAIN /
deadlock instead of guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Arm = Literal["N", "E", "S", "W"]
Intent = Literal["straight", "left", "right"]
ARMS: tuple[Arm, ...] = ("N", "E", "S", "W")  # clockwise
VEHICLES = {"car", "truck", "motorcycle", "bus", "tram", "bicycle", "emergency"}


@dataclass
class Participant:
    id: str
    kind: str = "car"  # car truck motorcycle bus tram bicycle pedestrian emergency
    arm: Arm = "S"  # where it comes from
    intent: Intent = "straight"
    sign: Literal["none", "priority_road", "yield", "stop", "priority_next"] = "none"
    signal: Literal["none", "green", "red", "yellow", "red_yellow", "green_arrow_sign"] = "none"
    police: Literal["none", "go", "stop"] = "none"
    from_property: bool = False  # leaving a property / lowered kerb / field track (§ 10)
    emergency_active: bool = False  # blue light AND siren (§ 38 Abs. 1)
    in_roundabout: bool = False
    crossing_arm: Arm | None = None  # pedestrians: the arm (road) they cross
    on_crosswalk: bool = False  # pedestrian on a zebra crossing (Zeichen 293, § 26)
    on_bike_path_straight: bool = False  # cyclist going straight next to the lane (§ 9 Abs. 3)


@dataclass
class Junction:
    kind: Literal["crossing", "t_junction", "roundabout", "level_crossing"] = "crossing"
    arms: tuple[Arm, ...] = ARMS
    main_road_arms: frozenset[str] = frozenset()  # arms forming the priority road (straight or bent)
    roundabout_yield: bool = True  # Zeichen 215 with Zeichen 205 at the entries (§ 8 Absatz 1a, Anlage 2 Zeichen 215)


@dataclass
class Yield:
    waits: str
    for_: str
    rule_id: str
    reason: str


@dataclass
class PriorityDecision:
    order: list[list[str]]  # groups that may go in sequence
    yields: list[Yield]
    deadlock: bool = False
    uncertain: list[str] = field(default_factory=list)

    def must_wait_for(self, a: str, b: str) -> bool:
        return any(y.waits == a and y.for_ == b for y in self.yields)

    def first(self) -> list[str]:
        return self.order[0] if self.order else []


# ----------------------------------------------------------------------------- geometry
def _idx(a: str) -> int:
    return ARMS.index(a)  # type: ignore[arg-type]


def exit_arm(p: Participant) -> str:
    i = _idx(p.arm)
    return ARMS[{"straight": (i + 2) % 4, "right": (i - 1) % 4, "left": (i + 1) % 4}[p.intent]]


def right_of(arm: str) -> str:
    """The arm on the RIGHT of a vehicle coming from `arm` (vehicle from S: right is E)."""
    return ARMS[(_idx(arm) - 1) % 4]


def opposite(arm: str) -> str:
    return ARMS[(_idx(arm) + 2) % 4]


def _chord(p: Participant) -> tuple[int, int]:
    return (2 * _idx(p.arm), 2 * _idx(exit_arm(p)) + 1)  # in-point, out-point on an 8-point circle


def _between(x: int, a: int, b: int) -> bool:
    lo, hi = sorted((a, b))
    return lo < x < hi


def paths_conflict(a: Participant, b: Participant) -> bool:
    if a.kind == "pedestrian" or b.kind == "pedestrian":
        ped, veh = (a, b) if a.kind == "pedestrian" else (b, a)
        if veh.kind == "pedestrian":
            return False
        return ped.crossing_arm in (veh.arm, exit_arm(veh))
    if a.in_roundabout != b.in_roundabout:
        # roundabout (right-hand traffic, counter-clockwise): the circulating vehicle passes every arm between its
        # entry and its exit; an entering vehicle conflicts with it if its entry arm is one of those
        inside, entering = (a, b) if a.in_roundabout else (b, a)
        steps = {"right": 1, "straight": 2, "left": 3}.get(inside.intent, 3)
        passed: list[str] = []
        arm: str = inside.arm
        for _ in range(steps - 1):
            arm = right_of(arm)
            passed.append(arm)
        return entering.arm in passed
    if a.arm == b.arm:  # same entry: only a cyclist going straight next to a right/left turner
        return (a.on_bike_path_straight and b.intent != "straight") or (
            b.on_bike_path_straight and a.intent != "straight")
    (a1, a2), (b1, b2) = _chord(a), _chord(b)
    if a2 == b2:
        return True
    return _between(b1, a1, a2) != _between(b2, a1, a2)


# ----------------------------------------------------------------------------- pairwise rules
def _priority_class(p: Participant, j: Junction) -> int:
    """2 = on the priority road / priority sign, 1 = no sign, 0 = yield/stop sign."""
    if p.sign in ("yield", "stop"):
        return 0
    if p.sign in ("priority_road", "priority_next") or p.arm in j.main_road_arms:
        return 2
    if j.main_road_arms:
        return 0  # side road of a priority road without own sign (sign may be hidden) -> treat as waiting
    return 1


def _decide(a: Participant, b: Participant, j: Junction) -> Yield | str | None:
    """Who waits for whom (Yield), 'uncertain:<why>' or None (no conflict)."""
    if not paths_conflict(a, b):
        return None
    # 1. police
    if a.police != "none" or b.police != "none":
        if a.police == "stop" and b.police != "stop":
            return Yield(a.id, b.id, "STVO_36_POLICE", "Weisung der Polizei geht allen Regeln vor")
        if b.police == "stop" and a.police != "stop":
            return Yield(b.id, a.id, "STVO_36_POLICE", "Weisung der Polizei geht allen Regeln vor")
    # 2. emergency vehicles with blue light and siren
    if a.emergency_active != b.emergency_active:
        e, o = (a, b) if a.emergency_active else (b, a)
        return Yield(o.id, e.id, "STVO_38_EMERGENCY", "Blaues Blinklicht mit Einsatzhorn: sofort freie Bahn schaffen")
    # 3. rail vehicles at level crossings
    if j.kind == "level_crossing" and (a.kind == "tram" or b.kind == "tram") and a.kind != b.kind:
        r, o = (a, b) if a.kind == "tram" else (b, a)
        return Yield(o.id, r.id, "STVO_19_RAIL", "Schienenfahrzeuge haben am Bahnübergang Vorrang")
    # 4. traffic lights (go before priority rules and signs)
    if a.signal != "none" or b.signal != "none":
        red = ("red", "yellow", "red_yellow")
        if a.signal in red and b.signal not in red:
            return Yield(a.id, b.id, "STVO_37_LIGHTS", "Rot/Gelb: anhalten; Lichtzeichen gehen Vorfahrtregeln vor")
        if b.signal in red and a.signal not in red:
            return Yield(b.id, a.id, "STVO_37_LIGHTS", "Rot/Gelb: anhalten; Lichtzeichen gehen Vorfahrtregeln vor")
        if a.signal == "green_arrow_sign" and b.signal == "green":
            return Yield(a.id, b.id, "STVO_37_GREEN_ARROW", "Grünpfeil: anhalten und den Verkehr bei Grün durchlassen")
        if b.signal == "green_arrow_sign" and a.signal == "green":
            return Yield(b.id, a.id, "STVO_37_GREEN_ARROW", "Grünpfeil: anhalten und den Verkehr bei Grün durchlassen")
        if a.signal in red and b.signal in red:
            return None  # both stopped
        # both green -> turning rules below decide (signs are overridden by the lights)
        if a.kind == "pedestrian" or b.kind == "pedestrian":
            return _pedestrian(a, b)
        return _turning(a, b, j, ignore_signs=True)
    # 5. pedestrians
    if a.kind == "pedestrian" or b.kind == "pedestrian":
        return _pedestrian(a, b)
    return _turning(a, b, j, ignore_signs=False)


def _pedestrian(a: Participant, b: Participant) -> Yield:
    ped, veh = (a, b) if a.kind == "pedestrian" else (b, a)
    if ped.on_crosswalk:
        return Yield(veh.id, ped.id, "STVO_26_CROSSWALK", "Fußgängerüberweg: Fußgängern das Überqueren ermöglichen")
    if veh.intent != "straight" and ped.crossing_arm == exit_arm(veh):
        return Yield(veh.id, ped.id, "STVO_9_PEDESTRIANS",
                     "Beim Abbiegen auf Fußgänger, die die Straße überqueren, besondere Rücksicht; ggf. warten")
    return Yield(ped.id, veh.id, "STVO_25_PEDESTRIANS", "Fußgänger müssen den Fahrverkehr beachten (kein Überweg)")


def _turning(a: Participant, b: Participant, j: Junction, ignore_signs: bool) -> Yield | str | None:
    if j.kind == "roundabout" and a.in_roundabout != b.in_roundabout:
        inside, entering = (a, b) if a.in_roundabout else (b, a)
        if j.roundabout_yield:
            return Yield(entering.id, inside.id, "STVO_8_ROUNDABOUT",
                         "Kreisverkehr mit Zeichen 215 und 205: der Verkehr im Kreis hat Vorfahrt")
        return Yield(inside.id, entering.id, "STVO_8_RIGHT_BEFORE_LEFT",
                     "Kreisverkehr ohne Zeichen 205: rechts vor links - der Einfahrende kommt von rechts")
    if not ignore_signs:
        ca, cb = _priority_class(a, j), _priority_class(b, j)
        if ca != cb:
            w, o = (a, b) if ca < cb else (b, a)
            return Yield(w.id, o.id, "STVO_8_SIGNS", "Vorfahrt durch Verkehrszeichen geregelt")
    if a.from_property != b.from_property:
        w, o = (a, b) if a.from_property else (b, a)
        return Yield(w.id, o.id, "STVO_10_PROPERTY",
                     "Aus einem Grundstück / über einen abgesenkten Bordstein: allen anderen Vorrang lassen")
    # cyclist going straight next to a turning vehicle from the same arm
    if a.arm == b.arm:
        cyc, veh = (a, b) if a.on_bike_path_straight else (b, a)
        return Yield(veh.id, cyc.id, "STVO_9_CYCLISTS", "Beim Abbiegen geradeaus fahrende Radfahrer durchlassen")
    # bent priority road: both on the priority road -> not modelled reliably
    if j.main_road_arms and a.arm in j.main_road_arms and b.arm in j.main_road_arms and not ignore_signs:
        straight_main = {opposite(x) for x in j.main_road_arms} == set(j.main_road_arms)
        if not straight_main:
            return "uncertain:both on a bent priority road (abknickende Vorfahrt) - not modelled"
    # left turner lets oncoming traffic pass (§ 9 Abs. 3)
    if opposite(a.arm) == b.arm:
        if a.intent == "left" and b.intent in ("straight", "right"):
            return Yield(a.id, b.id, "STVO_9_LEFT_ONCOMING", "Linksabbieger lässt den Gegenverkehr durchfahren")
        if b.intent == "left" and a.intent in ("straight", "right"):
            return Yield(b.id, a.id, "STVO_9_LEFT_ONCOMING", "Linksabbieger lässt den Gegenverkehr durchfahren")
        return None  # two oncoming left turners pass in front of each other
    # right before left (§ 8 Abs. 1) - also trams and cyclists
    if right_of(a.arm) == b.arm:
        return Yield(a.id, b.id, "STVO_8_RIGHT_BEFORE_LEFT", "Rechts vor links")
    if right_of(b.arm) == a.arm:
        return Yield(b.id, a.id, "STVO_8_RIGHT_BEFORE_LEFT", "Rechts vor links")
    return "uncertain:no rule decided this conflict"


def decide(participants: list[Participant], junction: Junction | None = None) -> PriorityDecision:
    j = junction or Junction()
    yields: list[Yield] = []
    uncertain: list[str] = []
    for i, a in enumerate(participants):
        for b in participants[i + 1:]:
            r = _decide(a, b, j)
            if isinstance(r, Yield):
                yields.append(r)
            elif isinstance(r, str):
                uncertain.append(f"{a.id}/{b.id}: {r.split(':', 1)[1]}")
    # order: repeatedly release everyone who waits for nobody still waiting
    remaining = [p.id for p in participants]
    order: list[list[str]] = []
    deadlock = False
    while remaining:
        free = [x for x in remaining if not any(y.waits == x and y.for_ in remaining for y in yields)]
        if not free:
            deadlock = True
            uncertain.append("deadlock: everyone has to wait for someone (Verständigung nötig)")
            order.append(sorted(remaining))
            break
        order.append(free)
        remaining = [x for x in remaining if x not in free]
    return PriorityDecision(order, yields, deadlock, uncertain)
