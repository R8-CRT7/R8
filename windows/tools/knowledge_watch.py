"""Knowledge watch: official law texts -> snapshots -> change detection -> impact report.

Source: gesetze-im-internet.de (Bundesministerium der Justiz), official XML downloads. German statutes are
official works without copyright (§ 5 UrhG), so verbatim snapshots of the relevant norms may be stored.

    python tools/knowledge_watch.py fetch   --out DIR
    python tools/knowledge_watch.py compare --old knowledge/sources/snapshots --new DIR --report report.md
    python tools/knowledge_watch.py show    --law stvo_2013 --norm "§ 3"

A detected change is NEVER applied to the knowledge base automatically. `compare` classifies it
(NO_CHANGE, MINOR_CHANGE, KNOWLEDGE_UPDATE, LEGAL_CHANGE, EXAM_CHANGE, URGENT_REVIEW) and lists the knowledge
objects / numeric rules whose cited evidence is affected, for human review.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET  # nosec B405 - official, fixed government source
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "knowledge" / "watch" / "sources.json"
BASE = "https://www.gesetze-im-internet.de/{slug}/xml.zip"
BLOCK = {"P", "row", "DT", "DD", "LA", "BR", "Title", "Subtitle", "tr", "entry", "pre"}
STATUSES = ("NO_CHANGE", "MINOR_CHANGE", "KNOWLEDGE_UPDATE", "LEGAL_CHANGE", "EXAM_CHANGE", "URGENT_REVIEW")


# ----------------------------------------------------------------------------- XML -> text
def _text(el: ET.Element) -> str:
    parts: list[str] = []

    def walk(e: ET.Element) -> None:
        tag = e.tag.split("}")[-1]
        if tag in BLOCK:
            parts.append("\n")
        if e.text:
            parts.append(e.text)
        for c in e:
            walk(c)
            if c.tail:
                parts.append(c.tail)
        if tag in ("entry",):
            parts.append(" | ")
        if tag in BLOCK:
            parts.append("\n")

    walk(el)
    text = "".join(parts).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_law(xml_bytes: bytes) -> dict:
    root = ET.fromstring(xml_bytes)  # nosec B314 - official source, no entities used
    norms: dict[str, dict] = {}
    for norm in root.iter("norm"):
        meta = norm.find("metadaten")
        if meta is None:
            continue
        enbez = (meta.findtext("enbez") or "").strip()
        if not enbez:
            continue
        title = (meta.findtext("titel") or "").strip()
        content = norm.find("textdaten/text/Content")
        text = _text(content) if content is not None else ""
        if not text:
            continue
        norms[enbez] = {"title": title, "text": text}
    return {"builddate": root.get("builddate", ""), "norms": norms}


def norm_key(enbez: str) -> str:
    """'Anlage 2 (zu § 41 Absatz 1)' -> 'Anlage 2'; '§ 3' -> '§ 3'."""
    m = re.match(r"(§+\s*\d+[a-z]?|Anlage\s+\d+[a-z]?)", enbez)
    return re.sub(r"\s+", " ", m.group(1)) if m else enbez


def _download(url: str, attempts: int = 4) -> bytes:
    last: Exception | None = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (360SMART knowledge watch)"})
            with urllib.request.urlopen(req, timeout=180) as r:  # nosec B310 - fixed official https URL
                return r.read()
        except OSError as e:  # timeouts / resets: back off and retry
            last = e
            print(f"  attempt {i + 1} failed for {url}: {e}", flush=True)
            time.sleep(10 * (i + 1))
    raise RuntimeError(f"download failed: {url}: {last}")


def _json(url: str) -> dict:
    return json.loads(_download(url).decode("utf-8"))


def _find_law(api: str, abbr: str, search: str) -> dict:
    """The in-force consolidated version of a law via the RIS search API (exact abbreviation match)."""
    from urllib.parse import quote

    res = _json(f"{api}/v1/legislation?searchTerm={quote(search)}&size=50")
    hits = [m["item"] for m in res.get("member", []) if m.get("item", {}).get("@type") == "Legislation"]
    exact = [h for h in hits if (h.get("abbreviation") or "").replace(" ", "").lower().startswith(abbr.lower())
             and "ausn" not in (h.get("abbreviation") or "").lower()]
    exact = [h for h in exact if h.get("legislationLegalForce") == "InForce"] or exact
    if not exact:
        raise RuntimeError(f"{abbr}: not found in RIS search ({[h.get('abbreviation') for h in hits]})")
    exact.sort(key=lambda h: (len(h.get("abbreviation") or ""), h["legislationIdentifier"]))
    return exact[0]


def fetch_raw(out: Path) -> dict:
    """Download the official LegalDocML ZIP of every configured law; store each XML gzip-compressed."""
    import gzip

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    api = cfg["api"]
    summary = {}
    for law in cfg["laws"]:
        item = _find_law(api, law["abbr"], law["search"])
        zip_url = next(e["contentUrl"] for e in item["encoding"] if e["encodingFormat"] == "application/zip")
        data = _download(api + zip_url)
        d = out / law["slug"]
        d.mkdir(parents=True, exist_ok=True)
        names = []
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                if name.lower().endswith(".xml"):
                    (d / (Path(name).name + ".gz")).write_bytes(gzip.compress(z.read(name), mtime=0))
                    names.append(Path(name).name)
        meta = {"slug": law["slug"], "abbreviation": item.get("abbreviation"), "name": item.get("name"),
                "eli": item["legislationIdentifier"], "legal_force": item.get("legislationLegalForce"),
                "zip_url": api + zip_url, "files": sorted(names),
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        summary[law["slug"]] = meta
        print(f"{law['slug']}: {meta['abbreviation']} {meta['eli']} files={len(names)}", flush=True)
    return summary


def fetch(out: Path) -> dict:
    """Legacy source (gesetze-im-internet.de XML) - not reachable from the CI runners, kept for local use."""
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for law in cfg["laws"]:
        url = BASE.format(slug=law["slug"])
        data = _download(url)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml_name = next(n for n in z.namelist() if n.endswith(".xml"))
            parsed = parse_law(z.read(xml_name))
        keep = law["norms"]
        norms = {}
        for enbez, n in parsed["norms"].items():
            key = norm_key(enbez)
            if keep != ["all"] and key not in keep:
                continue
            norms[key] = {"enbez": enbez, "title": n["title"], "text": n["text"],
                          "sha256": hashlib.sha256(normalize(n["text"]).encode()).hexdigest()}
        snap = {"law": law["slug"], "name": law["name"], "source_url": url, "source_priority": law["priority"],
                "builddate": parsed["builddate"], "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "missing_norms": [k for k in keep if k != "all" and k not in norms], "norms": norms}
        (out / f"{law['slug']}.json").write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
        summary[law["slug"]] = {"norms": len(norms)}
    return summary


# ----------------------------------------------------------------------------- compare + impact
def _load_dir(d: Path) -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(d).glob("*.json"))}


def _citations(knowledge_dir: Path) -> list[dict]:
    """Every knowledge object / numeric rule that cites a law norm with an evidence string."""
    cites = []
    for p in sorted(knowledge_dir.rglob("*.json")):
        if "sources" in p.parts or "watch" in p.parts:
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        items = data.get("items", []) if isinstance(data, dict) else data
        for it in items if isinstance(items, list) else []:
            for src in it.get("sources", []) if isinstance(it, dict) else []:
                if src.get("law") and src.get("norm"):
                    cites.append({"id": it.get("id") or it.get("concept_id"), "file": str(p.relative_to(knowledge_dir)),
                                  "law": src["law"], "norm": src["norm"], "evidence": src.get("evidence", "")})
    return cites


def compare(old_dir: Path, new_dir: Path, knowledge_dir: Path) -> dict:
    old, new = _load_dir(old_dir), _load_dir(new_dir)
    changed: list[dict] = []
    for slug, snap in new.items():
        prev = old.get(slug, {"norms": {}})
        for key, n in snap["norms"].items():
            p = prev["norms"].get(key)
            if p is None:
                changed.append({"law": slug, "norm": key, "kind": "added"})
            elif p["sha256"] != n["sha256"]:
                changed.append({"law": slug, "norm": key, "kind": "changed"})
        for key in prev["norms"]:
            if key not in snap["norms"]:
                changed.append({"law": slug, "norm": key, "kind": "removed"})
    cites = _citations(knowledge_dir)
    broken = []
    for c in cites:
        snap = new.get(c["law"])
        if snap is None:
            continue
        n = snap["norms"].get(c["norm"])
        if n is None or (c["evidence"] and normalize(c["evidence"]) not in normalize(n["text"])):
            broken.append(c)
    touched = {(c["law"], c["norm"]) for c in changed}
    affected = [c for c in cites if (c["law"], c["norm"]) in touched]
    if broken:
        status = "URGENT_REVIEW"
    elif any(c["law"] == "fev_2010" and c["norm"] == "Anlage 7" for c in changed):
        status = "EXAM_CHANGE"
    elif affected:
        status = "LEGAL_CHANGE"
    elif changed:
        status = "MINOR_CHANGE"
    else:
        status = "NO_CHANGE"
    return {"status": status, "changed_norms": changed, "affected_knowledge": affected,
            "broken_evidence": broken, "citations_checked": len(cites)}


def report_md(res: dict) -> str:
    lines = [f"# Knowledge watch report - {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}", "",
             f"**Status: {res['status']}** · citations checked: {res['citations_checked']}", "",
             "Nothing is changed automatically. A human reviews this report, updates the knowledge objects, "
             "runs the tests and only then refreshes the snapshots.", ""]
    for title, key in (("Broken evidence (value/text no longer in the law)", "broken_evidence"),
                       ("Knowledge citing changed norms", "affected_knowledge"),
                       ("Changed norms", "changed_norms")):
        lines.append(f"## {title} ({len(res[key])})")
        for x in res[key][:200]:
            lines.append(f"- `{x.get('law')}` {x.get('norm')} {x.get('kind', '')} {x.get('id', '') or ''}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--out", type=Path, required=True)
    fr = sub.add_parser("fetch-raw")
    fr.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("compare")
    c.add_argument("--old", type=Path, default=ROOT / "knowledge" / "sources" / "snapshots")
    c.add_argument("--new", type=Path, required=True)
    c.add_argument("--knowledge", type=Path, default=ROOT / "knowledge")
    c.add_argument("--report", type=Path)
    c.add_argument("--json", type=Path)
    s = sub.add_parser("show")
    s.add_argument("--dir", type=Path, default=ROOT / "knowledge" / "sources" / "snapshots")
    s.add_argument("--law", required=True)
    s.add_argument("--norm", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "fetch":
        fetch(a.out)
    elif a.cmd == "fetch-raw":
        fetch_raw(a.out)
    elif a.cmd == "compare":
        res = compare(a.old, a.new, a.knowledge)
        md = report_md(res)
        print(md)
        if a.report:
            a.report.write_text(md, encoding="utf-8")
        if a.json:
            a.json.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    elif a.cmd == "show":
        snap = json.loads((a.dir / f"{a.law}.json").read_text(encoding="utf-8"))
        n = snap["norms"][a.norm]
        print(f"{a.law} {n['enbez']} {n['title']}\n{n['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
