"""Question extraction: frame + layout profile + OCR -> Question.

The profile defines normalized regions relative to the target window's client area,
so moving/resizing the window keeps working. Answer click targets are derived from
the *current* OCR result every time (never from stale coordinates).
"""

from __future__ import annotations

import itertools
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from smart360.core.imaging import clarity, content_variance, dhash, encode_png
from smart360.core.models import AnswerOption, NormRect, Question, QuestionType, Rect
from smart360.vision.ocr import OcrBackend, OcrLine

_OCR_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ocr")


@dataclass(frozen=True, slots=True)
class LayoutProfile:
    name: str
    question: NormRect
    answers: NormRect
    image: NormRect | None = None
    action: NormRect | None = None  # e.g. the "next" button, used only with auto-advance flag
    # reference client size when calibrated (used for automatic profile choice)
    ref_width: int = 1920
    ref_height: int = 1080

    def to_dict(self) -> dict:
        def r(n: NormRect | None):  # type: ignore[no-untyped-def]
            return None if n is None else [n.x, n.y, n.w, n.h]

        return {
            "name": self.name,
            "question": r(self.question),
            "answers": r(self.answers),
            "image": r(self.image),
            "action": r(self.action),
            "ref_width": self.ref_width,
            "ref_height": self.ref_height,
        }

    @staticmethod
    def from_dict(d: dict) -> LayoutProfile:
        def r(v):  # type: ignore[no-untyped-def]
            if v is None:
                return None
            n = NormRect(*map(float, v))
            if not n.is_valid():
                raise ValueError(f"invalid region {v}")
            return n

        q, a = r(d["question"]), r(d["answers"])
        if q is None or a is None:
            raise ValueError("question and answers regions are required")
        return LayoutProfile(
            str(d.get("name", "Profile")),
            q,
            a,
            r(d.get("image")),
            r(d.get("action")),
            int(d.get("ref_width", 1920)),
            int(d.get("ref_height", 1080)),
        )


def choose_profile(profiles: list[LayoutProfile], width: int, height: int) -> LayoutProfile | None:
    """Pick the profile whose calibration size/aspect is closest to the current client area."""
    if not profiles:
        return None
    aspect = width / max(1, height)

    def score(p: LayoutProfile) -> float:
        pa = p.ref_width / max(1, p.ref_height)
        return abs(pa - aspect) * 3 + abs(p.ref_width - width) / max(width, 1)

    return min(profiles, key=score)


_NUMBER_HINT = re.compile(r"(zahl|antwort)\s*[:：]?\s*_*|^_{2,}", re.IGNORECASE)
_UNIT_ONLY = re.compile(
    r"^[\s_]*(m|km/h|km|%|meter|jahre?|cm|t|kg|minuten|stunden|sekunden)?[\s_.]*$", re.IGNORECASE
)
# leading checkbox artefacts read by OCR: "[_]", "[]", "|", "□", "(_)", and blurred boxes read as
# "[DD", "DJ)", "[D)" (a bracket plus box-shaped letters) before the real, capitalised answer text.
# Windows OCR reads an empty checkbox as "C]" / "U]" / "E]" - and not on every capture, which made the
# executor's re-check see a "different question" (found by the native Windows CI test).
_BULLET = re.compile(r"^\s*(?:[\[\](){}|_□☐☑✓✔]{1,4}\s+)+")
_BOX_TOKEN = re.compile(
    r"^\s*(?:[\[\](){}|_]*[DJOo0IlCcUuE]{1,3}[\[\](){}|_]*|[\[\](){}|_]+)\s+(?=[A-ZÄÖÜ0-9!|])"
)
# frequent OCR confusions in this domain
_FIXES = (
    (re.compile(r"\bkm\s*/\s*[nb]\b|\bkmlh\b|\bkm/n\b"), "km/h"),
    (re.compile(r"\s+%"), " %"),
    (re.compile(r"^[!|l1]ch\b"), "Ich"),  # "!ch", "|ch" -> "Ich" at the start of an answer
)


@dataclass(slots=True)
class ExtractionResult:
    question: Question | None
    frame_rect: Rect
    regions: dict[str, Rect] = field(default_factory=dict)
    timings_ms: dict[str, float] = field(default_factory=dict)
    problem: str | None = None


