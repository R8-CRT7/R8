"""Write reports/contradiction_index.json - the relations the prove-false engine uses (built from the KB only).

    python tools/contradiction_index.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smart360.theory.contradiction import build_index
from smart360.theory.kb import KnowledgeBase

ROOT = Path(__file__).resolve().parents[2]

if __name__ == "__main__":
    idx = build_index(KnowledgeBase.load())
    out = ROOT / "reports" / "contradiction_index.json"
    out.write_text(idx.to_json(), encoding="utf-8")
    print(f"{len(idx.relations)} relations -> {out}")
    for (rel, origin), n in sorted(Counter((r.relation, r.origin) for r in idx.relations).items()):
        print(f"  {rel:18} {origin:14} {n}")
