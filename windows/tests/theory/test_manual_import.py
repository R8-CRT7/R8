"""Manual official-source import: official markers, snapshot with provenance, evidence check, unofficial files
never become ground truth. Uses a tiny synthetic law file in a temporary knowledge root (never the real KB)."""

import json

from tools import manual_source_import as msi

OBJ = {"id": "T_RULE", "version": 1, "valid_from": None, "valid_until": None, "last_verified": "2026-10-01",
       "sources": [{"type": "law", "law": "fev_2010", "norm": "§ 6", "para": None,
                    "evidence": "Testsatz eins für die Klasse B.", "ref": None}],
       "confidence": 1.0, "topic": "01_personal", "subtopic": "t", "title": "T", "rule": "T", "conditions": [],
       "exceptions": [], "numeric_refs": [], "concepts": [], "keywords": [], "claims": [], "mnemonic": "",
       "exam_relevance": 3, "difficulty": 2}
XML = ('<?xml version="1.0" encoding="UTF-8"?><dokumente builddate="20260101" doknr="X">'
       '<norm><metadaten><jurabk>FeV</jurabk><enbez>§ 6</enbez><titel>Test</titel></metadaten>'
       '<textdaten><text><Content><P>Testsatz eins für die Klasse B.</P></Content></text></textdaten></norm>'
       '</dokumente>')


def _root(tmp_path):
    k = tmp_path / "knowledge"
    (k / "01_personal").mkdir(parents=True)
    (k / "sources" / "snapshots").mkdir(parents=True)
    (k / "01_personal" / "t.json").write_text(json.dumps({"items": [OBJ]}), encoding="utf-8")
    return k


def test_official_xml_is_imported_and_verifies_evidence(tmp_path):
    k = _root(tmp_path)
    f = tmp_path / "fev.xml"
    f.write_text(XML, encoding="utf-8")
    assert msi.main([str(f), "--law", "fev_2010", "--knowledge", str(k)]) == 0
    snap = json.loads((k / "sources" / "snapshots" / "fev_2010.json").read_text(encoding="utf-8"))
    assert snap["origin"] == "manual" and len(snap["sha256"]) == 64 and "jurabk:FeV" in snap["official_markers"]
    cited, verified, errors = msi.evidence_report(k, "fev_2010")
    assert verified == ["T_RULE"] and not errors


def test_unofficial_file_never_becomes_ground_truth(tmp_path):
    k = _root(tmp_path)
    f = tmp_path / "copy.html"
    f.write_text("<html><body>§ 6 Testsatz eins für die Klasse B.</body></html>", encoding="utf-8")
    assert msi.main([str(f), "--law", "fev_2010", "--knowledge", str(k)]) == 2
    assert not (k / "sources" / "snapshots" / "fev_2010.json").exists()
    assert (k / "sources" / "manual" / "unofficial" / "fev_2010.json").exists()
    _, verified, _ = msi.evidence_report(k, "fev_2010")
    assert verified == []


def test_wrong_law_marker_is_not_official(tmp_path):
    k = _root(tmp_path)
    f = tmp_path / "other.xml"
    f.write_text(XML.replace("<jurabk>FeV</jurabk>", "<jurabk>XYZ</jurabk>"), encoding="utf-8")
    assert msi.main([str(f), "--law", "fev_2010", "--knowledge", str(k)]) == 2


def test_broken_evidence_is_reported_not_fixed(tmp_path):
    k = _root(tmp_path)
    f = tmp_path / "fev.xml"
    f.write_text(XML.replace("Testsatz eins", "Ein anderer Satz"), encoding="utf-8")
    assert msi.main([str(f), "--law", "fev_2010", "--knowledge", str(k)]) == 3
    obj = json.loads((k / "01_personal" / "t.json").read_text(encoding="utf-8"))["items"][0]
    assert obj == OBJ  # the knowledge base itself is never edited
