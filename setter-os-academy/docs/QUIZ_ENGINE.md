# QUIZ_ENGINE

Implementierung `src/lib/engine/quiz.ts` · UI `src/components/QuestionRenderer.tsx` · Inhalte `content/questions/*.json` · Validator `src/lib/content/validate.ts`.

## Fragetypen und Bewertung

| Typ | `type` | Bewertung | Teilpunkte |
|---|---|---|---|
| Single Choice | `single` | richtig/falsch; Distraktor liefert Denkfehler + Fehlerkategorie | nein |
| Mehrfachauswahl | `multi` | (Treffer − Fehlgriffe) / Anzahl richtiger, ≥ 0; volle Punkte nur bei exakter Menge | ja |
| Richtig/Falsch | `truefalse` | richtig/falsch | nein |
| Zuordnung | `matching` | Anteil korrekter Paare | ja |
| Reihenfolge | `ordering` | Anteil korrekt geordneter Nachbarpaare; voll nur bei exakter Folge | ja |
| Lückentext | `cloze` | normalisierter Vergleich mit akzeptierten Varianten (Groß/klein, Umlaute, Satzzeichen) | ja |
| Freitext | `freetext` | transparente Muster-Rubrik (Pflichtgruppen, verbotene Formulierungen) → **immer vorläufig** (`needsManualReview`), zählt nicht für Bestehen | – |
| Situationsentscheidung | `situation` | best = 1, acceptable = 0,5, poor/unacceptable = 0, jeweils mit Feedback | ja |
| Fehlererkennung | `errorspot` | (gefundene − Fehlalarme) / Fehlerzeilen | ja |
| Kennzahlenberechnung | `calculation` | absolute Toleranz; deutsches Zahlenformat; Daten als Simulation gekennzeichnet | nein |
| CRM-Aufgabe | `crm` | Anteil korrekter Felder; simulierter Datensatz | ja |
| Praktische Gesprächsaufgabe | → Simulator | siehe SIMULATION_ENGINE | – |

**Bestehen:** Mittelwert der automatisch bewerteten Scores ≥ `passThreshold` (Modul 1: 0,8, inklusiv). Freitext wird separat ausgewiesen.

**Keine Scheingenauigkeit:** Ergebnisse werden auf 0,1 % gerundet; Freitext-Scores heißen „Selbstcheck“ und werden nie als Note angezeigt.

## Metadaten je Frage (Pflicht, vom Validator geprüft)

`id` (eindeutig) · `moduleId` · `objectiveId` (muss existieren) · `difficulty 1–5` · `prompt` · Lösung · `explanation` (≥ 20 Zeichen) · `sourceIds` (≥ 1, existierend) · `version` · optional `negation`, `tags`. Distraktoren bei Single/Multi brauchen `misconception` (geprüfter Denkfehler). Keine doppelten Fragen (Prompt + Typ). Reihenfolge-Items dürfen nicht schon in Lösungsreihenfolge stehen. Rechenaufgaben/CRM müssen `simulatedData: true` tragen.

## Skalierung auf ≥ 1.000 Fragen

- Eine Datei pro Modul (`content/questions/Mxx.json`), IDs `Q-Mxx-nnn` (3-stellig → 999 pro Modul).
- Abfragen über Lernziel/Typ/Schwierigkeit/Tags; Datenbank-Index `(module_id, objective_id)`.
- Prüfungsvarianten ziehen deterministisch per Seed aus Pools je Lernziel (Master-Prüfung `variant_seed`).

## Bestand

Modul 1: **30 Fragen**, alle 11 Typen, 6 Lernziele. Gesamtziel interne Beta: ≥ 150 (OPEN: Module 2–12).

## Tests

51 Regressionstests (R01–R51) gegen echte Kursfragen, u. a.: Negationsfragen, „alles anklicken“ wird nicht belohnt, Teilpunkte, Fehlalarme, Toleranzen, deutsche Zahlen, Freitext nie final, Determinismus (100×), jede Frage mit Musterlösung voll lösbar.
