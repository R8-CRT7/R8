# Driver Theory Knowledge Engine (Klasse B/BE) – Architektur und Stand

Branch: `feature/driver-theory-knowledge-engine` (Basis: v0.5.0-alpha.3). **Nicht veröffentlicht, kein alpha.4.**

## Grundsätze
* **Regeln verstehen statt Fragen auswendig lernen.** Die Wissensbasis enthält Regeln, Zahlen, Ausnahmen und
  eigene Kurzfassungen – keine kopierten Prüfungsfragen, keine Buch- oder Katalogpassagen.
* **Gesetz vor allem anderen.** Jede Gesetzes-Zitation trägt einen wörtlichen Auszug (`evidence`), der beim
  Laden und in den Tests gegen den amtlichen Text geprüft wird (StVO, StVZO, eKFV und Autobahn-Richtgeschwindigkeits-V aus dem
  Rechtsinformationsportal des Bundes, LegalDocML). Gesetzestexte sind amtliche Werke (§ 5 UrhG).
* **Kein Zahlenwert aus Modellwissen.** Jede Zahlenregel braucht ihren `value_text` in der Evidenz. Was nicht
  amtlich prüfbar ist (FeV, StVG, BKatV – nicht im RIS-Testbestand, gesetze-im-internet.de ist in dieser
  Umgebung gesperrt), ist als **unverified** markiert. Die Engine antwortet darauf **UNCERTAIN**, und der
  Lernmodus zeigt eine Warnung.
* **Lieber UNCERTAIN als falsch und sicher.** Die wichtigste Kennzahl ist die `false_confident_rate`.
* **Das DEGENER-Lehrbuch wurde nicht verwendet.** Es ist urheberrechtlich geschützt und in dieser Umgebung
  nicht erreichbar. Es wurde nichts daraus übernommen.

## Aufbau
```
knowledge/
  01_personal … 14_trailers/*.json   Regeln (KnowledgeObject): rule, conditions, exceptions, claims, sources, version …
  numeric_rules.json                 Zahlenregeln mit value_text + Evidenz
  signs.json                         185 Zeichen aus StVO Anlage 1–4 (erzeugt: tools/build_signs.py)
  curation/signs_curated.json        eigene Kurzbedeutungen, Verwechslungen
  concept_graph.json                 Konzept-Kanten (requires/influences/part_of/exception_of/…)
  sources/raw/<gesetz>/*.xml.gz      amtliche LegalDocML-Texte (vom CI-Runner geholt)
  sources/snapshots/<gesetz>.json    geparste Normen mit sha256 (tools/knowledge_watch.py parse)
  watch/sources.json                 welche Gesetze/Normen beobachtet werden
windows/smart360/theory/
  schema.py      pydantic-Modelle (Versionierung: id, version, valid_from/until, last_verified, sources, confidence)
  kb.py          Laden, Validierung, Evidenz-Prüfung (verified/unverified/secondary), Retrieval, Vokabular
  text.py        Normalisierung, Synonyme, Zahlen/Einheiten, Stemming, OCR-Reparatur (nur typische Verwechslungen)
  negation.py    NICHT/KEIN/DÜRFEN/MÜSSEN/KÖNNEN/IMMER/NUR/VERBOTEN/ERLAUBT/AUSNAHME → Deontik + Polarität
  calc.py        deterministische Formeln (12) mit Rechenweg; Klassenentscheid B/B96/BE (FeV, unverified)
  priority.py    Vorfahrt-Engine: Polizei > Einsatzfahrzeug > Bahn > Ampel > Fußgänger > Zeichen > Grundstück >
                 Rad gleiche Richtung > Abbiegen/Gegenverkehr > rechts vor links; Kreisverkehr; Deadlock-Erkennung
  scene.py       Szenenmodell für Bildfragen (JSON-Schema für ein Vision-Modell); Video: ein Frame ist nicht vollständig
  reasoning.py   Pipeline (unten)
  generator.py   synthetische Varianten aus Regeln (nie aus kopierten Fragen)
  golden.py      Golden-Set-Loader
  crosscheck.py  optionaler Abgleich mit der KI-Antwort (kann nur vorsichtiger machen)
windows/smart360/tutor/
  store.py mastery.py planner.py errors.py exam.py learn.py
```

