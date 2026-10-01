"""Import externally written theory questions into tests/theory/golden_external/ (READ-ONLY afterwards).

    python tools/external_import.py NEW.json [--dry-run]

Checks, in this order (any hard error -> nothing is written):
    format        id, topic (one of the 14 keys), question, answers, correct (1-based, pointing into answers)
                  or number, source ("external-..."), author (non-empty)
    unique ids    within the file and against everything imported before
    duplicates    the same normalised question (+ options) twice, within the file or against earlier imports
    leakage       lexical + normalised semantic similarity against claims, generator items, development golden,
                  lexicon and prompt texts (smart360/theory/leakage.py). Similar items are imported but marked
                  POSSIBLE_LEAKAGE and excluded from the independent main metric.

Imported files are never edited again: their sha256 is recorded in MANIFEST.json and checked by the evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError

from smart360.theory import leakage, splits
from smart360.theory.text import fold


def _norm(q: str, answers: list[str]) -> str:
    return re.sub(r"\W+", " ", fold(q + " | " + " | ".join(sorted(answers)))).strip()


def validate(raw_items: list[dict], existing: list[splits.ExternalItem]) -> tuple[list[splits.ExternalItem], list[str]]:
    errors: list[str] = []
    items: list[splits.ExternalItem] = []
    ids = {e.id for e in existing}
    seen_norm = {_norm(e.question, e.answers): e.id for e in existing}
    for n, raw in enumerate(raw_items, start=1):
        try:
            it = splits.ExternalItem.model_validate(raw)
            it.to_item()
        except (ValidationError, ValueError) as exc:
            errors.append(f"item {n} ({raw.get('id', '?')}): {exc}".replace("\n", " "))
            continue
        if it.id in ids:
            errors.append(f"{it.id}: id already used")
            continue
        key = _norm(it.question, it.answers)
        if key in seen_norm:
            errors.append(f"{it.id}: duplicate of {seen_norm[key]}")
            continue
        ids.add(it.id)
        seen_norm[key] = it.id
        items.append(it)
    return items, errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    data = json.loads(a.file.read_text(encoding="utf-8"))
    raw_items = data["items"] if isinstance(data, dict) else data
    existing = splits.load_external_records(purpose="import_check")
    items, errors = validate(raw_items, existing)
    if errors:
        print("REJECTED - nothing imported:")
        for e in errors:
            print("  ", e)
        return 1
    corpus = leakage.default_corpus()
    out = []
    for it in items:
        rep = leakage.check_item(it.id, it.question, it.answers, corpus)
        rec = it.model_copy(update={"leakage": leakage.POSSIBLE_LEAKAGE if rep.leak else "",
                                    "leakage_detail": rep.detail if rep.leak else ""})
        out.append(rec)
        print(f"{it.id}: {'POSSIBLE_LEAKAGE ' + rep.detail if rep.leak else 'independent'}")
    n_leak = sum(1 for r in out if r.leakage)
    print(f"{len(out)} valid, {n_leak} POSSIBLE_LEAKAGE (kept, excluded from the independent metric)")
    if a.dry_run:
        return 0
    target = splits.EXTERNAL_DIR / f"external_{time.strftime('%Y%m%d_%H%M%S')}.json"
    body = json.dumps({"items": [r.model_dump(exclude_defaults=False) for r in out]}, ensure_ascii=False, indent=1) + "\n"
    target.write_text(body, encoding="utf-8")
    man_p = splits.EXTERNAL_DIR / splits.MANIFEST
    manifest = json.loads(man_p.read_text(encoding="utf-8")) if man_p.exists() else {"files": {}}
    manifest["files"][target.name] = hashlib.sha256(body.replace("\r\n", "\n").encode("utf-8")).hexdigest()
    man_p.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(f"written {target.name}; manifest updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
