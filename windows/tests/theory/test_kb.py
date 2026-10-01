"""Knowledge base integrity: every law citation verbatim in the official snapshot, no unverified value hidden."""

import json
import re

from smart360.theory.kb import knowledge_dir
from smart360.theory.schema import TOPICS


def test_loads_and_all_evidence_is_verbatim_in_the_official_snapshot(kb):
    assert kb.evidence_errors == [], kb.evidence_errors


def test_all_14_topics_have_rules(kb):
    assert set(kb.by_topic) == set(TOPICS)


def test_counts(kb):
    assert len(kb.objects) >= 70
    assert len(kb.numeric) >= 60
    assert len(kb.signs) >= 150
    assert sum(len(o.claims) for o in kb.objects.values()) >= 250


def test_numeric_refs_exist(kb):
    missing = [(o.id, r) for o in kb.objects.values() for r in o.numeric_refs if r not in kb.numeric]
    assert missing == []


def test_every_numeric_value_text_is_in_its_evidence_when_verified(kb):
    for r in kb.numeric.values():
        if kb.status[r.id] == "verified":
            ev = " ".join(s.evidence for s in r.sources)
            assert re.sub(r"\s+", " ", r.value_text) in re.sub(r"\s+", " ", ev), r.id


def test_unverified_items_are_exactly_the_laws_without_official_snapshot(kb):
    """FeV/StVG/BKatV are not in the RIS test phase - their values must be flagged, never silently trusted."""
    for item_id, st in kb.status.items():
        if st == "unverified":
            item = kb.objects.get(item_id) or kb.numeric.get(item_id) or next(
                s for s in kb.signs.values() if s.id == item_id)
            laws = {s.law for s in item.sources if s.type == "law"}
            assert laws and not laws & set(kb.snapshots), item_id
    assert kb.status["FEV6_B_MAX_ZGM"] == "unverified"
    assert kb.status["STVO_3_INNERORTS"] == "verified"


def test_versioning_fields_present(kb):
    for o in [*kb.objects.values(), *kb.numeric.values()]:
        assert o.version >= 1
        assert o.sources
        if kb.status[o.id] == "verified":
            assert o.last_verified, o.id


def test_snapshots_have_source_metadata(kb):
    for slug, snap in kb.snapshots.items():
        assert snap["eli"].startswith("eli/bund/"), slug
        assert snap["source_url"].startswith("https://testphase.rechtsinformationen.bund.de/"), slug
        for n in snap["norms"].values():
            assert len(n["sha256"]) == 64


def test_no_copied_exam_catalogue_markers():
    """Guard against accidentally importing official/commercial question catalogues (numbering like 1.1.01-001)."""
    rx = re.compile(r"\b\d\.\d\.\d{2}-\d{3}\b")
    for p in knowledge_dir().rglob("*.json"):
        if "sources" in p.parts:
            continue
        assert not rx.search(p.read_text(encoding="utf-8")), p


def test_signs_cite_their_official_row(kb):
    s = kb.signs["205"]
    assert s.sources[0].norm == "Anlage 2 Nr. 2"
    assert any("muss Vorfahrt gewähren" in x.evidence for x in s.sources)
    assert kb.signs["276"].sources[-1].norm.startswith("Anlage 2 Nr. Zu 53")


def test_concept_graph_edges_reference_used_concepts(kb):
    used = {c for o in kb.objects.values() for c in o.concepts}
    unknown = {e.a for e in kb.edges} | {e.b for e in kb.edges}
    assert len(unknown & used) >= 0.7 * len(unknown)


def test_roundabout_rule_is_paragraph_8_not_9a(kb):
    """Regression: the StVO has no § 9a - found by checking against the official text."""
    assert kb.norm_text("stvo_2013", "§ 9a") is None
    assert "Kreisverkehr" in kb.norm_text("stvo_2013", "§ 8")


def test_knowledge_json_is_valid_and_ids_unique():
    ids = []
    for p in knowledge_dir().glob("[0-9][0-9]_*/*.json"):
        ids += [i["id"] for i in json.loads(p.read_text(encoding="utf-8"))["items"]]
    assert len(ids) == len(set(ids))
