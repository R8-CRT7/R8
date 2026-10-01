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

## Meilenstein „Generalisierung + unabhängige Validierung“

**Holdout:** vier getrennte Mengen (`smart360/theory/splits.py`).
* TRAIN = die synthetischen Varianten (Generator).
* VALIDATION = eigene Varianten mit Seed 4242: Akteur, Rauschen, Reihenfolge, Fragestamm, negierte Frage,
  Kurzform, konkurrierende Regel, lange irrelevante Einleitung.
* GOLDEN INTERNAL = v1 + v2, per SHA-256 eingefroren.
* GOLDEN EXTERNAL = `tests/theory/golden_external/`, **nur Auswertung**:
  * `load_golden_external(purpose="evaluation")`, alles andere wird verweigert.
  * `test_holdout.py` prüft, dass die Wissensbasis, der Generator, die Validierung und die KI-Prompts keine
    Golden-Datei lesen und keinen Golden-Text enthalten.
  * Die externe Menge ist **leer**: Sie wartet auf menschlich geschriebene Fragen.

**Eingefrorene Ausgangslage:** `reports/generalization_baseline.json`, Hash-Test in `test_generalization.py`.

**Behobene Ursachen-Klassen** (Ausgangspunkt: Ursachenanalyse `reports/golden_uncertain_analysis.md`; keine
einzelne Golden-Frage wurde als Claim aufgenommen):
1. **Semantische Normalisierung** (`knowledge/semantics/lexicon.json`, 57 Einträge):
   * Jeder Eintrag hat `canonical_concept`, `valid_context`, `invalid_context` und `confidence`.
   * Handlungskonzepte (WARTEN, WEITERFAHREN, ANHALTEN, VORLASSEN …) mit Unverträglichkeiten.
   * Exklusive Situationen: Polizeizeichen, Ampelfarbe, Haltverbotsart, Zeichennummer.
   * Gegensätze: rechts/links.
   * Eine Verneinung wird nie von einem Platzhalter verschluckt.
2. **Wortbildung:**
   * Komposita werden nur in Teile zerlegt, die in der Wissensbasis vorkommen.
   * Trennbare Verben werden zusammengesetzt („schleppen … ab“).
   * Partizipien werden auf den Verbstamm zurückgeführt.
   * Flexions-Alias für Stämme, die der Stemmer verschieden behandelt.
3. **Bedingungen und Spezialität:**
   * Qualifier, die die Frage nennt, eine allgemeine Regel aber nicht, machen die allgemeine Regel unsicher.
   * Ein Oberbegriff deckt den Unterbegriff ab (Wohnanhänger ⊂ Anhänger).
   * Sonderfälle einer Regel, die die Frage nicht nennt, gelten nicht (`condition_unmet`).
   * Widerspricht eine situationsspezifischere Regel der allgemeinen, ist das Ergebnis UNKNOWN (Ausnahme).
4. **Polarität am richtigen Prädikat:**
   * „nicht X, sondern Y“
   * ein vorangestelltes „Nichts,“
   * „niemand“
   * „nicht mehr X als“ → höchstens
   * Kurzantworten auf W-Fragen werden mit der Frage gelesen, und eine Negativfrage wird dabei nicht doppelt
     invertiert.
   * Eine nackte Zahl übernimmt die Wahrheit des passenden Claims.
5. **Gemeinsame Lesart der Antworten:**
   * Schließt die Handlung einer Antwort die einer belegten Antwort aus, ist sie FALSCH.
   * „Wer hat Vorrang?“: Nur eine Partei hat Vorrang.
   * „A und B“ wird Teilsatz für Teilsatz geprüft.
   * **Kein Ausschlussverfahren:** Gemessen machte es aus versteckten Fehlurteilen falsch-sichere Antworten.
6. **Zeichen:**
   * Abdeckung statt Kosinus, der amtliche Name zählt.
   * Eine „ohne X“-Antwort widerspricht einem Zeichen, das X anordnet.
   * Fällt die Bedeutung zu knapp aus, wird der amtliche Text herangezogen.
   * Bei unklarer Verneinung: UNKNOWN.
