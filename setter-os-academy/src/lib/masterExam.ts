// Master exam blueprint – pass rules are defined BEFORE any attempt (ASSESSMENT_RUBRIC.md §Master-Prüfung).
// Status: specified, NOT yet runnable (requires modules 2–12). Shown transparently in the UI.
export const MASTER_EXAM = {
  id: "MASTER-1",
  version: "0.1.0-spec",
  parts: [
    { id: "P1", title: "Fachwissenstest", detail: "40 Fragen aus allen 12 Modulen, gemischt, je Variante neu gezogen", rule: "≥ 80 %", competencies: ["Fachwissen"] },
    { id: "P2", title: "CRM-Praxisaufgabe", detail: "10 Datensätze im Übungs-CRM pflegen, Status und nächste Aktion setzen", rule: "≥ 9 von 10 korrekt", competencies: ["Dokumentation", "Prozess"] },
    { id: "P3", title: "Drei Kundensimulationen", detail: "Je ein Szenario: Termin sinnvoll · Disqualifizierung sinnvoll · ausdrückliches Nein", rule: "jede ≥ 70, kein Gate verletzt", competencies: ["Gesprächsführung", "Qualifizierung", "Ethik"] },
    { id: "P4", title: "Einwandbehandlung", detail: "6 Einwände, schriftlich, Bewertung durch Rubrik + Person", rule: "≥ 4 von 6 mit „gut“", competencies: ["Einwände"] },
    { id: "P5", title: "Lead-Qualifizierung", detail: "8 Lead-Profile einordnen und begründen", rule: "≥ 7 von 8", competencies: ["Qualifizierung"] },
    { id: "P6", title: "Terminorganisation", detail: "Bestätigung, Erinnerung, Verschiebung, No-Show-Recovery formulieren", rule: "alle Pflichtkriterien erfüllt", competencies: ["Terminvereinbarung"] },
    { id: "P7", title: "Rechtliche Fallentscheidung", detail: "4 Fälle (B2C-Anruf, Cold Email, LinkedIn, WhatsApp) entscheiden und begründen", rule: "4 von 4 – Rechtsfehler sind K.-o.", competencies: ["Recht"] },
    { id: "P8", title: "Kennzahlenberechnung", detail: "6 Rechenaufgaben mit Simulationsdaten", rule: "≥ 5 von 6", competencies: ["Analytics"] },
    { id: "P9", title: "Abschlussprojekt", detail: "Setting-Prozess für einen (fiktiven) Kunden: ICP, Leitfaden, Qualifizierungskriterien, KPI-Plan", rule: "Rubrik ≥ 70, Bewertung durch Person", competencies: ["Transfer"] },
  ],
  rules: [
    "Bestanden nur, wenn alle Teile bestanden sind.",
    "Wiederholung einzelner Teile nach frühestens 3 Tagen, mit neuen Aufgabenvarianten.",
    "Es wird dokumentiert, welche Kompetenzen tatsächlich geprüft wurden.",
    "Ein internes Zertifikat ist keine staatlich anerkannte Qualifikation und garantiert keine Beschäftigung oder Einkünfte.",
  ],
} as const;
