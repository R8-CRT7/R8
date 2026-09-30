"""Generate the app icon (Neural Pulse orb) as a multi-resolution .ico + .png (Pillow only)."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "smart360" / "assets"


def orb(size: int) -> Image.Image:
    s = size * 4  # supersample
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    # rounded dark tile
    tile = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.23), fill=(9, 14, 20, 255))
    img.alpha_composite(tile)
    # halo
    halo = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    c = s / 2
    for i in range(40, 0, -1):
        r = s * 0.12 + i * s * 0.0085
        a = int(10 + (40 - i) * 4.2)
        hd.ellipse((c - r, c - r, c + r, c + r), fill=(48, 213, 255, min(255, a // 2)))
    halo = halo.filter(ImageFilter.GaussianBlur(s * 0.03))
    img.alpha_composite(halo)
    # core with a highlight (radial gradient by hand)
    core = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    px = core.load()
    R = s * 0.23
    hx, hy = c - R * 0.35, c - R * 0.4
    for y in range(int(c - R) - 1, int(c + R) + 2):
        for x in range(int(c - R) - 1, int(c + R) + 2):
            d = math.hypot(x - c, y - c)
            if d > R:
                continue
            t = min(1.0, math.hypot(x - hx, y - hy) / (R * 1.35))
            if t < 0.28:
                k = t / 0.28
                col = (int(255 + (48 - 255) * k), int(255 + (213 - 255) * k), 255)
            else:
                k = (t - 0.28) / 0.72
                col = (int(48 + (70 - 48) * k), int(213 + (80 - 213) * k), int(255 + (190 - 255) * k))
            edge = max(0.0, min(1.0, (R - d) / (s * 0.006)))
            px[x, y] = (*col, int(255 * edge))
    img.alpha_composite(core)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    big = orb(256)
    big.save(OUT / "icon.png")
    big.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    orb(1024).save(OUT / "icon-1024.png")
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
