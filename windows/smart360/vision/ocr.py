"""OCR backends.

* WindowsOcr   - Windows.Media.Ocr via pywinrt. Built into Windows 10/11, offline, fast,
                 no extra install. Preferred on Windows. (No per-word confidence API.)
* TesseractOcr - pytesseract + tesseract binary. Cross-platform, gives confidences.
                 Used on Linux CI/dev and as Windows fallback if installed.
* NullOcr      - reports unavailability; the pipeline then falls back to vision-only AI.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps

from smart360.core.models import Rect

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OcrLine:
    text: str
    bbox: Rect  # relative to the image passed to recognize()
    confidence: float  # 0..1


class OcrBackend(ABC):
    name = "base"

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def recognize(self, img: Image.Image) -> list[OcrLine]: ...


def _prepare(img: Image.Image, min_height: int = 900) -> tuple[Image.Image, float]:
    """Grayscale, auto-contrast, invert dark themes, upscale small crops. Returns (img, scale)."""
    g = img.convert("L")
    # dark UI (light text on dark background) -> invert for OCR engines trained on dark-on-light
    small = g.resize((32, 32))
    if float(np.asarray(small).mean()) < 110:
        g = ImageOps.invert(g)
    g = ImageOps.autocontrast(g, cutoff=1)
    scale = 1.0
    if g.height < min_height and g.height > 0:
        scale = min(3.0, max(1.0, min_height / g.height))
        if scale > 1.05:
            g = g.resize((int(g.width * scale), int(g.height * scale)), Image.Resampling.LANCZOS)
    return g, scale


class TesseractOcr(OcrBackend):
    name = "tesseract"

    def __init__(self, lang: str = "deu", cmd: str | None = None):
        self.lang = lang
        self.cmd = cmd
        self._available: bool | None = None

    def available(self) -> bool:
        if self._available is None:
            try:
                import pytesseract

                if self.cmd:
                    pytesseract.pytesseract.tesseract_cmd = self.cmd
                elif sys.platform == "win32" and not shutil.which("tesseract"):
                    default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
                    if os.path.exists(default):
                        pytesseract.pytesseract.tesseract_cmd = default
                langs = pytesseract.get_languages(config="")
                if self.lang not in langs:
                    self.lang = "eng" if "eng" in langs else (langs[0] if langs else self.lang)
                self._available = True
            except Exception as exc:
                log.info("tesseract unavailable: %s", exc)
                self._available = False
        return self._available

    def recognize(self, img: Image.Image) -> list[OcrLine]:
        import pytesseract

        prepared, scale = _prepare(img)
        data = pytesseract.image_to_data(
            prepared, lang=self.lang, config="--psm 6", output_type=pytesseract.Output.DICT
        )
        lines: dict[tuple[int, int, int], list[int]] = {}
        for i, word in enumerate(data["text"]):
            if not word or not word.strip():
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(i)
        out: list[OcrLine] = []
        for idxs in lines.values():
            words = [data["text"][i].strip() for i in idxs]
            confs = [float(data["conf"][i]) for i in idxs if float(data["conf"][i]) >= 0]
            x0 = min(data["left"][i] for i in idxs)
            y0 = min(data["top"][i] for i in idxs)
            x1 = max(data["left"][i] + data["width"][i] for i in idxs)
            y1 = max(data["top"][i] + data["height"][i] for i in idxs)
            bbox = Rect(int(x0 / scale), int(y0 / scale), int((x1 - x0) / scale), int((y1 - y0) / scale))
            text = " ".join(words)
            # a line of pure noise (checkbox borders read as "|" / "O" / "[]") is dropped
            if len(text.strip(" |[]()_-—–.,:;'\"")) == 0:
                continue
            out.append(OcrLine(text, bbox, (sum(confs) / len(confs) / 100.0) if confs else 0.5))
        out.sort(key=lambda line: (line.bbox.y, line.bbox.x))
        return out


class WindowsOcr(OcrBackend):
    """Windows.Media.Ocr. Requires the winrt-* packages (installed by the Windows build)."""

    name = "windows"

    def __init__(self, language: str = "de-DE"):
        self.language = language
        self._engine = None
        self._available: bool | None = None

    def available(self) -> bool:
        if self._available is not None:
            return self._available
        if sys.platform != "win32":
            self._available = False
            return False
        try:
            from winrt.windows.globalization import Language
            from winrt.windows.media.ocr import OcrEngine

            engine = None
            if OcrEngine.is_language_supported(Language(self.language)):
                engine = OcrEngine.try_create_from_language(Language(self.language))
            if engine is None:
                engine = OcrEngine.try_create_from_user_profile_languages()
            self._engine = engine
            self._available = engine is not None
        except Exception as exc:
            log.info("Windows OCR unavailable: %s", exc)
            self._available = False
        return bool(self._available)

    def recognize(self, img: Image.Image) -> list[OcrLine]:
        import asyncio

        from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
        from winrt.windows.storage.streams import DataWriter

        if not self.available():
            raise RuntimeError("Windows OCR not available")
        prepared, scale = _prepare(img, min_height=600)
        rgba = prepared.convert("RGBA")
        b, g, r, a = rgba.split()[2], rgba.split()[1], rgba.split()[0], rgba.split()[3]
        bgra = Image.merge("RGBA", (b, g, r, a)).tobytes()
        writer = DataWriter()
        writer.write_bytes(bgra)
        bmp = SoftwareBitmap(BitmapPixelFormat.BGRA8, rgba.width, rgba.height, BitmapAlphaMode.PREMULTIPLIED)
        bmp.copy_from_buffer(writer.detach_buffer())

        engine = self._engine
        assert engine is not None

        async def run():  # type: ignore[no-untyped-def]
            return await engine.recognize_async(bmp)

        result = asyncio.run(run())
        out: list[OcrLine] = []
        for line in result.lines:
            rects = [w.bounding_rect for w in line.words]
            if not rects:
                continue
            x0 = min(r.x for r in rects)
            y0 = min(r.y for r in rects)
            x1 = max(r.x + r.width for r in rects)
            y1 = max(r.y + r.height for r in rects)
            bbox = Rect(int(x0 / scale), int(y0 / scale), int((x1 - x0) / scale), int((y1 - y0) / scale))
            # Windows OCR exposes no confidence; use a calibrated constant, lowered for
            # suspicious lines (very short, many non-letters).
            text = line.text
            letters = sum(c.isalnum() for c in text)
            conf = 0.9 if letters >= max(2, len(text) * 0.6) else 0.6
            out.append(OcrLine(text, bbox, conf))
        out.sort(key=lambda line: (line.bbox.y, line.bbox.x))
        return out


class NullOcr(OcrBackend):
    name = "none"

    def available(self) -> bool:
        return False

    def recognize(self, img: Image.Image) -> list[OcrLine]:
        return []


def select_backend(preference: str = "auto") -> OcrBackend:
    """auto: Windows OCR on Windows, else Tesseract, else Null."""
    order: list[OcrBackend]
    if preference == "windows":
        order = [WindowsOcr(), TesseractOcr()]
    elif preference == "tesseract":
        order = [TesseractOcr(), WindowsOcr()]
    else:
        order = [WindowsOcr(), TesseractOcr()]
    for b in order:
        t0 = time.perf_counter()
        if b.available():
            log.info("OCR backend %s ready (%.0f ms)", b.name, (time.perf_counter() - t0) * 1000)
            return b
    return NullOcr()
