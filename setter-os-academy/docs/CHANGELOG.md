# CHANGELOG

## [0.1.0-slice] – 2026-10-03
### Hinzugefügt
- Projektgrundlage `setter-os-academy/` (Next.js 16, React 19, TypeScript, Tailwind 4, Static Export).
- Recherche: Quellenregister (51 Quellen mit Prüfstatus), Wissensdatenbank (23 Einträge), Recherchebericht, Rechtsprüfliste mit Legal-Gate.
- Lehrplan für 12 Module; Modul 1 vollständig (6 Lektionen, 30 Fragen, Transferaufgabe).
- Quiz-Engine (11 Typen), Leitner-Wiederholung, Kompetenzschätzung, Gamification ohne Strafen.
- Customer Simulator + getrennter Sales Coach (Rubrik 1.0.0, Gates G1–G5), 3 Szenarien.
- Alle Kernansichten inkl. Admin/Content Studio, Mobile-Navigation, Dark/Light.
- PostgreSQL-Zielschema mit Versionierung, Unveränderlichkeit veröffentlichter Inhalte, Vier-Augen-Prinzip, Löschkaskade.
- Tests: 119 Unit/Regression/Schema, 12 E2E-Fälle × 2 Viewports inkl. axe (WCAG 2.2 AA).
### Behoben (während der Entwicklung)
- Löschkaskade (FK `created_by`), Faktenregel bei niedrigem Rapport, mobiles Chat-Scrolling, Logo-Gradient-ID.
### Bekannte Einschränkungen
- Siehe TEST_PLAN §2 „ungeprüft“ und OPEN_QUESTIONS.

## [0.2.0-stufe1] – 2026-10-03
### Hinzugefügt
- 90-Tage-Plan mit 7 Stufen, Kalender-Pacing, „Heute schon weitermachen“, Tagesabschluss, Stufen-Check als Tor (Quiz ≥ 80 % + Pflichtsimulationen), Übersicht „Themen beherrscht“.
- Kursbuch-Kapitel, Skill-Karten (Technik, Schritte, Beispiel, Evidenz, ethische Grenze) und Mythos-Checks als neue Lektionsbausteine.
- Modul 1 erweitert auf 8 Lektionen / 42 Fragen (≈ 2 h 50 min), Modul 2 „Professionelle Kommunikation“ neu: 7 Lektionen / 28 Fragen (≈ 2 h).
- Szenario SIM-004 (unsichere Kundin, Stromspeicher), Stufen-Check 1 mit 24 Fragen.
- 15 neue Quellen (u. a. Huang et al. 2017, Weger et al. 2014, Gollwitzer & Sheeran 2006, Carpenter 2013 + Re-Analyse).
- Lernzeit-Schätzung und Tests (≥ 2 h pro Modul, Plan-Logik P1–P10).
