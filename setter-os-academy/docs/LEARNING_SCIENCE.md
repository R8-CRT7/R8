# LEARNING_SCIENCE – Didaktische Architektur

Stand 03.10.2026. Evidenzstatus je Quelle siehe SOURCE_REGISTER. **Übertragbarkeit auf Vertriebskompetenz ist nicht direkt erforscht** – alle Designentscheidungen sind begründete Annahmen, die im Pilot gemessen werden.

## 1. Prinzipien, Evidenz, Grenzen, Umsetzung

| Prinzip | Evidenz (Auswahl) | Grenzen | Umsetzung in SETTER OS |
|---|---|---|---|
| **Retrieval Practice / Active Recall** | Dunlosky et al. 2013: höchste Nützlichkeit („practice testing“); Rowland 2014 Meta-Analyse Testing-Effekt (unverifiziert) | Wirkt v. a. bei Abruf mit Feedback; Effekt geringer bei sehr komplexem Material ohne Vorwissen | 2–3 Abrufübungen **in jeder Lektion**, nicht erst am Ende; Abschlussquiz; Wiederholungszentrum |
| **Spaced Repetition** | Dunlosky 2013 (distributed practice: hoch); Cepeda et al. 2006 (unverifiziert) | Optimale Abstände hängen vom Prüfzeitpunkt ab | Leitner-Boxen 1/3/7/16/35 Tage (`src/lib/engine/review.ts`) |
| **Interleaving** | Sana & Yan 2022: 63 % vs. 54 % (blockiert) nach 1 Monat | Schulkontext; bei völlig neuem Stoff zunächst blockiert sinnvoller | Lektionen blockiert (Einführung), Abschlussquiz und Wiederholung **gemischt** nach Lernziel |
| **Feedback** | Wisniewski et al. 2020: d = 0,48, informationsreich > knapp; Kluger & DeNisi 1996: ein Teil der Interventionen schadet (v. a. personenbezogen) | Heterogen | Aufgabenbezogenes Feedback: Denkfehler je Distraktor, Erklärung, Quelle. Coach-Feedback zu Gesprächsstellen, nie zur Person |
| **Worked Examples** | Sweller et al. 2011 (unverifiziert) | Expertise-Reversal (Kalyuga 2007): bei Fortgeschrittenen weniger hilfreich | Block-Typ `workedExample` in M01-L02/L04; Fading in späteren Modulen geplant |
| **Scaffolding** | Kalyuga 2007 | Muss abgebaut werden | Simulator mit Auswahlnachrichten (Scaffold) → später Freitext-Modus (KI) |
| **Deliberate Practice** | Macnamara et al. 2014: Varianzaufklärung in Berufen gering | Kein „10.000-Stunden-Versprechen“ | Wiederholbare Szenarien mit gezieltem Feedback auf schwächste Kompetenz |
| **Transfer** | – (allgemeine Literatur) | Nahtransfer ≠ Ferntransfer | Transferaufgabe je Modul (eigener Leitfaden), Branchen-Szenarien, Master-Abschlussprojekt |
| **Metakognition / Kalibrierung** | Allgemeine Forschung zu Judgments of Learning (nicht recherchiert) | – | Sicherheitsangabe (geraten/unsicher/sicher) pro Antwort; Kalibrierungslücke in Statistik; Reflexionsfragen |
| **Cognitive Load** | Sweller et al. 2011 | – | Lektionen 8–12 Min., eine Frage pro Bildschirm, keine Dekoanimationen, Mobile-first |
| **Mastery Learning** | Kulik et al. 1990 (unverifiziert) | Zeitaufwand | Bestehensgrenze 80 %, beliebig wiederholbar; „gesichert“ erst nach verzögertem Abruf |
| **Motivation / Self-Efficacy** | Bandura 1977 (unverifiziert); Deci et al. 1999: erwartete Belohnungen können intrinsische Motivation senken; Sailer & Homner 2020: Gamification kleine–mittlere Effekte | Belohnungen dürfen nicht das Ziel werden | Erfolgserlebnisse durch echte Kompetenz (Simulation bestanden), XP nur für Lernhandlungen, keine Strafen (siehe §4) |
| **Formative Assessment** | Wisniewski 2020 | – | Jede Übung ist formativ; nur Modul-/Master-Prüfung summativ |

