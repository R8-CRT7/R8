# LEGAL_REVIEW_CHECKLIST – Rechtliche Prüfung & Verkaufsfreigabe

Stand 03.10.2026 · **Kein Rechtsrat.** Diese Liste strukturiert die Prüfung durch eine Rechtsanwältin/einen Rechtsanwalt bzw. eine Steuerberatung.

## Legal-Review-Gate (verbindlich)

Solange **nicht alle** Punkte der Kategorie A mit „freigegeben“ und Datum/Name der prüfenden Fachperson markiert sind, gilt:

- [x] Die Anwendung ist ein **nichtkommerzieller, privat getesteter Prototyp** (Banner in jeder Ansicht).
- [x] **Keine Zahlungsfreischaltung** – es existiert kein Zahlungscode, keine Produkt-/Order-Tabelle (`db/schema.sql` endet bewusst vor „products/orders/payments“).
- [x] **Keine kommerziellen Verkaufsversprechen** (E2E-Test E01 prüft die Landing Page auf Einkommensversprechen).
- [x] **Keine Veröffentlichung personenbezogener Testdaten** – Daten bleiben im Browser; Seiten sind `noindex`.
- [x] Rechtliche Dokumente nur als **ENTWURF** (`docs/legal-drafts/`).

## A. Freigabe-relevant (Blocker vor Verkauf)

| # | Prüfpunkt | Recherche-Stand | Offene Frage an Fachperson | Status |
|---|---|---|---|---|
| A1 | **FernUSG / ZFU-Zulassungspflicht** | BGH III ZR 109/24, III ZR 73/25, III ZR 137/25 (weite Auslegung). Quiz/Simulation/Feedback/Prüfung = funktional Lernerfolgskontrolle. | Fällt das Produkt (asynchron, automatisierte Kontrolle, ggf. E-Mail-Support) unter § 1 FernUSG? Welche Gestaltung wäre zulassungsfrei? Lohnt Antrag (Gebühr ≥ 1.050 €, 150 % des Preises) vs. Abwarten der Reform? | offen |
| A2 | **FernUSG-Reform** | Referentenentwurf 17.08.2026: Aufhebung §§ 1–26 zum 01.07.2027 | Aktueller Verfahrensstand? Übergangsregeln für Altverträge? | offen, alle 14 Tage prüfen |
| A3 | **Gewerbeanmeldung** | – | Gewerbe oder freier Beruf (Bildung)? Zuständiges Amt. Nebentätigkeit neben Festanstellung (Arbeitsvertrag prüfen). | offen |
| A4 | **Steuern** | § 19 UStG: 25.000 €/100.000 € | Kleinunternehmer sinnvoll? USt-Befreiung für Bildungsleistungen (§ 4 Nr. 21 UStG) anwendbar? Einfluss des FernUSG-Urteils auf USt (FGS-Beitrag)? Steuerliche Erfassung beim Finanzamt. | offen |
| A5 | **Impressum** (§ 5 DDG) | Entwurf vorhanden | Ladungsfähige Anschrift (Privatadresse vermeiden? c/o-Lösungen zulässig?) | Entwurf |
| A6 | **Datenschutzerklärung** (Art. 13 DSGVO) | Entwurf; Prototyp ohne Server | Bei Cloud-Betrieb: Hosting, Auth, Logs, KI-Anbieter, Drittlandtransfer | Entwurf |
| A7 | **Verbraucherinformationen & Widerrufsrecht** digitale Inhalte (§§ 312 ff., 356 Abs. 5 BGB) | – | Widerrufsbelehrung, Muster-Widerrufsformular, Zustimmung + Bestätigung zum vorzeitigen Erlöschen | offen |
| A8 | **AGB/Nutzungsbedingungen** | Strukturentwurf | Leistungsbeschreibung ohne Erfolgsgarantie; Zertifikat ≠ staatliche Anerkennung; Haftung | Entwurf |
| A9 | **Zahlungsabwicklung** | – | Anbieterwahl (Merchant of Record vs. eigener Shop), Rechnungsstellung, Rückerstattung | gesperrt bis A1–A8 |
| A10 | **Werbeaussagen** (UWG §§ 5, 5a) | Keine Erfolgsquoten, keine Testimonials | Prüfung Landing Page & Marketing | offen |
| A11 | **Markenrecht** „SETTER OS ACADEMY“ | Ähnliche Marken „Setter AI“, „Setterflow“ gefunden; DPMA/EUIPO nicht geprüft | Kollisionsrecherche Kl. 9, 41, 42; ggf. Anmeldung | offen |

