"""Session trace: one JSON line per pipeline stage, per question.

capture -> OCR (question, answers, checkbox targets) -> AI answer + confidence -> user decision ->
execution capture (planned clicks) -> verification capture -> click / no click + reason.

Images are crops of the question/answer area only (never the whole screen), with the detected checkboxes
(green = found, orange = estimated) and the click targets (red cross) drawn in. API keys never reach the
engine, so they cannot end up here; every line is additionally passed through `redact`.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from smart360.core.models import Question, Rect
from smart360.storage.secrets import redact

log = logging.getLogger(__name__)


class SessionTrace:
    def __init__(self, directory: Path, images: bool = True, max_images: int = 600, max_sessions: int = 20):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.session = time.strftime("%Y%m%d-%H%M%S")
        self.path = self.dir / f"session-{self.session}.jsonl"
        self.images = images
        self.max_images = max_images
        self._lock = threading.Lock()
        self._numbers: dict[str, int] = {}
        self._prune(max_sessions)

    # ------------------------------------------------------------------ numbering
    def number(self, question_id: str | None) -> int | None:
        if not question_id:
            return None
        with self._lock:
            if question_id not in self._numbers:
                self._numbers[question_id] = len(self._numbers) + 1
            return self._numbers[question_id]

    # ------------------------------------------------------------------ writing
    def record(self, stage: str, /, **data: Any) -> None:
        line = {"t": round(time.time(), 3), "session": self.session, "stage": stage,
                "n": self.number(data.get("question_id")), **data}
        text = redact(json.dumps(line, ensure_ascii=False, default=str))
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(text + "\n")

    def image(
        self,
        name: str,
        frame: Image.Image,
        frame_rect: Rect,
        question: Question | None,
        marks: list[dict[str, Any]] | None = None,
        band: Rect | None = None,
    ) -> str | None:
        """Saves the question/answer area of `frame` with targets drawn in. Returns the file name."""
        if not self.images:
            return None
        img = frame.convert("RGB").copy()
        d = ImageDraw.Draw(img)
        ox, oy = frame_rect.x, frame_rect.y
        if question is not None:
            for a in question.answers:
                if a.checkbox is None:
                    continue
                c = a.checkbox
                color = (16, 160, 90) if a.checkbox_found else (230, 140, 0)
                d.rectangle((c.x - ox, c.y - oy, c.x - ox + c.w, c.y - oy + c.h), outline=color, width=2)
                d.text((c.x - ox + c.w + 3, c.y - oy - 2), str(a.index), fill=color)
        for m in marks or []:
            x, y = m["x"] - ox, m["y"] - oy
            col = (220, 30, 30) if not m.get("blocked") else (120, 120, 120)
            d.line((x - 14, y, x + 14, y), fill=col, width=3)
            d.line((x, y - 14, x, y + 14), fill=col, width=3)
            d.ellipse((x - 5, y - 5, x + 5, y + 5), outline=col, width=2)
        if band is not None:
            box = (band.x - ox, band.y - oy, band.x - ox + band.w, band.y - oy + band.h)
            pad = 24
            img = img.crop((max(0, box[0] - pad), max(0, box[1] - pad),
                            min(img.width, box[2] + pad), min(img.height, box[3] + pad)))
        fname = f"{self.session}-{name}.png"
        img.save(self.dir / fname, optimize=True)
        self._prune_images()
        return fname

    # ------------------------------------------------------------------ housekeeping
    def _prune(self, max_sessions: int) -> None:
        sessions = sorted(self.dir.glob("session-*.jsonl"))
        for old in sessions[:-max_sessions] if len(sessions) > max_sessions else []:
            try:
                old.unlink()
            except OSError:
                pass

    def _prune_images(self) -> None:
        files = sorted(self.dir.glob("*.png"), key=lambda p: p.stat().st_mtime)
        for old in files[: max(0, len(files) - self.max_images)]:
            try:
                old.unlink()
            except OSError:
                pass


def read_trace(path: Path) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            lines.append(json.loads(raw))
        except json.JSONDecodeError:
            continue  # a line cut off by a crash must not break the protocol
    return lines


def latest_trace(directory: Path) -> Path | None:
    files = sorted(Path(directory).glob("session-*.jsonl"))
    return files[-1] if files else None
