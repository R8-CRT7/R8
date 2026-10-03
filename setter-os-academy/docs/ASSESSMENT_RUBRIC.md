# ASSESSMENT_RUBRIC – Bewertung von Simulationen, Transfer und Prüfungen

Rubrik-Version **1.0.0** (`RUBRIC_VERSION` in `src/lib/engine/coach.ts`). Jede Bewertung speichert die Rubrik-Version.

## 1. Simulationen

### Kompetenzen und Gewichte (Summe 100, Test C02)

| Kompetenz | Gewicht | Quelle des Werts |
|---|---|---|
| Gesprächseröffnung | 8 | Zugpunkte / Szenario-Ziel |
| Bedarfsermittlung | 14 | Zugpunkte / Ziel |
| Fragetechnik | 10 | Zugpunkte / Ziel |
| Aktives Zuhören | 8 | Zugpunkte / Ziel |
| Klarheit | 6 | Zugpunkte / Ziel |
| **Qualifizierung** | 16 | 60 % Abdeckung der Pflichtfakten + 40 % Zugpunkte |
| Umgang mit Einwänden | 10 | Zugpunkte / Ziel |
| Kundenorientierung | 8 | Zugpunkte / Ziel |
| Terminvereinbarung / Ergebnis | 8 | 60 Punkte ideales Ergebnis bzw. 40 zulässiges + 40 % Zugpunkte |
| Dokumentation | 6 | Übergabenotiz: bekannter Fakt richtig **oder** unbekannter als „nicht erfragt“ |
| Rechtliche & ethische Korrektheit | 6 | 100, bei jedem Verstoß 0 |

Kompetenzen ohne Ziel im Szenario gelten als **„nicht geprüft“** und fließen nicht in die Gesamtnote ein (Gewichte werden renormiert, Test C17). So wird dokumentiert, was tatsächlich geprüft wurde.

### Gates (harte Grenzen)

| Gate | Auslöser | Wirkung |
|---|---|---|
| G1 | Zug mit rechtlichem/ethischem Verstoß (Druck, falsche Versprechen, ignoriertes Nein, erfundener Social Proof) | max. 40, nicht bestanden |
| G2 | Termin gebucht, Pflichtfakten unvollständig | max. 60, nicht bestanden |
| G3 | Termin gebucht, obwohl Ideal „Disqualifizieren“ oder „Nein respektieren“ | max. 50, nicht bestanden |
| G4 | Übergabenotiz enthält Fakt, der nie erfragt wurde | max. 65, nicht bestanden |
| G5 | Kein zulässiges Ergebnis (z. B. Abbruch) | nicht bestanden |

**Bestanden:** Gesamt ≥ 70 **und** kein Gate ausgelöst. Ein gebuchter Termin kann schlechte Qualifizierung oder unzulässige Kommunikation nicht ausgleichen (Test C20).

### Feedback-Ausgabe (immer vollständig, Test C14)
1. Gesamtbewertung (+ Rohwert, falls durch Gates begrenzt) · 2. Bewertung je Kompetenz · 3. drei Stärken · 4. drei Verbesserungspunkte mit konkretem Hinweis · 5. entscheidende Gesprächsstellen mit Begründung · 6. verbesserte Beispielantwort (schwerster Fehler zuerst) · 7. verknüpfte Wiederholungsübung.

### Konsistenz & Fairness
Deterministisch (C18). Persona-Name/Herkunft beeinflusst die Bewertung nicht (C19). Spätere KI-Bewertung: nur ergänzende Begründung; Punktzahl und Gates bleiben regelbasiert.

## 2. Freitext & Transferaufgaben

- Automatischer **Selbstcheck** mit offengelegten Kriterien (Pflicht-Muster, verbotene Formulierungen) – nie finale Note.
- Finale Bewertung durch eine Person anhand der Kriterien der Aufgabe (z. B. 7 Kriterien in M01-Transfer). Skala je Kriterium: erfüllt / teilweise / nicht erfüllt. Bestanden ab 70 % und keinem Verstoß gegen Ethik-/Rechtskriterien.
- Zweitbewertung bei Prüfungsrelevanz (Master-Prüfung).

## 3. Modulprüfung

Regeln stehen vor Beginn in der Prüfungsansicht: Fragenzahl, gemischt, Bestehen ≥ 80 %, Teilpunkte, unbegrenzte Wiederholung, Speicherung mit Fragenversionen.

## 4. Master-Prüfung (Spezifikation `src/lib/masterExam.ts`, noch nicht freigeschaltet)

9 Teile: Fachwissen (≥ 80 %) · CRM-Praxis (≥ 9/10) · 3 Kundensimulationen (je ≥ 70, kein Gate) · Einwandbehandlung (≥ 4/6 „gut“) · Lead-Qualifizierung (≥ 7/8) · Terminorganisation (alle Pflichtkriterien) · rechtliche Fallentscheidung (4/4, K.-o.) · Kennzahlen (≥ 5/6) · Abschlussprojekt (Rubrik ≥ 70, Personenbewertung). Bestanden nur bei allen Teilen. Wiederholung einzelner Teile frühestens nach 3 Tagen mit neuen Varianten. Dokumentation der geprüften Kompetenzen. **Ein internes Zertifikat ist keine staatlich anerkannte Qualifikation und garantiert weder Beschäftigung noch Einkünfte.**