## Reasoning-Pipeline (`reasoning.solve`)
OCR-Reparatur (Polaritäts- und Fachwörter, nur typische OCR-Verwechslungen; unlesbare Antworten → UNKNOWN)
→ Normalisierung → Klassifikation (Rechnen, Klasse, Zeichen, Vorfahrt, Bild, Video, Mehrfachauswahl,
Frage nach dem Falschen) → Szenenprüfung (Bild ohne Szene / dynamische Frage mit einem Frame → unsicher)
→ Regel-Retrieval → deterministische Rechnung → Zeichen-Bedeutung → Vorfahrt-Engine → **semantische
Prüfung A** (Frage + Antwort gegen Claims; Ja/Nein-Fragen; kurze Antworten zusammen mit der Frage gelesen;
Hauptsatz und Bedingung getrennt) → **Prüfung B** (ohne Situationsgewichtung; Widerspruch → UNKNOWN) →
**Prüfung C** (Zahlen pro Einheit) → Ausnahme-Prüfung → Negations-Prüfung → zweiter Durchgang (Lücken,
keine Antwort, unverifizierte Regel, Widerspruch zur KI, niedrige OCR) → Konfidenz als gewichtetes
geometrisches Mittel aus OCR, Bild, Regelabdeckung, Trefferqualität, Quelle, Rechnung, Übereinstimmung,
Ausnahmerisiko, Mehrdeutigkeit. Ist irgendetwas unsicher, wird die Konfidenz unter die Schwelle gekappt
(gleiche Sicherheitskappe wie die App).

Wichtige Schutzmechanismen, jeweils aus einem gemessenen Fehler entstanden:

| Mechanismus | Fehlerklasse, die er verhindert |
|---|---|
| Qualifier-Wächter + „ohne X“ | „Pkw mit/ohne Anhänger“ → falsches Tempolimit |
| Spezifität | „aus einem Feldweg von rechts“ → die allgemeine Regel „rechts vor links“ gewinnt |
| Hauptsatz vs. Bedingung | „nicht“ im „solange …“-Nebensatz kippt die Aussage |
| Zahlen pro Einheit, unbekannte Zahl → UNKNOWN | „unter 75 m“ ungeprüft akzeptiert |
| Zeichen-Polarität nur bei polarer Antwort | „nicht/verboten“ in der Bedeutung kippt einen bloßen Zeichennamen |
| OCR-Reparatur, unlesbar → UNKNOWN | „kcin“ statt „kein“ kippt die Aussage |
| Ja/Nein-Fragen mit Begründung | „Ja, wenn …“ ohne die Frage ausgewertet |

## Tutor
* **Lernmodus:** Planer → Frage → Antwort → Prüfung → Erklärung **jeder** Option → Regel und amtliche Quelle →
  Merkhilfe → ähnliche Frage → Profil. Gespeichert werden Thema, Unterthema, Versuch, richtig/falsch, Zeit,
  „unsicher“, Fehlertyp und Modus.
* **Mastery 0–100:**
  * Bayes-Genauigkeit mit 30 Tagen Halbwertszeit und Belegen aus verschiedenen Varianten und Tagen.
  * Nach **einer** richtigen Antwort höchstens 50, mit weniger als 3 Varianten höchstens 70.
  * Unsichere Antworten zählen 0,6, langsame 0,9.
* **Spaced Repetition:** Die Stabilität wächst nach richtigen Antworten mit Abstand und sinkt bei Fehlern auf
  40 %. Fällig wird eine Wiederholung bei 80 % Retention. Prüfungsrelevantes und Wackelkandidaten kommen früher.
* **Planer:** Klassen 1–7 (Lücke, wiederkehrender Fehler, fast vergessen, neue Regel, unsicher,
  Prüfungssimulation, Kontrolle); innerhalb einer Klasse sortiert nach Mastery-Gewinn pro Minute.
* **Fehlerursachen:** 11 Ursachen, jeweils mit einer Reparatur-Aktion. Für die Engine gibt es eine eigene
  Diagnose (`engine_mistake`).
* **Prüfungssimulation:** 30 Fragen, höchstens 10 Fehlerpunkte, nicht zwei 5-Punkte-Fehler, exakte
  Mehrfachauswahl.
  * Die Struktur stammt aus der FeV Anlage 7 und ist **nicht amtlich verifiziert**. Das wird angezeigt.
  * Die Fehlerpunkte je Frage sind eine Näherung, weil der amtliche Katalog nicht vorliegt.
* Terminal: `python windows/tools/theory_learn.py [--exam|--status]`.

