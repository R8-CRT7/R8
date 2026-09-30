"""Image utilities: perceptual hashing, clarity, change detection helpers.

Implemented with numpy + Pillow only (no scipy/imagehash dependency). dHash is
robust to scaling and small colour shifts, fast (<1 ms for a 1080p crop) and is
what we need for "same screen?" and "same situation image?" questions.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageFilter


def to_gray_array(img: Image.Image, size: tuple[int, int] | None = None) -> np.ndarray:
    g = img.convert("L")
    if size is not None:
        g = g.resize(size, Image.Resampling.BILINEAR)
    return np.asarray(g, dtype=np.float32)


def dhash(img: Image.Image, hash_size: int = 8) -> int:
    """Difference hash (64 bit for hash_size=8)."""
    a = to_gray_array(img, (hash_size + 1, hash_size))
    diff = a[:, 1:] > a[:, :-1]
    value = 0
    for bit in diff.flatten():
        value = (value << 1) | int(bit)
    return value


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def region_signature(img: Image.Image) -> np.ndarray:
    """Small grayscale thumbnail used for cheap frame differencing (160x90: fine enough that two
    similar-looking questions with different text still differ, see changed_fraction)."""
    return to_gray_array(img, (160, 90))


def changed_fraction(a: np.ndarray, b: np.ndarray, level: float = 24.0) -> float:
    """Share of pixels that changed clearly. Catches text changes that a mean difference averages away."""
    if a.shape != b.shape:
        return 1.0
    return float(np.mean(np.abs(a - b) > level))


def mean_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        return 255.0
    return float(np.mean(np.abs(a - b)))


def clarity(img: Image.Image) -> float:
    """0..1 sharpness estimate (variance of Laplacian, squashed). Blurry/tiny crops
    get low values, which lowers composite confidence."""
    g = img.convert("L")
    if g.width < 8 or g.height < 8:
        return 0.0
    if g.width > 800:
        g = g.resize((800, max(8, int(g.height * 800 / g.width))))
    lap = np.asarray(g.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    var = float(lap.var())
    return float(min(1.0, var / 1500.0))


def content_variance(img: Image.Image) -> float:
    """Std-dev of luminance. Used to decide if an 'image area' actually has an image."""
    return float(to_gray_array(img, (96, 54)).std())


def encode_png(img: Image.Image, max_side: int | None = None) -> bytes:
    if max_side and max(img.size) > max_side:
        scale = max_side / max(img.size)
        img = img.resize(
            (max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.Resampling.LANCZOS
        )
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def checkbox_fill(img: Image.Image) -> float:
    """Mean darkness-contrast of a checkbox crop (used by the verifier)."""
    a = to_gray_array(img)
    if a.size == 0:
        return 0.0
    return float(a.std())