7. **Fehler im Code:** Modalwörter mit Umlaut (dürfen, müssen, unzulässig) wurden nicht aus den Inhaltswörtern
   entfernt, weil der Stamm vor der Umlautfaltung gebildet wurde.

**Ergebnisse** (Schwellen unverändert, `safety.theory_crosscheck` bleibt aus):

| Satz | n | overall accuracy | coverage | accuracy_when_answered | UNCERTAIN | false-confident |
|---|---|---|---|---|---|---|
| Ausgangslage synthetisch | 5 152 | 76,0 % | 76,0 % | 100 % | 24,0 % | 0 % |
| Synthetisch jetzt | 5 240 | 77,2 % | 77,2 % | 100 % | 22,8 % | 0 % |
| Validation (8 Varianten) | 2 016 | 71,4 % | 71,4 % | 100 % | 28,6 % | 0 % |
| ↳ ohne „konkurrierende Regel“ | 1 764 | ≈ 80 % | | 100 % | ≈ 20 % | 0 % |
| ↳ konkurrierende Regel als Zusatz-Distraktor | 252 | 9,5 % | 9,5 % | 100 % | 90,5 % | 0 % |
| Golden v1 (erste Messung → jetzt) | 80 | 21,3 % → **52,5 %** | 52,5 % | 85 % → 100 % | 75,0 % → 47,5 % | 3,75 % → **0 %** |
| Golden v2 (erste Messung → jetzt) | 80 | 20,0 % → **38,8 %** | 38,8 % | 84 % → 100 % | 76,3 % → 61,3 % | 3,75 % → **0 %** |
| **Golden intern gesamt** | 160 | **45,6 %** | 45,6 % | 100 % | **54,4 %** | **0 %** |
| Golden extern | 0 | – (noch keine Fragen) | | | | |

**Ziel verfehlt:** 60 % overall und höchstens 40 % UNCERTAIN wurden nicht erreicht. Das false-confident-Ziel
(≤ 1 %) ist erfüllt. Die Gründe stehen in `reports/golden_uncertain_analysis.md`. Die größten Restblöcke sind:
* Paraphrasen ohne Wortüberlappung (22)
* Falsch-Optionen, die keine Regel ausdrücklich ausschließt (16)
* Ja/Nein-Fragen zu fehlendem Wissen (13)
* Zahlen in Bedingungen (8)

Rund 90 Einzelantworten haben **keinen** inhaltlich passenden Claim in der Wissensbasis. Das ist eine
Wissenslücke, die man nicht mit „Tricks“ schließen darf. Die Golden-Sets wurden zur Ursachenanalyse benutzt und
sind deshalb **nicht mehr unabhängig**. Die eigentliche Messung der Generalisierung steht noch aus und kann nur
die externe, menschlich geschriebene Menge liefern.

## Meilenstein „External Validation + Semantic Generalization“

**Development golden:** v1/v2 heißen im Code `development_golden` (`Split.DEVELOPMENT_GOLDEN`). Sie dienen nur noch
als Regressionstest und liefern historische Werte. Sie erzeugen keine Claims, Synonyme oder Spezialregeln und
werden nicht zum Einstellen einzelner Fragen benutzt.

**External golden** (`tests/theory/golden_external/`, nur Auswertung):
* **Importer** (`tools/external_import.py`) prüft:
  * Format, Autor, eindeutige IDs
  * Duplikate, auch gegen frühere Importe
  * **Leakage-Erkennung** (`smart360/theory/leakage.py`): lexikalische plus normalisierte semantische Ähnlichkeit
    gegen Claims, Generator, Development Golden, Lexikon und Prompts. Treffer heißen `POSSIBLE_LEAKAGE` und
    zählen nicht zur unabhängigen Hauptmetrik.
