# TEST_PLAN – Qualitätssicherung & Pilotphase

## 1. Tatsächlich ausgeführte Tests (03.10.2026, Linux-Container, Node 22, Chromium 141)

| Suite | Befehl | Tests | Ergebnis |
|---|---|---|---|
| Inhaltsvalidierung (CI-Gate) | `npm test` (tests/content.test.ts) | 3 | ✅ 0 Fehler (Warnungen werden ausgegeben) |
| Quiz-Engine – fachliche Regression | tests/quiz.test.ts | 51 (R01–R51) | ✅ |
| Simulator + Coach – fachliche Regression | tests/simulation.test.ts | 32 (S01–S12, C01–C20) | ✅ |
| Wiederholung, Kompetenz, Gamification, Persistenz/Migration | tests/learning.test.ts | 26 | ✅ |
| Datenbankschema gegen Postgres (PGlite) | tests/schema.test.ts | 7 (D01–D07) | ✅ |
| **Summe Unit/Regression** | `npm test` | **119** | ✅ |
| E2E Desktop (1280×720) | `npm run test:e2e` | 12 (1 nur mobil → übersprungen) | ✅ 11 |
| E2E iPhone-13-Viewport (Chromium-Emulation) | `npm run test:e2e` | 12 (1 nur Desktop → übersprungen) | ✅ 11 |
| Typprüfung | `npm run typecheck` | – | ✅ |
| Produktions-Build (Static Export, 38 Seiten) | `npm run build` | – | ✅ |

Fachliche Regressionstests: **83** (R01–R51, S01–S12, C01–C20) – Ziel ≥ 50 erfüllt.

Während der Tests gefundene und behobene Fehler:
- Löschkonzept: Nutzerlöschung scheiterte an Fremdschlüssel `course_versions.created_by` → `on delete set null` (D07).
- Simulator: ausdrückliche Kundenaussagen wurden bei niedrigem Rapport nicht als „erfahren“ gezählt → ehrliche Notiz wurde fälschlich als „erfunden“ (G4) gewertet. Regel getrennt (S12, E06).
- Mobile: Chatverlauf scrollte die ganze Seite, Antwortoptionen waren außerhalb des Sichtbereichs → interne Scrollfläche.
- Logo-Verlauf unsichtbar auf Mobilgeräten (doppelte SVG-ID in ausgeblendeter Sidebar) → `useId`.

## 2. Abdeckung nach Brief §16

| Bereich | Abgedeckt durch | Status |
|---|---|---|
| Registrierung | E02 (Pflichtfelder), Profilanlage in allen E2E | ✅ lokal |
| Login | Seite vorhanden (lokales Profil/Import) | ⚠️ **ungeprüft** (kein E2E für Import) |
| Lernfortschritt + Persistenz | E04 (Reload), P01–P08 | ✅ |
| Quizbewertung, Mehrfachantworten, Negationsfragen | R01–R51 | ✅ |
| Prüfungslogik | R49, E07, P05 | ✅ (Modulquiz); Master-Prüfung **nicht implementiert** |
| Wiederholungsalgorithmus | L01–L06, K01–K07 | ✅ |
| Simulationen, Szenariokonsistenz | S01–S12 (inkl. erschöpfender Pfadsuche) | ✅ |
| Bewertungslogik, Konsistenz, Fairness | C01–C20 | ✅ deterministisch; KI-Bewertung n/a |
| Datenmigrationen | P01–P04 | ✅ lokal; Cloud-Migration **ungeprüft** |
| Berechtigungen, Rechte und Rollen | DB-Constraints D02/D04 | ⚠️ RLS-Policies **nicht implementiert** |
| Adminfunktionen | manuell im Browser gesichtet | ⚠️ **kein automatisierter Test** |
| Mobile Darstellung | E09 (kein Overflow), E10 (Tap-Ziele), Screenshots | ✅ Emulation; **echtes iPhone/Safari ungeprüft** |
| Fehlermeldungen | E02, Import-Fehlerpfad (Code) | teilweise |
| Barrierefreiheit | E11 axe WCAG 2.2 AA dunkel+hell, E12 Tastatur | ✅ automatisiert; Screenreader **ungeprüft** |
| Sicherheit | Code-Review: keine Secrets, keine Fremd-Requests | ⚠️ kein Pentest |
| Datenschutz | P06 (Datenminimierung), D07, E08 (Löschen) | ✅ |

**Ausdrücklich ungeprüft:** echtes iOS-Safari/WebKit (in der Umgebung nicht installiert), VoiceOver, Admin-Editor-Export, Sicherungs-Import über UI, Lighthouse/Performance-Messung, sehr große Datenmengen, Mehrbenutzerbetrieb.

## 3. Pilotphase mit dem Gründer (Brief §17)

### Ablauf (6 Wochen, ca. 20–30 Min./Tag)
| Woche | Inhalt | Messung |
|---|---|---|
| 0 | **Vortest**: Modul-1-Abschlussquiz ohne Vorbereitung + SIM-001/002/003 je einmal | Ausgangswissen, Ausgangs-Simulationswerte |
| 1 | Modul 1 Lektionen, Checks, Transferaufgabe | Bearbeitungszeit, Check-Leistung, Verständlichkeit (1–5 je Lektion) |
| 1 | Abschlussquiz + alle 3 Simulationen | Quiz-%, Simulationswerte, Fehlerkategorien |
| 2 | nur Wiederholungszentrum (fällige Fragen) | Wiederholungsleistung, Kalibrierung |
| 2 | **verzögerter Test +7 Tage**: Quiz erneut, Simulationen mit anderem Pfad | Behaltensleistung |
| 5–6 | **verzögerter Test +30 Tage** | nachhaltiger Lernerfolg |
| laufend | Fehlerprotokoll (technisch/inhaltlich) | Bugliste |
| Ende | SUS-Fragebogen (10 Items), offenes Interview | Bedienbarkeit |

### Erhebungsbogen pro Sitzung (Vorlage)
Datum · Gerät (iPhone/Laptop) · Dauer · Lektion/Übung · Verständlichkeit 1–5 · „Was war unklar?“ · technische Fehler (Schritte, Screenshot) · Idee.

Auswertung: Export der Daten über *Einstellungen → Daten exportieren* (JSON) – enthält Versuche, Zeiten, Sicherheiten, Fehlerkategorien und Simulationswerte.

### Interpretation
- Ein einmal bestandenes Quiz ist **kein Nachweis dauerhaften Könnens** – maßgeblich sind +7/+30-Tage-Werte und Simulationen mit neuen Pfaden.
- n = 1 und Entwickler = Tester → starke Verzerrung. Ergebnisse dürfen **nicht** als Wirksamkeitsnachweis oder Werbeaussage verwendet werden.
- Für einen öffentlichen Start: Tests mit ≥ 5–8 weiteren Personen, die nicht an der Entwicklung beteiligt waren (Rekrutierung nur mit Einwilligung, Datenschutzinfo, anonymisierte Auswertung).

### Testbericht-Vorlage
Zusammenfassung · Messwerte (Tabelle vor/nach/+7/+30) · typische Fehler (Top-5-Kategorien) · Bedienbarkeit (SUS) · technische Fehler (Schwere A–C) · **priorisierte Verbesserungsliste** (Impact × Aufwand) · Grenzen der Aussagekraft.