## B. Datenschutz & KI

| # | Prüfpunkt | Stand |
|---|---|---|
| B1 | Verarbeitungsverzeichnis (Art. 30 DSGVO) | Vorlage offen |
| B2 | Auftragsverarbeitung (Art. 28): Hosting, Supabase, E-Mail, KI-API | erst bei Cloud-Betrieb |
| B3 | Datenminimierung Simulation: nur Zug-IDs; KI-Modus: Texte ≤ 2.000 Zeichen, `retain_until` | umgesetzt (lokal) / Schema vorbereitet |
| B4 | **Löschkonzept**: Nutzer löschen → Kaskade auf alle Lerndaten (getestet, D07); Staff-Konten pseudonymisieren | Schema getestet |
| B5 | KI-Datenschutz: keine echten Kundendaten in Simulationen; Hinweis in jeder Übung | umgesetzt (UI-Hinweise) |
| B6 | Art. 50 KI-VO: Kennzeichnung KI-Gesprächspartner, sobald KI-Simulator aktiv | aktuell regelbasiert, Kennzeichnung „keine KI“ |
| B7 | DSFA notwendig? (Lernanalytik, Profilbildung) | offen |
| B8 | Minderjährige Nutzer? (Altersgrenze in AGB) | offen |

## C. Barrierefreiheit

| # | Prüfpunkt | Stand |
|---|---|---|
| C1 | BFSG-Pflicht (Kleinstunternehmen-Ausnahme bei Dienstleistungen) | Ausnahme wahrscheinlich, trotzdem Ziel WCAG 2.2 AA |
| C2 | Automatisierte axe-Prüfung (WCAG 2.2 AA, dunkel & hell) | bestanden ohne serious/critical (E11) |
| C3 | Manuelle Prüfung mit VoiceOver (iOS) und Tastatur | **ungeprüft** |

## D. Inhalte (Kurs lehrt Recht)

| # | Prüfpunkt | Stand |
|---|---|---|
| D1 | Rechtsaussagen in Lektion M01-L03/L06 und Fragen Q-M01-010/011/012/023 von Fachperson gegenlesen | offen |
| D2 | Hinweis „keine Rechtsberatung, Stand“ an allen Rechtsinhalten | umgesetzt |
| D3 | Prüfintervall Rechtsquellen 14–90 Tage (Admin-Warnung) | umgesetzt |

## E. Selbstständigkeit des Gründers (Setting-Service)

| # | Prüfpunkt | Stand |
|---|---|---|
| E1 | Scheinselbstständigkeit bei Setting-Aufträgen (Weisung, Eingliederung, mehrere Auftraggeber) | recherchiert (Grundsätze), Einzelfall offen |
| E2 | Akquise des Service nur über zulässige Kanäle (UWG §§ 7, 7a) | Kursinhalt geplant (M11) |
| E3 | AV-Vertrag mit Auftraggebern, wenn Setter Kundendaten verarbeitet | offen |
| E4 | Volljährigkeit (18) – keine Einschränkung der Geschäftsfähigkeit | erfüllt |

## Ablauf bis zur Freigabe

1. Interne Beta abschließen (TEST_PLAN.md).
2. Paket für Anwalt/Steuerberatung: dieses Dokument, RESEARCH_REPORT §5, Produktbeschreibung, Entwürfe.
3. Entscheidung A1 (ZFU ja/nein/Abwarten) dokumentieren in `CHANGELOG.md` und `OPEN_QUESTIONS.md`.
4. Erst danach: Zahlungsanbieter auswählen (**ausdrückliche Zustimmung des Gründers erforderlich**).
