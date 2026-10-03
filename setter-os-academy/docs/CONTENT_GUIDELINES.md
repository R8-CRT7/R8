# CONTENT_GUIDELINES – Redaktionsleitfaden

## Grundsätze
1. **Wahrheit vor Wirkung.** Keine erfundenen Zahlen, Erfolgsquoten, Bewertungen, Referenzen oder Zertifizierungen.
2. **Quellenpflicht.** Jede fachliche Aussage verweist auf eine Quelle aus `content/sources.json`. Unverifizierte Quellen dürfen Lehrtext nur als „Praxis-Konvention“ oder „Annahme“ stützen.
3. **Aussagearten kennzeichnen:** Fakt · Expertenmeinung · Annahme · Modellrechnung. Korrelation nicht als Kausalität formulieren (Beispiel HBR 2011).
4. **Ethik:** Kein Inhalt lehrt, ein ausdrückliches Nein zu übergehen, künstliche Verknappung, Täuschung oder das Ausnutzen psychischer Schwächen.
5. **Recht:** Rechtsinhalte tragen „Stand MM/JJJJ – keine Rechtsberatung“, haben ein Prüfintervall von 14–90 Tagen und werden vor Veröffentlichung von einer Fachperson gegengelesen.
6. **Daten:** Alle Beispiele mit erfundenen Personen/Firmen; Rechen-/CRM-Daten mit `simulatedData: true` und sichtbarem Hinweis.
7. **Rollenklarheit:** Inhalte zeigen, wann ein Setter an eine Fachperson übergibt (Preis, Förderung, Technik, Steuer, Vertrag).

## Sprache
Deutsch, Du-Form gegenüber Lernenden, Sie-Form in Kundendialogen (B2C) bzw. passend zum Kanal (Instagram/B2B-Startups ggf. Du). Kurze Sätze, aktive Verben, ein Gedanke pro Absatz. Gendergerecht mit Doppelpunkt (Lernende:r) oder neutralen Formen. Keine Anglizismen, wo ein deutsches Wort klarer ist; Fachbegriffe beim ersten Auftreten erklären.

## Fragen schreiben
- Ein Lernziel pro Frage; Schwierigkeit 1–5 ehrlich einschätzen.
- **Jeder falsche Antwortweg testet einen plausiblen Denkfehler** (`misconception`) und hat eine Fehlerkategorie.
- Negationsfragen nur mit „NICHT“ in Großbuchstaben und `negation: true`.
- Keine Trickfragen, keine „Alle oben genannten“.
- Erklärung beantwortet: Warum richtig? Warum die Distraktoren falsch?
- Keine künstlichen Duplikate: Varianten müssen ein anderes Szenario oder eine andere Denkleistung prüfen.

## Szenarien schreiben
Ausgangslage sichtbar, Fakten verborgen; jede Kundenantwort plausibel und knapp; mindestens ein „guter“, ein „schwacher“ und ein „kritischer“ Zug je Phase; jeder schwache Zug mit `betterMoveId`; jeder Druck-Zug mit `violation`. Der Validator prüft diese Regeln.

## KI-Texte
KI darf Entwürfe liefern. Sie werden als `ai_generated` markiert, fachlich geprüft (Quelle!) und **nie automatisch veröffentlicht** (DB-Constraint).

## Aktualisierungsprozess
1. Admin → Qualitätsprüfung zeigt überfällige Quellen.
2. Quelle prüfen → Aussage, Prüfdatum, Version anpassen; abhängige Fragen/Lektionen (über `knowledge.json`-Verknüpfungen) prüfen.
3. Entwurf exportieren → Review durch zweite Person → neue Kursversion → `CHANGELOG.md`.
4. Pflichttermine: Recht alle 14–90 Tage (FernUSG-Reform aktuell alle 14 Tage), Sales-Technologie 60–180 Tage, Forschung 1–5 Jahre.
5. `node scripts/gen-source-register.mjs` aktualisiert das Quellenregister.

## Nutzerfeedback
Tabelle `content_feedback` (unklar/fehler/veraltet) – im Prototyp über Pilot-Erhebungsbogen. Jede Meldung bekommt Status und Bearbeitung im CHANGELOG.
