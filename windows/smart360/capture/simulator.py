"""A 360°-style practice screen simulator.

Used for: demo mode (try the product without the real software), end-to-end
integration tests with real OCR, chaos tests and README screenshots.

The questions are self-written practice questions in the style of the German
theory test; they are NOT copied from the official catalogue or from DEGENER.
"""

from __future__ import annotations

import random
import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from smart360.core.models import NormRect, Rect

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


@dataclass(frozen=True)
class SimQuestion:
    text: str
    answers: tuple[str, ...]
    correct: tuple[int, ...]
    reason: str
    topic: str
    image: str | None = None  # "stop", "yield", "speed50", "crossing", "priority"
    number_answer: str | None = None


QUESTION_BANK: tuple[SimQuestion, ...] = (
    SimQuestion(
        "Sie nähern sich einer Kreuzung ohne Verkehrszeichen. Von rechts kommt ein Radfahrer."
        " Wie verhalten Sie sich?",
        (
            "Ich lasse den Radfahrer zuerst fahren",
            "Ich fahre zügig vor dem Radfahrer",
            "Ich verringere die Geschwindigkeit und bin bremsbereit",
        ),
        (1, 3),
        "Ohne Regelung gilt rechts vor links, auch für Radfahrer.",
        "Vorfahrt",
        "crossing",
    ),
    SimQuestion(
        "Was bedeutet dieses Verkehrszeichen?",
        ("Vorfahrt gewähren", "Halt, Vorfahrt gewähren", "Nur an Kreuzungen anhalten, wenn Verkehr kommt"),
        (2,),
        "Beim Stoppschild muss immer an der Haltlinie angehalten werden.",
        "Verkehrszeichen",
        "stop",
    ),
    SimQuestion(
        "Welche Höchstgeschwindigkeit gilt nach diesem Zeichen für Pkw?",
        ("30 km/h", "50 km/h", "70 km/h"),
        (2,),
        "Das Zeichen begrenzt die Geschwindigkeit auf 50 km/h.",
        "Geschwindigkeit",
        "speed50",
    ),
    SimQuestion(
        "Womit müssen Sie rechnen, wenn am Fahrbahnrand Kinder mit Schulranzen stehen?",
        (
            "Dass die Kinder plötzlich auf die Fahrbahn laufen",
            "Dass die Kinder stehen bleiben",
            "Dass ein Kind unaufmerksam ist",
        ),
        (1, 3),
        "Kinder handeln oft spontan; rechnen Sie immer mit Fehlverhalten.",
        "Gefahrenlehre",
        None,
    ),
    SimQuestion(
        "Wie verhalten Sie sich an diesem Zeichen?",
        (
            "Ich gewähre dem Querverkehr Vorfahrt",
            "Ich habe an der nächsten Kreuzung Vorfahrt",
            "Ich muss in jedem Fall anhalten",
        ),
        (1,),
        "Das Dreieck auf der Spitze bedeutet Vorfahrt gewähren.",
        "Verkehrszeichen",
        "yield",
    ),
    SimQuestion(
        "Wann müssen Sie beim Überholen besonders vorsichtig sein?",
        (
            "Bei unklarer Verkehrslage",
            "Wenn der Gegenverkehr schlecht einzusehen ist",
            "Auf einer Autobahn mit drei freien Fahrstreifen",
        ),
        (1, 2),
        "Bei unklarer Lage und schlechter Sicht ist Überholen gefährlich oder verboten.",
        "Überholen",
        None,
    ),
    SimQuestion(
        "Was gilt an diesem Verkehrszeichen?",
        (
            "Ich habe Vorfahrt an der nächsten Kreuzung oder Einmündung",
            "Ich muss Vorfahrt gewähren",
            "Ich darf hier nicht halten",
        ),
        (1,),
        "Das Zeichen gibt Vorfahrt an der nächsten Kreuzung oder Einmündung.",
        "Vorfahrt",
        "priority",
    ),
    SimQuestion(
        "Wie groß ist der Anhalteweg bei 50 km/h und normaler Bremsung ungefähr, wenn der"
        " Reaktionsweg 15 m und der Bremsweg 25 m beträgt? Antwort in Metern.",
        (),
        (),
        "Anhalteweg = Reaktionsweg + Bremsweg = 15 m + 25 m.",
        "Abstand",
        None,
        "40",
    ),
    SimQuestion(
        "Warum ist ein gleichmäßiger Fahrstil umweltschonend?",
        (
            "Er senkt den Kraftstoffverbrauch",
            "Er verringert Lärm und Abgase",
            "Er erhöht den Reifenverschleiß",
        ),
        (1, 2),
        "Gleichmäßiges Fahren spart Kraftstoff und reduziert Emissionen.",
        "Umwelt",
        None,
    ),
    SimQuestion(
        "Was müssen Sie vor Fahrtantritt bei einem Pkw regelmäßig prüfen?",
        ("Reifendruck und Profiltiefe", "Funktion der Beleuchtung", "Den Stand des Kilometerzählers"),
        (1, 2),
        "Reifen und Beleuchtung sind sicherheitsrelevant und regelmäßig zu prüfen.",
        "Technik",
        None,
    ),
)