## Messungen (alle aus diesem Branch, keine echten Prüfungsfragen)
| Satz | n | Genauigkeit | UNCERTAIN | false-confident | Präzision wenn beantwortet |
|---|---|---|---|---|---|
| Synthetisch (aus den Regeln erzeugt) | 5 152 | 76,0 % | 24,0 % | **0,0 %** | 100,0 % |
| ↳ Mehrfachauswahl exakt | 862 | 70,5 % | 29,5 % | 0,0 % | 100,0 % |
| ↳ Rechnen | 632 | 98,4 % | 1,6 % | 0,0 % | 100,0 % |
| ↳ Negation / Frage nach dem Falschen | 752 | 71,4 % | 28,6 % | 0,0 % | 100,0 % |
| ↳ Bild (Vorfahrt-Szenen) | 408 | 100 % | 0 % | 0,0 % | 100 % |
| ↳ Zeichen | 102 | 94,1 % | 5,9 % | 0,0 % | 100 % |
| ↳ Fahrerlaubnisklasse (FeV, unverified) | 26 | 0 % | 100 % | 0,0 % | – |
| **Golden v1 – erste Messung** | 80 | **21,3 %** | 75,0 % | **3,75 %** | 85,0 % |
| **Golden v2 – erste Messung** | 80 | **20,0 %** | 76,3 % | **3,75 %** | 84,2 % |
| Golden v1/v2 nach Korrektur der Fehlerklassen (nicht mehr unabhängig) | 80/80 | 35,0 % / 23,8 % | 65,0 % / 76,3 % | 0 % / 0 % | 100 % / 100 % |

Regelauswahl-Genauigkeit (synthetisch): 99,4 %.

**Ehrliche Einordnung:**
1. Die synthetischen Werte messen **Robustheit** gegenüber Umformulierung, Negation, OCR-Rauschen, Zahlen und
   Mehrfachauswahl, und zwar auf den Formulierungen der eigenen Wissensbasis. Sie messen **nicht**, wie viel
   der echten Prüfung abgedeckt ist.
2. Die Golden-Sets (eigene Fragen, nie zum Optimieren verwendet, per SHA-256 eingefroren) zeigen das reale
   Bild. Bei neuen Formulierungen antwortet die Engine **nur selten** (rund 20–35 %), meist mit UNCERTAIN.
   Bei der jeweils ersten Messung waren **3 von 80** Antworten falsch und sicher.
   * Die Ursachen wurden als allgemeine Fehlerklassen behoben (siehe Tabelle oben). Danach sind die Golden-Sets
     nicht mehr unabhängig.
   * Eine echte Nachmessung braucht einen **neuen** Satz, idealerweise von einem Menschen geschrieben.
3. Beide Golden-Sets stammen vom selben Autor wie die Wissensbasis (KI). Sie sind daher **nicht** unabhängig
   im strengen Sinn.
4. Daraus folgt die Rolle der Engine: Sie ist als **vorsichtiger Prüfer** neben der KI geeignet
   (`safety.theory_crosscheck`, Standard aus). Als alleiniger Antwortgeber ist sie (noch) nicht geeignet.
   **Keine Aussage über 100 % Zuverlässigkeit.**

## Tägliche Wissensprüfung (`.github/workflows/knowledge-watch.yml`, 04:17 UTC)
1. **Erkennen:** RIS-API, nur gültige Fassungen.
2. **Vergleichen:** Rohtexte gegen die geprüften Texte.
3. **Wirkung:** parse → compare → alle Evidenzen gegen den neuen Text.
4. **Status:** `NO_CHANGE / MINOR_CHANGE / KNOWLEDGE_UPDATE / LEGAL_CHANGE / EXAM_CHANGE / URGENT_REVIEW`
   (gebrochene Evidenz = URGENT_REVIEW).
5. **Bericht:** in der Job-Zusammenfassung.

Es wird **nichts automatisch übernommen**. Neue Rohtexte landen nur bei einem bewusst markierten Commit
(`[refresh-sources]`) im Repository. Danach folgen eine Prüfung durch einen Menschen, Tests und ein neuer
Snapshot.

## Bekannte Grenzen
* FeV/StVG/BKatV fehlen (Probezeit, Punkte, Alkohol, Cannabis, Klassen, Bußgelder, Prüfungsstruktur).
  Diese Werte sind unverified.
* Kein Vision-Modell im Branch:
  * Bildfragen funktionieren nur mit einem Szenenmodell (JSON).
  * Ohne Szenenmodell → UNCERTAIN.
  * Echte 360°-Bilder wurden nie getestet.
* Videos: nur die Vollständigkeitsprüfung (ein Frame reicht nicht). Es gibt noch keine Analyse über mehrere
  Frames.
* Die Abdeckung ist dünn bei:
  * Zusatzzeichen
  * Fahrphysik jenseits der Faustformeln
  * Tunnel und Wild
  * Gefahrgut
  * Umweltfahrweise im Detail
* Wenige Paraphrasen: Die Engine versteht vor allem Formulierungen, die nah an ihren Claims sind.