class QuestionExtractor:
    def __init__(self, ocr: OcrBackend, image_variance_threshold: float = 18.0, png_max_side: int = 1024):
        self.ocr = ocr
        self.image_variance_threshold = image_variance_threshold
        self.png_max_side = png_max_side

    def extract(
        self, frame: Image.Image, frame_rect: Rect, profile: LayoutProfile, with_crops: bool = True
    ) -> ExtractionResult:
        """`frame` is the capture of `frame_rect` (window client area, screen coordinates)."""
        timings: dict[str, float] = {}
        local = Rect(0, 0, frame.width, frame.height)
        q_rect = profile.question.to_abs(local)
        a_rect = profile.answers.to_abs(local)
        i_rect = profile.image.to_abs(local) if profile.image else None
        regions = {
            "question": q_rect.translated(frame_rect.x, frame_rect.y),
            "answers": a_rect.translated(frame_rect.x, frame_rect.y),
        }
        if i_rect:
            regions["image"] = i_rect.translated(frame_rect.x, frame_rect.y)

        q_img = _crop(frame, q_rect)
        a_img = _crop(frame, a_rect)
        t0 = time.perf_counter()
        # question and answers are independent: OCR them in parallel (each tesseract call is
        # single-threaded, see ocr.py) - measured 440 ms -> 206 ms median
        a_future = _OCR_POOL.submit(self.ocr.recognize, a_img)
        q_lines = self.ocr.recognize(q_img)
        a_lines = a_future.result()
        timings["ocr"] = (time.perf_counter() - t0) * 1000

        q_text = " ".join(line.text for line in q_lines).strip()
        if len(q_text) < 8:
            return ExtractionResult(None, frame_rect, regions, timings, "no question text")

        t1 = time.perf_counter()
        qtype, answers, layout_conf = self._parse_answers(a_lines, a_rect, frame_rect, a_img)
        if qtype is QuestionType.SINGLE_OR_MULTI and len(answers) < 2:
            return ExtractionResult(None, frame_rect, regions, timings, "answers not found")
        timings["parse"] = (time.perf_counter() - t1) * 1000

        image_hash = None
        has_image = False
        img_clarity = 1.0
        i_img = None
        if i_rect is not None:
            i_img = _crop(frame, i_rect)
            if content_variance(i_img) >= self.image_variance_threshold:
                has_image = True
                image_hash = dhash(i_img)
                img_clarity = clarity(i_img)

        confs = [line.confidence for line in q_lines + a_lines]
        ocr_conf = statistics.fmean(confs) if confs else 0.0
        question = Question(
            text=_clean(q_text),
            answers=tuple(answers),
            question_type=qtype,
            image_hash=image_hash,
            has_image=has_image,
            ocr_confidence=round(ocr_conf, 3),
            layout_confidence=layout_conf,
            image_clarity=round(img_clarity, 3),
            question_png=encode_png(q_img, self.png_max_side) if with_crops else None,
            answers_png=encode_png(a_img, self.png_max_side) if with_crops else None,
            image_png=encode_png(i_img, self.png_max_side) if (with_crops and has_image and i_img) else None,
        )
        timings["total"] = (time.perf_counter() - t0) * 1000
        return ExtractionResult(question, frame_rect, regions, timings)

    # ------------------------------------------------------------------ answers
    def _parse_answers(
        self, lines: list[OcrLine], a_rect: Rect, frame_rect: Rect, a_img: Image.Image
    ) -> tuple[QuestionType, list[AnswerOption], float]:
        joined = " ".join(line.text for line in lines).strip()
        if not lines or (
            len(lines) <= 2
            and (_NUMBER_HINT.search(joined) and _UNIT_ONLY.match(_NUMBER_HINT.sub("", joined)))
        ):
            return QuestionType.NUMBER_INPUT, [], 0.7 if lines else 0.4

        groups = _group_rows(lines)
        answers: list[AnswerOption] = []
        ox, oy = frame_rect.x + a_rect.x, frame_rect.y + a_rect.y
        for idx, group in enumerate(groups, start=1):
            text = _clean(" ".join(line.text for line in group))
            text = _BULLET.sub("", text).strip()
            x0 = min(line.bbox.x for line in group)
            y0 = min(line.bbox.y for line in group)
            x1 = max(line.bbox.x + line.bbox.w for line in group)
            y1 = max(line.bbox.y + line.bbox.h for line in group)
            first = group[0]
            row = Rect(x0, y0, x1 - x0, y1 - y0)
            cb_local = _find_checkbox(a_img, first.bbox, row)
            answers.append(
                AnswerOption(
                    index=idx,
                    text=text,
                    bbox=row.translated(ox, oy),
                    checkbox=cb_local.translated(ox, oy),
                    ocr_confidence=statistics.fmean(line.confidence for line in group),
                )
            )
        n = len(answers)
        layout_conf = 1.0 if n == 3 else (0.75 if n in (2, 4) else 0.35)
        return QuestionType.SINGLE_OR_MULTI, answers, layout_conf


