"""Knowledge watch: LegalDocML parsing, change classification, broken evidence -> URGENT_REVIEW."""

import gzip
import json

import tools.knowledge_watch as kw

AKN = "http://Inhaltsdaten.LegalDocML.de/1.8.2/"
MAIN = f"""<akn:akomaNtoso xmlns:akn="{AKN}"><akn:doc><akn:mainBody>
<akn:article eId="art-z3"><akn:num>§ 3</akn:num><akn:heading>Geschwindigkeit</akn:heading>
<akn:paragraph><akn:num>(4)</akn:num><akn:content><akn:p>Die zulässige Höchstgeschwindigkeit beträgt für Kraftfahrzeuge mit Schneeketten auch unter günstigsten Umständen {{v}} km/h.</akn:p></akn:content></akn:paragraph>
</akn:article></akn:mainBody></akn:doc></akn:akomaNtoso>"""
ANNEX = f"""<akn:akomaNtoso xmlns:akn="{AKN}"><akn:doc><akn:preface><akn:docTitle>Anlage 2 (zu § 41 Absatz 1) Vorschriftzeichen</akn:docTitle></akn:preface>
<akn:mainBody><akn:table><akn:tr><akn:td><akn:p>Abschnitt 1 Wartegebote</akn:p></akn:td></akn:tr>
<akn:tr><akn:td><akn:p>2</akn:p></akn:td><akn:td><akn:p>Zeichen 205<akn:br/><akn:img src="x"/> Vorfahrt gewähren.</akn:p></akn:td>
<akn:td><akn:p><akn:b>Ge- oder Verbot</akn:b></akn:p><akn:p>Wer ein Fahrzeug führt, muss Vorfahrt gewähren.</akn:p></akn:td></akn:tr>
</akn:table></akn:mainBody></akn:doc></akn:akomaNtoso>"""


def _raw(tmp_path, v):
    d = tmp_path / f"raw{v}" / "stvo_2013"
    d.mkdir(parents=True)
    (d / "regelungstext-verkuendung-1.xml.gz").write_bytes(gzip.compress(MAIN.replace("{v}", str(v)).encode()))
    (d / "anlage-regelungstext-2.xml.gz").write_bytes(gzip.compress(ANNEX.encode()))
    (d / "meta.json").write_text(json.dumps({"name": "StVO", "abbreviation": "StVO", "eli": "eli/bund/x",
                                             "zip_url": "https://example/x.zip", "fetched_at": "2026-10-01T00:00:00Z"}),
                                 encoding="utf-8")
    return d.parent


def test_parse_ldml_articles_and_sign_rows(tmp_path):
    out = tmp_path / "snap"
    kw.parse_raw(_raw(tmp_path, 50), out)
    snap = json.loads((out / "stvo_2013.json").read_text(encoding="utf-8"))
    assert "Schneeketten" in snap["norms"]["§ 3"]["text"]
    assert snap["norms"]["§ 3"]["paragraphs"]["(4)"]
    assert snap["sign_index"]["205"] == "Anlage 2 Nr. 2"
    assert "muss Vorfahrt gewähren" in snap["norms"]["Anlage 2 Nr. 2"]["text"]


def test_compare_detects_legal_change_and_broken_evidence(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    kw.parse_raw(_raw(tmp_path, 50), old)
    (tmp_path / "x").mkdir()
    kw.parse_raw(_raw(tmp_path / "x", 40), new)
    kdir = tmp_path / "knowledge" / "08_speed_distance"
    kdir.mkdir(parents=True)
    (kdir / "a.json").write_text(json.dumps({"items": [{"id": "SNOW", "sources": [
        {"type": "law", "law": "stvo_2013", "norm": "§ 3", "evidence": "mit Schneeketten auch unter günstigsten Umständen 50 km/h"}]}]}), encoding="utf-8")
    res = kw.compare(old, new, tmp_path / "knowledge")
    assert res["status"] == "URGENT_REVIEW"
    assert res["broken_evidence"][0]["id"] == "SNOW"
    assert any(c["norm"] == "§ 3" and c["kind"] == "changed" for c in res["changed_norms"])
    md = kw.report_md(res)
    assert "Nothing is changed automatically" in md


def test_no_change(tmp_path):
    a = tmp_path / "a"
    kw.parse_raw(_raw(tmp_path, 50), a)
    res = kw.compare(a, a, tmp_path)
    assert res["status"] == "NO_CHANGE"


def test_committed_snapshots_match_committed_raw_sources(tmp_path):
    """The reviewed snapshots are exactly what the parser makes of the reviewed raw texts."""
    out = tmp_path / "s"
    kw.parse_raw(kw.ROOT / "knowledge" / "sources" / "raw", out)
    for p in out.glob("*.json"):
        mine = json.loads(p.read_text(encoding="utf-8"))["norms"]
        committed = json.loads((kw.ROOT / "knowledge" / "sources" / "snapshots" / p.name).read_text(encoding="utf-8"))["norms"]
        assert {k: v["sha256"] for k, v in mine.items()} == {k: v["sha256"] for k, v in committed.items()}
