"""Manual official-source import: parse -> verify official markers -> snapshot -> evidence check -> report.

    python tools/manual_source_import.py FILE --law fev_2010 [--confirm-official] [--dry-run]

See knowledge/sources/manual/README.md. Never edits knowledge objects; an unofficial file never becomes ground truth.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import re
import sys
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.knowledge_watch import norm_key, parse_law, parse_ldml_main

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ABBR = {"fev_2010": ("FeV",), "stvg": ("StVG",), "bkatv_2013": ("BKatV",), "stvo_2013": ("StVO",),
                 "stvzo_2012": ("StVZO",)}


@dataclass
class Parsed:
    fmt: str
    norms: dict[str, dict]
    markers: list[str] = field(default_factory=list)
    official: bool = False
    builddate: str = ""


def _xml_bytes(data: bytes) -> bytes:
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = next(n for n in z.namelist() if n.endswith(".xml"))
            return z.read(name)
    return data


def parse_file(path: Path, law: str, confirm_official: bool = False) -> Parsed:
    data = path.read_bytes()
    suffix = path.suffix.lower()
    abbr = EXPECTED_ABBR.get(law, ())
    if suffix in (".xml", ".zip"):
        raw = _xml_bytes(data)
        text = raw.decode("utf-8", errors="replace")
        if "akomaNtoso" in text or "akn:" in text:
            norms = parse_ldml_main(raw)
            markers = [m for m in ("akomaNtoso", "eli/bund") if m in text]
            return Parsed("legaldocml", norms, markers, len(markers) == 2 or confirm_official)
        parsed = parse_law(raw)
        norms = {norm_key(k): v for k, v in parsed["norms"].items()}
        markers = []
        if "<dokumente" in text and parsed.get("builddate"):
            markers.append("gii:dokumente+builddate")
        jur = re.findall(r"<jurabk>([^<]+)</jurabk>", text)
        if jur and any(j.strip() in abbr for j in jur):
            markers.append(f"jurabk:{jur[0].strip()}")
        return Parsed("gii_xml", norms, markers, len(markers) == 2 or confirm_official, parsed.get("builddate", ""))
    if suffix in (".html", ".htm"):
        text = data.decode("utf-8", errors="replace")
        markers = [m for m in ("gesetze-im-internet.de", "Bundesministerium der Justiz") if m in text]
        body = html.unescape(re.sub(r"<[^>]+>", "\n", re.sub(r"(?is)<(script|style).*?</\1>", "", text)))
        return Parsed("html", _split_norms(body), markers, confirm_official and bool(markers))
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # optional, not a dependency of the app
        except ImportError as exc:
            raise SystemExit("PDF import needs the optional package 'pypdf' - or provide the XML/HTML file") from exc
        body = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
        markers = ["Bundesgesetzblatt"] if "Bundesgesetzblatt" in body else []
        return Parsed("pdf", _split_norms(body), markers, confirm_official and bool(markers))
    raise SystemExit(f"unsupported file type {suffix}")


def _split_norms(body: str) -> dict[str, dict]:
    norms: dict[str, dict] = {}
    parts = re.split(r"\n\s*(§\s*\d+[a-z]?|Anlage\s+\d+[a-z]?)\b", "\n" + body)
    for i in range(1, len(parts) - 1, 2):
        key = re.sub(r"\s+", " ", parts[i]).strip()
        text = re.sub(r"[ \t]+", " ", parts[i + 1]).strip()
        if text and key not in norms:
            norms[key] = {"title": text.split("\n", 1)[0][:120], "text": text}
    return norms


def snapshot(parsed: Parsed, law: str, src: Path) -> dict:
    return {"law": law, "abbreviation": (EXPECTED_ABBR.get(law) or ("",))[0], "origin": "manual",
            "source_file": src.name, "sha256": hashlib.sha256(src.read_bytes()).hexdigest(), "format": parsed.fmt,
            "official_markers": parsed.markers, "builddate": parsed.builddate, "source_priority": 1,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "norms": parsed.norms}


def evidence_report(knowledge_root: Path, law: str) -> tuple[list[str], list[str], list[str]]:
    from smart360.theory.kb import KnowledgeBase

    kb = KnowledgeBase.load(knowledge_root)
    cited = sorted({it.id for it in [*kb.objects.values(), *kb.numeric.values()] for s in it.sources if s.law == law})
    verified = [i for i in cited if kb.status.get(i) == "verified"]
    errors = [e for e in kb.evidence_errors if f" {law} " in e or f"in {law}" in e]
    return cited, verified, errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path, nargs="?")
    ap.add_argument("--law", help="law id as cited in the knowledge base, e.g. fev_2010, stvg")
    ap.add_argument("--all", action="store_true", help="import every <law>_xml.zip found in knowledge/sources/manual/")
    ap.add_argument("--confirm-official", action="store_true",
                    help="you checked that the file is the official text (needed for HTML/PDF)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--knowledge", type=Path, default=ROOT / "knowledge")
    a = ap.parse_args(argv)
    if a.all:
        files = sorted((a.knowledge / "sources" / "manual").glob("*_xml.zip"))
        if not files:
            print("no <law>_xml.zip files in knowledge/sources/manual/ - see the README there")
            return 1
        codes = [main([str(f), "--law", f.name.removesuffix("_xml.zip"), "--knowledge", str(a.knowledge)]
                      + (["--confirm-official"] if a.confirm_official else [])) for f in files]
        return max(codes)
    if a.file is None or a.law is None:
        ap.error("FILE and --law are required (or use --all)")
    parsed = parse_file(a.file, a.law, a.confirm_official)
    print(f"format {parsed.fmt}, {len(parsed.norms)} norms, markers {parsed.markers}, official={parsed.official}")
    if not parsed.norms:
        print("no norms found - nothing imported")
        return 1
    snap = snapshot(parsed, a.law, a.file)
    if a.dry_run:
        return 0
    if not parsed.official:
        target = a.knowledge / "sources" / "manual" / "unofficial" / f"{a.law}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"NOT official (markers missing / not confirmed) -> stored for reference only: {target}")
        print("It verifies nothing; the rules citing this law stay unverified.")
        return 2
    target = a.knowledge / "sources" / "snapshots" / f"{a.law}.json"
    target.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    cited, verified, errors = evidence_report(a.knowledge, a.law)
    lines = [f"# Manual import {a.law} ({time.strftime('%Y-%m-%d')})", "",
             f"File `{a.file.name}` ({parsed.fmt}), sha256 `{snap['sha256'][:16]}…`, markers {parsed.markers}.", "",
             f"Rules citing {a.law}: {len(cited)} - verified now: {len(verified)} - broken evidence: {len(errors)}", "",
             "## Verified", "", ", ".join(verified) or "-", "", "## Evidence not found (fix by hand, never automatic)", ""]
    lines += [f"- {e}" for e in errors] or ["-"]
    rep = a.knowledge.parent / "reports" / f"manual_import_{a.law}.md"
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"snapshot {target}; {len(verified)}/{len(cited)} citations verified, {len(errors)} broken -> {rep}")
    return 0 if not errors else 3


if __name__ == "__main__":
    raise SystemExit(main())
