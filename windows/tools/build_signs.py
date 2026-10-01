"""Build knowledge/signs.json from the official StVO snapshot (Anlagen 1-4) plus own short meanings.

Every sign cites its row in the official snapshot with a verbatim excerpt (sign number + official name and,
where present, the first sentence of its 'Ge- oder Verbot'). Meanings are own short summaries from
knowledge/curation/signs_curated.json; signs without a curated meaning get only their official name.

    python tools/build_signs.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / "knowledge" / "sources" / "snapshots" / "stvo_2013.json"
CUR = ROOT / "knowledge" / "curation" / "signs_curated.json"
OUT = ROOT / "knowledge" / "signs.json"
CATEGORY = {"Anlage 1": "Gefahrzeichen", "Anlage 2": "Vorschriftzeichen", "Anlage 3": "Richtzeichen",
            "Anlage 4": "Verkehrseinrichtung"}


def _first_rule(text: str) -> str:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    try:
        i = lines.index("Ge- oder Verbot")
    except ValueError:
        return ""
    for ln in lines[i + 1:]:
        if re.fullmatch(r"\d+\.|[a-z]\)", ln):
            continue
        if ln in ("Erläuterung",):
            return ""
        return ln
    return ""


def _group_rows(norms: dict, key: str) -> list[tuple[str, str]]:
    """Rules that the Anlage states once for several rows ('lfd. Nr. Zu 53, 54 und 54.4' / 'zu 5 bis 7')."""
    anlage, nr = key.split(" Nr. ", 1)
    try:
        me = float(nr)
    except ValueError:
        return []
    out = []
    for k, n in norms.items():
        if not k.startswith(anlage + " Nr. ") or not re.match(r"[Zz]u ", k.split(" Nr. ", 1)[1]):
            continue
        spec = k.split(" Nr. ", 1)[1][3:]
        hit = False
        for a, b in re.findall(r"(\d+(?:\.\d+)?)\s*bis\s*(\d+(?:\.\d+)?)", spec):
            hit |= float(a) <= me <= float(b)
        hit |= me in [float(x) for x in re.findall(r"\d+(?:\.\d+)?", re.sub(r"\d+(?:\.\d+)?\s*bis\s*\d+(?:\.\d+)?", "", spec))]
        rule = _first_rule(n["text"])
        if hit and rule:
            out.append((k, rule))
    return out


def build() -> dict:
    snap = json.loads(SNAP.read_text(encoding="utf-8"))
    cur = json.loads(CUR.read_text(encoding="utf-8"))["signs"]
    items = []
    for number, key in snap["sign_index"].items():
        norm = snap["norms"][key]
        text = norm["text"]
        head = text.split("\n", 1)[0].strip()
        m = re.search(rf"Zeichen {re.escape(number)}\b\s*([^\n]*?)(?=\s*Zeichen \d|$)", head)
        name = (m.group(1).strip() if m else norm["title"]).rstrip(".") or norm["title"]
        evidence = f"Zeichen {number}"
        rule = _first_rule(text)
        c = cur.get(number, {})
        anlage = key.split(" Nr.")[0]
        group = _group_rows(snap["norms"], key)
        items.append({
            "id": f"SIGN_{number.replace('.', '_').replace('-', '_')}", "number": number, "name": name,
            "category": CATEGORY.get(anlage, "Vorschriftzeichen"),
            "meaning": c.get("meaning") or f"Amtliche Bezeichnung: {name} (keine eigene Zusammenfassung hinterlegt)",
            "effects": c.get("effects", []), "priority_effect": c.get("priority_effect", "none"),
            "keywords": c.get("keywords", []), "confusions": c.get("confusions", []),
            "exceptions": c.get("exceptions", []), "last_verified": snap["fetched_at"][:10],
            "confidence": 1.0 if c else 0.6,
            "sources": [{"type": "law", "law": "stvo_2013", "norm": key, "evidence": evidence},
                        *([{"type": "law", "law": "stvo_2013", "norm": key, "evidence": rule}] if rule else []),
                        *({"type": "law", "law": "stvo_2013", "norm": g, "evidence": ev} for g, ev in group)],
        })
    items.sort(key=lambda s: [float(p) if p.replace(".", "").isdigit() else 0 for p in re.split(r"[-]", s["number"])])
    return {"_generated_by": "windows/tools/build_signs.py", "items": items}


if __name__ == "__main__":
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(data['items'])} signs -> {OUT}")
