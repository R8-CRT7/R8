"""OCR benchmark on 360°-style practice screens.

Measures, per available backend: question text similarity, exact answer extraction rate,
answer count accuracy and latency across display scalings and degradations (JPEG, blur).

    python tools/ocr_benchmark.py [--out artifacts/ocr_benchmark.json]
"""

from __future__ import annotations

import argparse
import io
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageFilter
from rapidfuzz import fuzz

from smart360.capture.simulator import PracticeSimulator, simulator_profile
from smart360.core.models import normalize_text
from smart360.vision.extractor import LayoutProfile, QuestionExtractor
from smart360.vision.ocr import TesseractOcr, WindowsOcr

SCALES = {"75%": (960, 600), "100%": (1280, 800), "125%": (1600, 1000), "150%": (1920, 1200)}


def degrade(img: Image.Image, kind: str) -> Image.Image:
    if kind == "jpeg":
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=35)
        return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    if kind == "blur":
        return img.filter(ImageFilter.GaussianBlur(1.1))
    return img


def run(backend) -> dict:  # type: ignore[no-untyped-def]
    prof = LayoutProfile.from_dict(simulator_profile())
    ex = QuestionExtractor(backend)
    results = []
    for scale, (w, h) in SCALES.items():
        for kind in ("clean", "jpeg", "blur"):
            sim = PracticeSimulator(width=w, height=h, shuffle=True, seed=3)
            for i in range(len(sim.bank)):
                sim.goto(i)
                img = degrade(sim.render(), kind)
                t0 = time.perf_counter()
                res = ex.extract(img, sim.rect, prof, with_crops=False)
                ms = (time.perf_counter() - t0) * 1000
                q = res.question
                truth_q = normalize_text(sim.question.text)
                truth_a = [normalize_text(a) for a in sim.displayed_answers()]
                if q is None:
                    results.append({"scale": scale, "kind": kind, "ok": False, "q_sim": 0, "answers_exact": False,
                                    "count_ok": False, "ms": ms})
                    continue
                got_a = list(q.normalized_answers)
                results.append({
                    "scale": scale, "kind": kind, "ok": True,
                    "q_sim": fuzz.ratio(q.normalized_text, truth_q) / 100,
                    "answers_exact": got_a == truth_a,
                    "count_ok": len(got_a) == len(truth_a),
                    "ms": ms,
                })

    def agg(rows: list[dict]) -> dict:
        return {
            "n": len(rows),
            "detected": round(sum(r["ok"] for r in rows) / len(rows), 3),
            "question_similarity": round(statistics.fmean(r["q_sim"] for r in rows), 4),
            "answers_exact": round(sum(r["answers_exact"] for r in rows) / len(rows), 3),
            "answer_count_ok": round(sum(r["count_ok"] for r in rows) / len(rows), 3),
            "median_ms": round(statistics.median(r["ms"] for r in rows), 1),
            "p95_ms": round(sorted(r["ms"] for r in rows)[int(len(rows) * 0.95) - 1], 1),
        }

    out = {"overall": agg(results)}
    for key in ("scale", "kind"):
        for val in sorted({r[key] for r in results}):
            out[f"{key}={val}"] = agg([r for r in results if r[key] == val])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("artifacts/ocr_benchmark.json"))
    args = ap.parse_args()
    report = {}
    for backend in (WindowsOcr(), TesseractOcr()):
        if backend.available():
            print(f"benchmarking {backend.name} …", flush=True)
            report[backend.name] = run(backend)
        else:
            report[backend.name] = "unavailable on this machine"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