* Importierte Dateien sind per SHA-256 in `MANIFEST.json` gesperrt.
* Die erste Messung wird einmalig in `reports/external_first_measurement.json` eingefroren.
* **Stand: leer.** Es gibt noch keine externe Messung.

**Hybride Regel-Suche** (`retrieval.py`):
* **RuleFrame** für jede Regel und Frage: intent, actors, action, objects, road/vehicle context, conditions,
  exceptions, modality, numeric constraints, traffic signs, priority relation.
* **Kandidaten-Kanäle:**
  * lexikalisch
  * semantisch: normalisierte Konzepte plus Zeichen-4-Gramme, TF-IDF. Ein Embedding-Backend lässt sich optional
    einstecken; ab Werk ist keines aktiv, es gibt keine neue Abhängigkeit.
  * Concept-Graph-Erweiterung um eine Stufe, nur typisierte Kanten
* **Ranking:** nach passenden, fehlenden und widersprüchlichen Bedingungen sowie der Quellenqualität.
* **Semantik schlägt nur Kandidaten vor.** Das Urteil fällt deterministisch. Ein Test mit einem
  Zufalls-Embedding beweist, dass keine Antwort sicher wird, die die Regeln nicht belegen.
* Claims, deren Situation der Frage widerspricht, werden übersprungen (innerorts ↔ außerorts, Lkw ↔ nur Pkw).

**Gegenbeweise:**
* **`contradiction.py`** erzeugt `reports/contradiction_index.json` mit 791 Relationen: contradicts,
  incompatible_with, exception_to, narrower_than, broader_than. Quellen sind nur Lexikon, Claims, Concept Graph
  und Qualifier.
* **`prove_false.py`** macht eine Option nur mit einem Beweis aus **verifiziertem** Wissen in derselben Situation
  FALSCH:
  * Handlung widerspricht einer geforderten Handlung
  * der amtliche Zeichentext verbietet die Handlung, ohne Ausnahmen und ohne Zahlenbedingung
  * eine verifizierte Ausnahme bricht ein „immer/nie“
* „A ist richtig, also ist B falsch“ ist kein Beweis.
* Gemessen: 57 Beweise auf synthetischen und Validierungsfragen, **alle korrekt**.

**Weitere Bausteine:**
* **Ja/Nein:** volle Proposition aus Frage und Antwort („ich darf nicht hier halten“). Bedingungen bleiben Teil
  der Aussage. Dazu kommt die neue Validierungs-Variante `val_yesno`.
* **Rollen:**
  * Sie → ich
  * es / dieses Fahrzeug → der Verkehrsteilnehmer aus der Frage
  * dort / hier → der Ort aus der Frage
* **Zahlenmodell** (`numeric_model.py`): Zahlen sind Fakten mit Größe, Vergleich und Bedingungen.
  * Eine nackte Zahl wird nur von verifizierten Fakten beurteilt, deren Bedingungen die Frage nennt.
  * Welche Größe gefragt ist, kommt nur aus der Fragephrase.
  * Schwellen-Claims („mehr als 20 l“) werden nicht mehr per Gleichheit verglichen. Das war eine latente
    Fehlurteilsklasse. Diese strengere Regel kostet 3 Fragen im Development Golden: 10 Zahlenantworten, die
    vorher per Gleichheit entschieden wurden, sind jetzt UNKNOWN.

**Wissen und Quellen:**
* **Wissenslücken** (`reports/knowledge_gap_clusters.md`): 59 Antwortoptionen ohne passenden Claim, gruppiert
  nach nächster amtlicher Norm, Thema und Lückentyp.
* **Manueller Quellenimport** (`knowledge/sources/manual/`, `tools/manual_source_import.py`) für FeV/StVG/BKatV:
  parse → amtliche Merkmale prüfen → Snapshot mit Herkunft → Evidenzprüfung → Bericht. Die Wissensbasis wird
  dabei nie automatisch geändert.
* **Unverified-Politik:**
  * Unverifiziertes Wissen erzeugt nie hohe Confidence (Reason → UNCERTAIN).
  * Es kann den Crosscheck nie blockieren lassen.
  * Im Tutor erscheint es nur als Lernstoff (`learning_only`).

