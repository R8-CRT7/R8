"""Generate docs/KNOWLEDGE_COVERAGE.md from the knowledge base, the law snapshots and the metric reports.

    python tools/knowledge_coverage.py

Nothing in the document is typed by hand: counts come from knowledge/, test numbers from the generator,
accuracy/UNCERTAIN per topic from reports/theory_metrics_synthetic.json (run tools/theory_eval.py first)."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smart360.theory.generator import all_items
from smart360.theory.kb import KnowledgeBase
from smart360.theory.schema import TOPICS

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "KNOWLEDGE_COVERAGE.md"

# Areas of the official Klasse-B catalogue we know are thin or missing - stated honestly, maintained by hand.
GAPS = {
    "01_personal": "Fahreignung, Sehvermögen, Erste-Hilfe-Pflicht beim Erwerb (FeV, nicht verifizierbar)",
    "02_human_risk": "Drogen/Cannabis-Grenzwerte (StVG § 24a, nicht verifizierbar), Medikamentengruppen",
    "03_legal": "Bußgeldkatalog (BKatV nicht im RIS-Testbestand), Haftung/Versicherung, Fahrerlaubnis auf Probe im Detail",
    "04_road_system": "Straßenarten im Detail, Bahnübergänge ohne Andreaskreuz in Sonderfällen",
    "06_signs": "Zusatzzeichen nur allgemein (§ 39 Abs. 3), die 1000er-Reihe ohne eigene Kurzbedeutungen; viele Zeichen nur mit amtlicher Bezeichnung",
    "08_speed_distance": "Kurven-/Fliehkraft-Physik, Aquaplaning-Geschwindigkeiten (keine amtliche Zahl)",
    "11_special": "Tunnel (Z 327) und Wildwechsel (Z 142) nur in Grundzügen, Erste Hilfe im Detail",
    "12_learning": "Prüfungsstruktur (FeV Anlage 7) nicht amtlich verifizierbar",
    "13_vehicle_technology": "Bremsen-/Lenkungsprüfung, Kraftstoffsparen im Detail, Assistenzsysteme (keine amtliche Norm im Bestand), Gefahrgut nur Z 261/269",
    "14_trailers": "Fahrerlaubnisklassen B/B96/BE (FeV § 6, nicht verifizierbar), Stützlast, Anhängelast-Berechnung",
}


def build() -> str:
    kb = KnowledgeBase.load()
    items = all_items(kb)
    metrics_p = ROOT / "reports" / "theory_metrics_synthetic.json"
    metrics = json.loads(metrics_p.read_text(encoding="utf-8")) if metrics_p.exists() else {}
    by_topic_m = metrics.get("by_topic", {})
    n_items = Counter(i.topic for i in items)
    n_image = Counter(i.topic for i in items if i.question.has_image or i.question.scene is not None)
    num_by_topic = Counter(r.topic for r in kb.numeric.values())
    sources: dict[str, set[str]] = defaultdict(set)
    status: dict[str, Counter] = defaultdict(Counter)
    last: dict[str, str] = {}
    for o in kb.objects.values():
        status[o.topic][kb.status[o.id]] += 1
        for s in o.sources:
            sources[o.topic].add(f"{s.law} {s.norm}" if s.law else s.type)
        if o.last_verified:
            last[o.topic] = max(last.get(o.topic, ""), o.last_verified)
    snaps = ", ".join(f"{k} ({v.get('abbreviation')}, {v.get('eli')}, abgerufen {v.get('fetched_at', '')[:10]})"
                      for k, v in kb.snapshots.items())
    lines = [
        "# Knowledge coverage (Klasse B/BE)",
        "",
        "_Automatisch erzeugt von `windows/tools/knowledge_coverage.py` - nicht von Hand bearbeiten._",
        "",
        f"Amtliche Quellen (Rechtsinformationsportal des Bundes, LegalDocML): {snaps}.",
        "Nicht verfügbar (nicht im RIS-Testbestand, Netzwerkrichtlinie blockiert gesetze-im-internet.de): "
        "FeV, StVG, BKatV - Regeln daraus sind als **unverified** markiert und führen in der Engine zu UNCERTAIN.",
        "",
        f"**Gesamt:** {len(kb.objects)} Regeln · {len(kb.numeric)} Zahlenregeln · {len(kb.signs)} Verkehrszeichen · "
        f"{sum(len(o.claims) for o in kb.objects.values())} Aussagen (Claims) · {len(kb.edges)} Konzept-Kanten · "
        f"{len(items)} synthetische Testvarianten · Evidence-Fehler: {len(kb.evidence_errors)}",
        "",
        "| Thema | Regeln (verified / unverified / secondary) | Zahlen | Tests | Bildtests | Genauigkeit synth. | UNCERTAIN synth. | letzte Validierung |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for t, name in TOPICS.items():
        st = status[t]
        m = by_topic_m.get(t, {})
        acc = f"{m['accuracy']:.0%}" if m.get("accuracy") is not None else "-"
        unc = f"{m['uncertain_rate']:.0%}" if m.get("uncertain_rate") is not None else "-"
        lines.append(f"| {t} {name} | {sum(st.values())} ({st['verified']} / {st['unverified']} / {st['secondary']}) | "
                     f"{num_by_topic[t]} | {n_items[t]} | {n_image[t]} | {acc} | {unc} | {last.get(t, '-')} |")
    lines += ["", "## Quellen je Thema", ""]
    for t in TOPICS:
        lines.append(f"- **{t}:** {', '.join(sorted(sources[t])) or '-'}")
    lines += ["", "## Unsichere Bereiche / Lücken (ehrlich, von Hand gepflegt)", ""]
    for t, gap in GAPS.items():
        lines.append(f"- **{t}:** {gap}")
    unverified = sorted(i for i, s in kb.status.items() if s == "unverified")
    lines += ["", "## Nicht amtlich verifizierte Einträge", "", ", ".join(unverified) or "-", "",
              "## Konflikte", "",
              "Keine bekannten Quellenkonflikte. Regel: Gesetz vor Behörde vor TÜV/DEKRA vor Verlag vor Fahrschule. "
              "Ein Widerspruch zwischen Regeln mit ähnlicher Trefferqualität führt in der Engine zu UNCERTAIN "
              "(`conflicting_rules`).", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"written {OUT}")