# Screen layout (fractions of the simulator window). Shared with the default profile.
LAYOUT = {
    "question": NormRect(0.06, 0.14, 0.88, 0.17),
    "image": NormRect(0.06, 0.34, 0.34, 0.44),
    "answers": NormRect(0.43, 0.34, 0.51, 0.46),
    "action": NormRect(0.78, 0.86, 0.16, 0.08),
}


def _font(size: int, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONT_DIR / f"Inter-{weight}.ttf"), size)
    except OSError:
        return ImageFont.load_default(size)  # type: ignore[return-value]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


@dataclass
class SimulatorState:
    index: int = 0
    order: tuple[int, ...] = ()
    selected: set[int] = field(default_factory=set)  # displayed indices (1-based)
    typed: str = ""


class PracticeSimulator:
    """Thread-safe. Coordinates are relative to the simulator window origin `origin`."""

    def __init__(
        self,
        width: int = 1280,
        height: int = 800,
        origin: tuple[int, int] = (100, 80),
        shuffle: bool = False,
        seed: int = 7,
        bank: tuple[SimQuestion, ...] = QUESTION_BANK,
    ):
        self.width, self.height = width, height
        self.origin = origin
        self.shuffle = shuffle
        self.bank = bank
        self._rng = random.Random(seed)
        self._lock = threading.RLock()
        self.state = SimulatorState()
        self.visible = True
        self.clicks: deque[tuple[int, int]] = deque(maxlen=200)  # bounded: demo mode runs for hours
        self._checkboxes: dict[int, Rect] = {}
        self._frame: Image.Image | None = None
        self.goto(0)

    # ------------------------------------------------------------------ control
    @property
    def rect(self) -> Rect:
        return Rect(self.origin[0], self.origin[1], self.width, self.height)

    @property
    def question(self) -> SimQuestion:
        return self.bank[self.state.index]

    def displayed_answers(self) -> list[str]:
        q = self.question
        return [q.answers[i] for i in self.state.order]

    def displayed_correct(self) -> tuple[int, ...]:
        q = self.question
        return tuple(sorted(self.state.order.index(c - 1) + 1 for c in q.correct))

    def goto(self, index: int) -> None:
        with self._lock:
            index %= len(self.bank)
            order = list(range(len(self.bank[index].answers)))
            if self.shuffle:
                self._rng.shuffle(order)
            self.state = SimulatorState(index=index, order=tuple(order))
            self._frame = None

    def next(self) -> None:
        self.goto(self.state.index + 1)

    def move(self, x: int, y: int) -> None:
        with self._lock:
            self.origin = (x, y)

    def resize(self, w: int, h: int) -> None:
        with self._lock:
            self.width, self.height = w, h
            self._frame = None

    def click(self, sx: int, sy: int) -> bool:
        """Screen-coordinate click. Returns True if it hit a checkbox."""
        with self._lock:
            self.clicks.append((sx, sy))
            if not self.visible:
                return False
            lx, ly = sx - self.origin[0], sy - self.origin[1]
            for idx, r in self._checkboxes.items():
                grown = Rect(r.x - 6, r.y - 6, r.w + 12, r.h + 12)
                if grown.contains(lx, ly):
                    self.state.selected ^= {idx}
                    self._frame = None
                    return True
            action = LAYOUT["action"].to_abs(Rect(0, 0, self.width, self.height))
            if action.contains(lx, ly):
                self.next()
            return False

    def type_text(self, text: str) -> None:
        with self._lock:
            self.state.typed = text
            self._frame = None

    def is_solved_correctly(self) -> bool:
        with self._lock:
            if self.question.number_answer is not None:
                return self.state.typed == self.question.number_answer
            return tuple(sorted(self.state.selected)) == self.displayed_correct()

    # ------------------------------------------------------------------ rendering
    def render(self) -> Image.Image:
        with self._lock:
            if self._frame is not None:
                return self._frame
            self._frame = self._render()
            return self._frame

    def _render(self) -> Image.Image:
        w, h = self.width, self.height
        img = Image.new("RGB", (w, h), (246, 248, 251))
        d = ImageDraw.Draw(img)
        frame = Rect(0, 0, w, h)
        # header
        d.rectangle((0, 0, w, int(h * 0.09)), fill=(0, 84, 147))
        d.text(
            (int(w * 0.03), int(h * 0.025)),
            "Theorie-Training  ·  Übungsbogen",
            font=_font(int(h * 0.03), "SemiBold"),
            fill=(255, 255, 255),
        )
        d.text(
            (int(w * 0.80), int(h * 0.028)),
            f"Frage {self.state.index + 1}/{len(self.bank)}",
            font=_font(int(h * 0.026)),
            fill=(210, 230, 245),
        )
        q = self.question
        # question text
        qr = LAYOUT["question"].to_abs(frame)
        qfont = _font(max(14, int(h * 0.029)), "SemiBold")
        y = qr.y + 6
        for line in _wrap(d, q.text, qfont, qr.w - 12)[:4]:
            d.text((qr.x + 6, y), line, font=qfont, fill=(20, 28, 38))
            y += int(qfont.size * 1.35)
        # image
        ir = LAYOUT["image"].to_abs(frame)
        d.rounded_rectangle(
            (ir.x, ir.y, ir.x + ir.w, ir.y + ir.h), radius=8, fill=(255, 255, 255), outline=(214, 220, 228)
        )
        if q.image:
            self._draw_image(d, ir, q.image)
        # answers
        ar = LAYOUT["answers"].to_abs(frame)
        afont = _font(max(13, int(h * 0.026)))
        self._checkboxes = {}
        if q.number_answer is not None:
            d.text((ar.x + 6, ar.y + 10), "Antwort:", font=afont, fill=(20, 28, 38))
            inp = (
                ar.x + 6 + int(d.textlength("Antwort: ", font=afont)) + 8,
                ar.y + 4,
                ar.x + 6 + int(d.textlength("Antwort: ", font=afont)) + 150,
                ar.y + 4 + int(afont.size * 1.8),
            )
            d.rectangle(inp, outline=(120, 130, 140), width=2, fill=(255, 255, 255))
            d.text((inp[0] + 8, inp[1] + 6), self.state.typed, font=afont, fill=(20, 28, 38))
            d.text((inp[2] + 10, ar.y + 10), "m", font=afont, fill=(20, 28, 38))
        else:
            y = ar.y + 6
            cb = int(afont.size * 1.1)
            for disp_idx, text in enumerate(self.displayed_answers(), start=1):
                box = Rect(ar.x + 6, y + 2, cb, cb)
                self._checkboxes[disp_idx] = box
                sel = disp_idx in self.state.selected
                d.rectangle(
                    (box.x, box.y, box.x + box.w, box.y + box.h),
                    outline=(90, 100, 112),
                    width=2,
                    fill=(0, 84, 147) if sel else (255, 255, 255),
                )
                if sel:
                    d.line(
                        (
                            box.x + 4,
                            box.y + cb // 2,
                            box.x + cb // 2 - 1,
                            box.y + cb - 5,
                            box.x + cb - 4,
                            box.y + 4,
                        ),
                        fill=(255, 255, 255),
                        width=3,
                    )
                lines = _wrap(d, text, afont, ar.w - cb - 30)
                ty = y
                for line in lines:
                    d.text((box.x + cb + 14, ty), line, font=afont, fill=(20, 28, 38))
                    ty += int(afont.size * 1.3)
                y = ty + int(afont.size * 1.6)
        # action button
        br = LAYOUT["action"].to_abs(frame)
        d.rounded_rectangle((br.x, br.y, br.x + br.w, br.y + br.h), radius=10, fill=(0, 84, 147))
        f = _font(int(h * 0.026), "SemiBold")
        tw = d.textlength("Weiter", font=f)
        d.text(
            (br.x + (br.w - tw) / 2, br.y + br.h / 2 - f.size * 0.6), "Weiter", font=f, fill=(255, 255, 255)
        )
        return img

    @staticmethod
    def _draw_image(d: ImageDraw.ImageDraw, r: Rect, kind: str) -> None:
        cx, cy = r.x + r.w // 2, r.y + r.h // 2
        s = min(r.w, r.h) // 3
        if kind == "stop":
            import math

            pts = [
                (
                    cx + s * math.cos(math.radians(22.5 + 45 * i)),
                    cy + s * math.sin(math.radians(22.5 + 45 * i)),
                )
                for i in range(8)
            ]
            d.polygon(pts, fill=(200, 20, 30), outline=(255, 255, 255))
            f = _font(int(s * 0.5), "Bold")
            tw = d.textlength("STOP", font=f)
            d.text((cx - tw / 2, cy - f.size * 0.6), "STOP", font=f, fill=(255, 255, 255))
        elif kind == "yield":
            d.polygon([(cx - s, cy - s * 0.8), (cx + s, cy - s * 0.8), (cx, cy + s)], fill=(200, 20, 30))
            d.polygon(
                [(cx - s * 0.62, cy - s * 0.58), (cx + s * 0.62, cy - s * 0.58), (cx, cy + s * 0.55)],
                fill=(255, 255, 255),
            )
        elif kind == "speed50":
            d.ellipse((cx - s, cy - s, cx + s, cy + s), fill=(200, 20, 30))
            d.ellipse((cx - s * 0.78, cy - s * 0.78, cx + s * 0.78, cy + s * 0.78), fill=(255, 255, 255))
            f = _font(int(s * 0.8), "Bold")
            tw = d.textlength("50", font=f)
            d.text((cx - tw / 2, cy - f.size * 0.62), "50", font=f, fill=(10, 10, 10))
        elif kind == "priority":
            d.polygon(
                [(cx, cy - s), (cx + s * 0.8, cy + s * 0.6), (cx - s * 0.8, cy + s * 0.6)], fill=(200, 20, 30)
            )
            d.polygon(
                [(cx, cy - s * 0.6), (cx + s * 0.5, cy + s * 0.4), (cx - s * 0.5, cy + s * 0.4)],
                fill=(255, 255, 255),
            )
            d.rectangle((cx - 4, cy - s * 0.3, cx + 4, cy + s * 0.3), fill=(10, 10, 10))
        elif kind == "crossing":
            d.rectangle((r.x, cy - s * 0.5, r.x + r.w, cy + s * 0.5), fill=(90, 94, 100))
            d.rectangle((cx - s * 0.5, r.y, cx + s * 0.5, r.y + r.h), fill=(90, 94, 100))
            d.rectangle((cx - s * 0.25, cy + s * 0.9, cx + s * 0.05, cy + s * 1.4), fill=(30, 110, 200))  # me
            d.ellipse(
                (cx + s * 0.9, cy - s * 0.35, cx + s * 1.15, cy - s * 0.1), fill=(40, 170, 80)
            )  # cyclist


def simulator_profile(name: str = "Simulator") -> dict:
    """Layout profile dict matching the simulator (used for demo mode)."""

    def r(n: NormRect) -> list[float]:
        return [n.x, n.y, n.w, n.h]

    return {
        "name": name,
        "question": r(LAYOUT["question"]),
        "answers": r(LAYOUT["answers"]),
        "image": r(LAYOUT["image"]),
        "action": r(LAYOUT["action"]),
        "ref_width": 1280,
        "ref_height": 800,
    }