**Tutor:**
* Bei einem Fehler kommt zuerst das Konzept, dann: Regel → Warum? (amtlicher Text) → Merksatz → Beispiel → neue
  Variante → Wiederholung.
* Stufen 1–6 (`levels.py`): direkte Regel, Umformulierung, Distraktor, Ausnahme, Kombination, Bild/Situation.
* Mastery wächst mit neuen Formulierungen, Kontexten und Ausnahmen sowie verzögerten Wiederholungen. „Gemeistert“
  (≥ 80) braucht 3 Stufen **und** eine Wiederholung nach mindestens einem Tag.

**Ergebnisse** (Schwellen unverändert):

| Satz | n | overall accuracy | coverage | accuracy_when_answered | UNCERTAIN | false-confident |
|---|---|---|---|---|---|---|
| Synthetisch | 5 240 | 77,5 % | 77,5 % | 100 % | 22,5 % | 0 % |
| Validation (9 Varianten) | 2 049 | 72,4 % | 72,4 % | 100 % | 27,6 % | 0 % |
| ↳ ohne „konkurrierende Regel“ | 1 797 | ≈ 81 % | | 100 % | | 0 % |
| Development Golden v1+v2 | 160 | 44,4 % | 44,4 % | 100 % | 55,6 % | 0 % |
| Golden extern | 0 | – (leer) | | | | |

**Latenz** nach dem Aufwärmen (synthetisch, p50 / p95):
* Regelsuche: 7 / 13 ms
* Prüfung: 3 / 8 ms
* gesamt: 11 / 20 ms

Der Kaltstart (Index aufbauen) dauert etwa 2 s. Die App wärmt deshalb im Hintergrund vor, sobald der Crosscheck
an ist.

**Ziel verfehlt:** 60 % auf dem internen Golden-Set wurden nicht erreicht (44,4 %).
* Die größte Restursache sind **fehlende Aussagen** in der Wissensbasis: 59 Optionen ohne passenden Claim, die
  Hälfte davon ohne eindeutige Norm.
* Dazu kommen Falsch-Optionen ohne verifizierten Gegenbeweis.
* Weder Schwellen noch Golden-Fragen wurden angefasst.

## Phase „Knowledge Completeness“ (2026-10-01)

**Amtliche Quellen:**
* FeV, StVG und BKatV sind **nicht integriert**.
* Der Abruf über das Rechtsinformationsportal liefert „NOT FOUND“: Der Testbestand enthält nur StVO, StVZO, eKFV
  und BABRiGeschwV.
* Der Abruf von gesetze-im-internet.de über den GitHub-Runner (`knowledge-watch.yml`, Eingabe `fetch_gii`) bricht
  mit HTTP-Timeout ab, ebenso aus dieser Umgebung (Netzwerkrichtlinie).
* Es wurde keine Sperre umgangen.
* Manueller Weg: `knowledge/sources/manual/README.md` mit den drei Dateien, dann
  `python windows/tools/manual_source_import.py --all`.

**Wissen je Norm geschlossen** (`windows/tools/analysis/norm_coverage.py` → `reports/norm_coverage.md`):
* Abgedeckte Einzelvorschriften: **308 → 400 von 492** (StVO §§ 1–43 mit Anlagen, zitierte StVZO-Normen, eKFV,
  BABRiGeschwV).
* Regeln: **92 → 132**. Claims: **403 → 512**.
* Alle neuen Regeln sind *verified*: Jede Evidence ist wörtlich im amtlichen Snapshot enthalten
  (`kb_builder.src` prüft das vor dem Schreiben). Evidence-Fehler: 0.
