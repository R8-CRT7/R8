# SIMULATION_ENGINE – Customer Simulator & AI Sales Coach

## 1. Zwei getrennte Rollen

| | Customer Simulator (`src/lib/engine/customer.ts`) | Sales Coach (`src/lib/engine/coach.ts`) |
|---|---|---|
| Aufgabe | spielt den Interessenten | bewertet das beendete Gespräch |
| Kennt | verborgene Fakten, Antwortregeln, Rapport, Flags | Rubrik, Gewichte, Gates, Zug-Metadaten, Übergabenotiz |
| Kennt nicht | Punktzahlen, Gewichte | — produziert **nie** Kundenantworten |
| Ausgabe | neuer `SimulationState` (pur, deterministisch) | `SimulationEvaluation` |

Beide sind reine Funktionen → gleiche Eingabe = gleiches Ergebnis (Tests S07, C18). Kein API-Zugang nötig.

## 2. Szenario-Modell (`content/scenarios/SIM-xxx.json`)

- **Ausgangslage** (`briefing`, sichtbar), **Persona**, Markt, Richtung, Kanal, Schwierigkeit.
- **Verborgene Fakten** (`facts`): z. B. Bedarf, Eigentum, Zeitrahmen, Entscheider, Budget; `requiredForQualification`; je Fakt ≥ 2 plausible Distraktoren für die Übergabenotiz.
- **Züge** (`moves`): Nachrichten, die der Lernende wählen kann, mit `intent`, `quality` (good/ok/weak/bad), Kompetenzpunkten, Rapport-Effekt, `reveals`, Voraussetzungen (`requires` Fakten, `requiresFlags`), Ausblendung (`hiddenByFlags`), optional `violation` (rechtlich/ethisch), `coachNote`, `betterMoveId`.
- **Kundenantworten** (`reply`): Varianten mit Bedingungen (Mindest-Rapport, Fakten bekannt/unbekannt, Flags), letzte Variante ist Default (vom Validator erzwungen). Antworten können Fakten preisgeben (`reveals`) und das Gespräch beenden (`ends`).
- **Ergebnisse:** `idealOutcome`, `acceptableOutcomes` aus `book | nurture | disqualify | respect_no | handoff`; Zeitlimit `maxTurns` → `lost`.

### Informationsregeln
1. Fakten werden **nur** durch passende Fragen sichtbar – der Kunde verrät nicht alles von selbst.
2. Eine Frage liefert ihren Fakt nur, wenn der Rapport > 1 ist (verärgerte Kunden teilen nichts; Test S08).
3. Was der Kunde ausdrücklich in seiner Antwort sagt (`reply.reveals`), gilt immer als bekannt (Test S12).
4. Mehrere sinnvolle Verläufe sind möglich (Test S06; erschöpfende Suche S10/S11 belegt für jedes Szenario mindestens einen bestehbaren und einen an einem Gate scheiternden Pfad).

## 3. Vorhandene Szenarien (Vertical Slice)

| ID | Archetyp | Markt/Kanal | Ideal | Prüft besonders |
|---|---|---|---|---|
| SIM-001 | Interessierter Kunde mit Fachfrage (Wärmepumpe) | B2C, Website-Chat | Termin | Qualifizierung inkl. Mitentscheider, Förderfrage an Berater übergeben, Terminbestätigung |
| SIM-002 | Kunde ohne Budget / nicht qualifiziert (Agentur) | B2B, Instagram-DM | Disqualifizieren | Budget früh klären, ehrlich disqualifizieren, keine Erfolgsversprechen |
| SIM-003 | Kunde, der ausdrücklich keinen Termin möchte (PV) | B2C, WhatsApp | Nein respektieren | Nein sofort akzeptieren, Kontaktwunsch klären, keine Folgekontakte |

## 4. Geplante Szenarien (bis interne Beta ≥ 20)

Unsicherer Kunde · preisorientierter Kunde · skeptischer Kunde · unentschlossener Kunde · Kunde mit wenig Zeit · Kunde mit vielen Fragen · Kunde mit Einwänden (Partner, Konkurrenz) · falsche Erwartungen · komplexe Anforderungen (B2B SaaS, Buying Center) · No-Show-Recovery · Terminverschiebung · Recruiting-Retainer · IT-Dienstleister · Unternehmensberatung · Lead-Reaktivierung (Einwilligung prüfen) · Outbound B2B (mutmaßliche Einwilligung) · Stromspeicher-Nachrüstung.

## 5. Ablauf in der UI

Briefing → Gespräch (Auswahl aus deterministisch gemischten Nachrichten, Tipp-Indikator, Notizen-Spalte mit erfahrenen Fakten) → **Übergabenotiz** (für jeden Fakt: Wert oder „Nicht erfragt / unbekannt“) → Auswertung.

## 6. Datenminimierung

Gespeichert werden nur Szenario-ID/-Version, Zug-IDs, Übergabe-Auswahl und die Kennzahlen. Der Text-Verlauf wird bei Bedarf per `replay()` rekonstruiert (Test P06). Keine Freitexte, keine echten Personen.

## 7. Spätere KI-Variante (nicht aktiv)

Freitext-Eingabe statt Auswahl. Der KI-Kunde erhält Persona + Fakten + Offenlegungsregeln; eine **deterministische Prüfschicht** ordnet jede Nutzernachricht einem Intent/Zug zu (Klassifikation mit Konfidenz; bei Unsicherheit Rückfrage an den Lernenden oder manuelle Prüfung). Bewertung bleibt Rubrik + Gates; KI liefert nur Begründungstexte. Vor Aktivierung: Kosten-Freigabe, AV-Vertrag, Art.-50-Kennzeichnung, Konsistenz-/Fairness-Tests.
