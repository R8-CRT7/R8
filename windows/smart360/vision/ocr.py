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

# subprocess is used only to run the tesseract binary with a fixed argv (no shell)
import subprocess  # nosec B404
import sys
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps

from smart360.core.models import Rect

log = logging.getLogger(__name__)

# Tesseract spawns OpenMP threads that busy-wait. With concurrent OCR calls this oversubscribes the
# CPU (observed: load average 85, single calls taking >10 min). One thread per process is what the
# Tesseract docs recommend for parallel use - and our crops are small.
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
OCR_TIMEOUT_S = 15.0


class OcrTimeout(RuntimeError):
    pass


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
            # no sharpening: A/B-tested (docs/DECISIONS.md D-07) - it amplifies JPEG artefacts and
            # does not help lossless screen captures
            g = g.resize((int(g.width * scale), int(g.height * scale)), Image.Resampling.LANCZOS)
    return g, scale


class TesseractOcr(OcrBackend):
    """Runs the tesseract CLI directly (TSV output).

    Not via pytesseract: its cleanup globs a unique temp-file pattern per call, and fnmatch caches every
    compiled pattern (LRU, 32 768 entries) - the soak test measured ~5 KB of growth per question.
    """

    name = "tesseract"

    def __init__(self, lang: str = "deu", cmd: str | None = None):
        self.lang = lang
        self.cmd = cmd
        self._available: bool | None = None

    def _binary(self) -> str | None:
        if self.cmd:
            return self.cmd
        found = shutil.which("tesseract")
        if found:
            return found
        if sys.platform == "win32":
            default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(default):
                return default
        return None

    def available(self) -> bool:
        if self._available is None:
            binary = self._binary()
            try:
                if binary is None:
                    raise FileNotFoundError("tesseract binary not found")
                out = subprocess.run(  # noqa: S603 - fixed argv, no shell
                    [binary, "--list-langs"], capture_output=True, text=True, timeout=10, check=True
                ).stdout.split()
                langs = [x for x in out if not x.endswith(":")]
                if self.lang not in langs:
                    self.lang = "eng" if "eng" in langs else (langs[0] if langs else self.lang)
                self.cmd = binary
                self._available = True
            except (OSError, subprocess.SubprocessError, ValueError) as exc:
                log.info("tesseract unavailable: %s", exc)
                self._available = False
        return self._available

    def _run_tsv(self, img: Image.Image) -> list[dict[str, str]]:
        if not self.available() or self.cmd is None:  # lazy: resolves the binary path on first use
            raise RuntimeError("tesseract is not available")
        with tempfile.TemporaryDirectory(prefix="360smart-ocr-") as tmp:
            src = os.path.join(tmp, "in.png")
            img.save(src)
            try:
                proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
                    [self.cmd, src, "stdout", "-l", self.lang, "--psm", "6", "tsv"],
                    capture_output=True,
                    timeout=OCR_TIMEOUT_S,
                    check=False,
                )
            except subprocess.TimeoutExpired as e:
                raise OcrTimeout(f"tesseract timed out after {OCR_TIMEOUT_S:.0f} s") from e
        if proc.returncode != 0:
            raise RuntimeError(f"tesseract failed ({proc.returncode}): {proc.stderr[:200]!r}")
        rows = proc.stdout.decode("utf-8", errors="replace").splitlines()
        if not rows:
            return []
        header = rows[0].split("\t")
        return [dict(zip(header, r.split("\t"), strict=False)) for r in rows[1:]]

    def recognize(self, img: Image.Image) -> list[OcrLine]:
        prepared, scale = _prepare(img)
        lines: dict[tuple[str, str, str], list[dict[str, str]]] = {}
        for row in self._run_tsv(prepared):
            word = (row.get("text") or "").strip()
            if row.get("level") != "5" or not word:
                continue
            key = (row["block_num"], row["par_num"], row["line_num"])
            lines.setdefault(key, []).append(row)
        out: list[OcrLine] = []
        for words in lines.values():
            text = " ".join(w["text"].strip() for w in words)
            # a line of pure noise (checkbox borders read as "|" / "O" / "[]") is dropped
            if len(text.strip(" |[]()_-—–.,:;'\"")) == 0:
                continue
            confs = [float(w["conf"]) for w in words if float(w["conf"]) >= 0]
            x0 = min(int(w["left"]) for w in words)
            y0 = min(int(w["top"]) for w in words)
            x1 = max(int(w["left"]) + int(w["width"]) for w in words)
            y1 = max(int(w["top"]) + int(w["height"]) for w in words)
            bbox = Rect(int(x0 / scale), int(y0 / scale), int((x1 - x0) / scale), int((y1 - y0) / scale))
            out.append(OcrLine(text, bbox, (sum(confs) / len(confs) / 100.0) if confs else 0.5))
        out.sort(key=lambda line: (line.bbox.y, line.bbox.x))
        return out


class WindowsOcr(OcrBackend):
    """Windows.Media.Ocr. Requires the winrt-* packages (installed by the Windows build)."""

    name = "windows"

    def __init__(self, language: str = "de-DE"):
        self.language = language
        # One OcrEngine per thread: an engine rejects a second concurrent RecognizeAsync
        # ("Another RecognizeAsync operation is already running!"), and the extractor OCRs the
        # question and answer regions in parallel (found by the native Windows CI test).
        self._local = threading.local()
        self._available: bool | None = None

    def _create_engine(self):  # type: ignore[no-untyped-def]
        from winrt.windows.globalization import Language
        from winrt.windows.media.ocr import OcrEngine

        engine = None
        if OcrEngine.is_language_supported(Language(self.language)):
            engine = OcrEngine.try_create_from_language(Language(self.language))
        if engine is None:
            engine = OcrEngine.try_create_from_user_profile_languages()
        return engine

    def _thread_engine(self):  # type: ignore[no-untyped-def]
        engine = getattr(self._local, "engine", None)
        if engine is None:
            engine = self._local.engine = self._create_engine()
        return engine

    def available(self) -> bool:
        if self._available is not None:
            return self._available
        if sys.platform != "win32":
            self._available = False
            return False
        try:
            self._available = self._thread_engine() is not None
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

        engine = self._thread_engine()
        if engine is None:
            raise RuntimeError("Windows OCR engine could not be created")

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