## 2. Lernzyklus pro Modul

1. **Aktivieren** – kurze Einordnung, Lernziele sichtbar
2. **Erklären** – Text, Beispiel, Worked Example
3. **Abrufen** – eingebettete Checks (sofortiges Feedback)
4. **Anwenden** – Fallstudie, Situationsentscheidung, Simulation
5. **Reflektieren** – Reflexionsfrage, Sicherheitsangabe
6. **Prüfen** – Abschlussquiz (gemischt), Transferaufgabe
7. **Festigen** – verteilte, gemischte Wiederholung

## 3. Adaptiver Algorithmus (transparent, kein ML)

Pro Frage (`ItemReview`): Box 1–5, Versuche, richtig, falsch, letzter Score, letzte Übung, nächste Fälligkeit, letzte Sicherheit.

Regeln (`scheduleNext`):
- Falsch (Score < 1) → Box 1, fällig in 1 Tag
- Richtig + „geraten“ → Box bleibt
- Richtig sonst → Box + 1 (max. 5), Intervall 1/3/7/16/35 Tage
- Freitext (vorläufige Bewertung) → **verändert die Box nicht**

Pro Lernziel (`summarizeObjective`) werden getrennt geführt:

| Größe | Art | Berechnung |
|---|---|---|
| Versuche, richtig, falsch, Fehlerkategorien, Ø Bearbeitungszeit, letzte Übung | **gemessen** | Zählung |
| Leistung | **gemessen** | gewichteter Mittelwert der letzten 8 Versuche (neuere stärker) |
| Kalibrierungslücke | **gemessen** | Ø (Sicherheit/3 − Score) |
| Simulationsleistung | **gemessen** | Ø Gesamtwert verknüpfter Simulationen |
| Kompetenz-Einschätzung | **geschätzt** | `nicht_geprüft` → `im_aufbau` → `gefestigt` (≥ 3 Versuche, ≥ 80 %) → `gesichert` (zusätzlich ≥ 2 Lerntage, korrekter Abruf ≥ 3 Tage nach Erstkontakt, Simulation ≥ 70 falls vorhanden) |

XP, Level, Logins und Lerntage fließen **nicht** in die Kompetenzeinschätzung ein (getestet: K01–K07).

## 4. Gamification-Regeln

| Element | Regel | Begründung |
|---|---|---|
| XP | nur für Lernhandlungen (Lektion, erste richtige Antwort, Wiederholung, Quiz bestanden, Simulation, Transfer). Keine XP für Logins. | Deci et al. 1999 |
| Level | 6 Stufen; Hinweis „misst Aktivität, nicht Kompetenz“ überall | Trennung Aktivität/Kompetenz |
| Lernserie | **Aktive Tage der letzten 7 Tage** statt brechender Streak | Kein Druck, Pausen erlaubt |
| Erfolge | an echte Verhaltensweisen gekoppelt (z. B. „Nein heißt Nein“, „Saubere Übergabe“, „Langzeitgedächtnis“) | Werte statt Klicks belohnen |
| Verlust | **Nichts wird je entzogen** (DB-Constraint `amount > 0`, Erfolge ohne Widerruf) | Brief §8 |
| Lernpause | Schalter in Einstellungen | Brief §8 |
| Ranglisten | nur Opt-in, erst mit Cloud-Konten | Vergleichsdruck vermeiden |
| Käufe | keine Kaufauslöser, keine Lootboxen | Brief §8 |
| Geplant | Skill Tree (vorhanden, statisch), Wochen-Challenges, Boss Challenges (= Modulsimulation unter Prüfungsbedingungen), Missionen | Roadmap |

## 5. Messung im Pilot

Siehe TEST_PLAN.md §Pilot: Vortest/Nachtest je Modul, verzögerter Abruf nach 7 und 30 Tagen, Simulationswerte vor/nach Modul, Kalibrierung, subjektive Verständlichkeit (1–5), SUS-Fragebogen.
