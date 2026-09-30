"""Very subtle UI sounds, synthesized at startup (no audio assets). Off by default."""

from __future__ import annotations

import logging
import math
import struct
import tempfile
import wave
from pathlib import Path

log = logging.getLogger(__name__)

TONES = {
    # name: [(freq Hz, duration s)], soft sine blips with an exponential decay
    "ready": [(880.0, 0.07), (1318.5, 0.11)],
    "confirm": [(659.3, 0.06), (987.8, 0.09)],
    "error": [(311.1, 0.12), (233.1, 0.16)],
}


def _synth(path: Path, notes: list[tuple[float, float]], rate: int = 44100, volume: float = 0.18) -> None:
    frames = bytearray()
    for freq, dur in notes:
        n = int(rate * dur)
        for i in range(n):
            t = i / rate
            env = math.exp(-t * 18) * min(1.0, i / (rate * 0.004))
            frames += struct.pack("<h", int(32767 * volume * env * math.sin(2 * math.pi * freq * t)))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


class SoundBoard:
    def __init__(self) -> None:
        self.enabled = False
        self._effects: dict[str, object] = {}
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect

            d = Path(tempfile.mkdtemp(prefix="360smart-snd-"))
            for name, notes in TONES.items():
                p = d / f"{name}.wav"
                _synth(p, notes)
                eff = QSoundEffect()
                eff.setSource(QUrl.fromLocalFile(str(p)))
                eff.setVolume(0.35)
                self._effects[name] = eff
        except Exception as e:  # no audio backend (e.g. CI) -> silent
            log.info("sounds unavailable: %s", e)

    def play(self, name: str) -> None:
        if not self.enabled:
            return
        eff = self._effects.get(name)
        if eff is not None:
            try:
                eff.play()  # type: ignore[attr-defined]
            except Exception:
                pass