* Neue Gebiete:
  * StVO: Überholen und Zeichen, Fahrstreifen, Licht, Halten und Parken (Parkuhr, Parkscheibe, Handyparken),
    Fahrgäste, Fußgänger, Verbände, Bahnübergänge, Polizei, Sonderrechte, Werbung, Verkehrseinrichtungen,
    Zusatzzeichen, Markierungen, Ortstafel und Reißverschluss, Erlaubnispflicht (Rennen, Übergröße), Tonfolge,
    Gefahrzeichen mit Pfeil
  * StVZO: HU-Pflicht und Plakette, Reifen, Winterreifen, Warndreieck, Warnleuchte und Warnblinkanlage
  * eKFV: E-Scooter-Verkehrsflächen, Betriebserlaubnis und Versicherungsplakette, Bremsen, Blinker, Lichtzeichen,
    Verkehrsverbote
* Die Test-Sets wurden dafür nicht gelesen. Die nicht abgedeckten Vorschriften sind überwiegend nicht
  prüfungsrelevant: Militär, Feiertage, Bauvorschriften der eKFV, Wegweiser.

**Allgemeine Engine-Korrekturen** (keine Frage-Sonderfälle):
* Eine Antwort, die einen *unterscheidenden* Situationsbegriff eines Claims nennt, wird in dieser Situation
  beurteilt. Begriffe aus dem Regeltitel und gemeinsame Begriffe aller Claims zählen dabei nicht.
* Ein wahrer Claim mit Menge („etwa 100 m“) bestätigt keine Antwort ohne Menge (`claim_quantity_missing`).
* Gegensatz-Dimension `QUANTITY_LIMIT`: „mehr X als“ widerspricht „höchstens X“ (nach Normalisierung von „nicht
  mehr … als“).
* In der Spezifität zählen die Teile eines zusammengesetzten Worts einmal: „bahn“, „übergang“ und „bahnübergang“
  sind ein Begriff.
* Widerspricht ein Claim derselben Regel mit *genau der Menge der Antwort*, wird ein Mengenvergleich gegen einen
  anderen Claim nicht entschieden (`exact_quantity_claim_disagrees` → UNCERTAIN).
* Lexikon: 21 Objekt-Konzepte, z. B. Warndreieck, Parkscheibe, E-Scooter, Bahnübergang. Sie dienen nur der
  Struktur (RuleFrame). Es wurden keine Synonyme aus Testfragen übernommen.

**Messung** (Start = Commit 62b2bdb; FC = false-confident):

| Set | Accuracy | Coverage | UNCERTAIN | Acc. beantwortet | FC |
|---|---|---|---|---|---|
| synthetisch (5240 → 5936) | 77.5 % → **88.4 %** | 77.5 % → 88.4 % | 22.5 % → 11.6 % | 100 % → 100 % | 0 → **0** |
| Validierung (2049 → 2433) | 72.4 % → **82.4 %** | 72.4 % → 82.4 % | 27.6 % → 17.6 % | 100 % → 100 % | 0 → **0** |
| Development golden (160, nur Regression) | 44.4 % → **45.6 %** | 44.4 % → 45.6 % | 55.6 % → 54.4 % | 100 % → 100 % | 0 → **0** |
| External golden | leer, unverändert | – | – | – | – |

* Synthetisch und Validierung entstehen aus den Claims selbst. Neue Regeln erhöhen dort die Werte auch durch
  Selbstabgleich. Aussagekräftig für die Generalisierung bleibt nur ein externes Set.
* Topic 02 (Alkohol), 03 (Recht) und 14 (Führerscheinklassen) bleiben schwach, weil ihre Regeln aus FeV/StVG
  stammen und *unverified* sind. Die Engine antwortet dort bewusst UNCERTAIN.

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
  * Fahrphysik jenseits der Faustformeln
  * Assistenzsysteme (keine amtliche Norm im Bestand)
  * Umweltfahrweise im Detail
* Tunnel (Z 327), Zusatzzeichen (§ 39 Abs. 3), Umweltzone (Z 270.1), Gefahrgut (Z 261/269) und Wildwechsel
  (Z 142) sind nur in Grundzügen abgedeckt (verified).
* Wenige Paraphrasen: Die Engine versteht vor allem Formulierungen, die nah an ihren Claims sind.