def _looks_like_number_input(lines: list[OcrLine], joined: str) -> bool:
    """'Antwort: [____] m' - one short line, an 'Antwort' label or unit, no answer sentence."""
    if len(lines) > 2:
        return False
    if _NUMBER_HINT.search(joined) and _UNIT_ONLY.match(_NUMBER_HINT.sub("", joined)):
        return True
    words = [w for w in re.findall(r"[A-Za-zÄÖÜäöüß]{2,}", joined)]
    return "antwort" in joined.lower() and len(words) <= 3


def _crop(img: Image.Image, r: Rect) -> Image.Image:
    x0 = max(0, min(img.width - 1, r.x))
    y0 = max(0, min(img.height - 1, r.y))
    x1 = max(x0 + 1, min(img.width, r.x + r.w))
    y1 = max(y0 + 1, min(img.height, r.y + r.h))
    return img.crop((x0, y0, x1, y1))


def _clean(text: str) -> str:
    text = _BULLET.sub("", text)
    token = _BOX_TOKEN.match(text)
    if token and any(ch in token.group(0) for ch in "[](){}|_"):
        text = text[token.end() :]
    for rx, repl in _FIXES:
        text = rx.sub(repl, text)
    text = text.replace("|", " ").replace("—", "-")
    text = re.sub(r"\s+([?.,!:;])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _group_rows(lines: list[OcrLine]) -> list[list[OcrLine]]:
    """Wrapped answer lines belong to the same option: split on large vertical gaps."""
    if not lines:
        return []
    lines = sorted(lines, key=lambda line: line.bbox.y)
    heights = [line.bbox.h for line in lines if line.bbox.h > 0]
    h = statistics.median(heights) if heights else 14
    groups: list[list[OcrLine]] = [[lines[0]]]
    for prev, cur in itertools.pairwise(lines):
        gap = cur.bbox.y - (prev.bbox.y + prev.bbox.h)
        indent_jump = cur.bbox.x < prev.bbox.x - 0.8 * h  # new row starts further left (checkbox column)
        if gap > 0.9 * h or (gap > 0.45 * h and indent_jump):
            groups.append([cur])
        else:
            groups[-1].append(cur)
    return groups


def _find_checkbox(a_img: Image.Image, first_line: Rect, row: Rect) -> Rect:
    """Locate the checkbox left of the first text line: the darkest-edge square in the band
    between the region's left border and the text start. Falls back to the band centre."""
    band_x1 = max(1, first_line.x - 2)
    cy = first_line.y + first_line.h // 2
    size = max(10, int(first_line.h * 1.3))
    if band_x1 < size // 2:
        # no room left of the text: click the start of the text row itself
        return Rect(first_line.x, cy - size // 2, size, size)
    y0 = max(0, cy - size)
    y1 = min(a_img.height, cy + size)
    band = np.asarray(a_img.convert("L").crop((0, y0, band_x1, y1)), dtype=np.float32)
    if band.size == 0:
        return Rect(band_x1 // 2 - size // 2, cy - size // 2, size, size)
    edges = np.abs(np.diff(band, axis=1)).sum(axis=0)
    if edges.max() < 200:
        cx = band_x1 // 2
    else:
        cols = np.where(edges > edges.max() * 0.5)[0]
        cx = int((cols.min() + cols.max()) / 2)
    return Rect(max(0, cx - size // 2), cy - size // 2, size, size)
