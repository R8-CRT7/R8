# RESEARCH_REPORT – Fach-, Lern- und Rechtsrecherche

Stand: 03.10.2026 · Version 0.1 · Verantwortlich: Projektteam (KI-gestützt erstellt, **fachlich und rechtlich noch nicht extern geprüft**)

## 0. Methode und Grenzen dieser Recherche (bitte zuerst lesen)

| Punkt | Tatsächlicher Stand |
|---|---|
| Werkzeuge | Websuche (US-Suchindex) war verfügbar. Direkter Seitenabruf (`WebFetch`, `curl`) war durch die Netzwerkrichtlinie der Arbeitsumgebung für fast alle Domains **gesperrt** – u. a. gesetze-im-internet.de, zfu.de, bundesgerichtshof.de, beck-aktuell.de, noerr.com, heise.de. |
| Folge | Primärtexte (Gesetze, Urteile, Studien) wurden **nicht im Volltext gelesen**. Kernaussagen wurden über Such-Snippets und mehrere Sekundärquellen (Kanzleien, IHK, Fachpresse) abgeglichen. Solche Quellen tragen den Status `teilweise_verifiziert`. |
| Aus Fachwissen | Einige Standardwerke (z. B. Kahneman & Tversky 1979, Sweller 2011, Cialdini 2021) sind aus Fachwissen eingetragen und als `unverifiziert` markiert. Sie dürfen erst nach Prüfung als gesicherte Aussage in Lehrtexte. |
| HubSpot/Salesforce | Kursinhalte (HubSpot Academy, Trailhead) waren nicht abrufbar; nur die Inbound-Methodik (Identify, Connect, Explore, Advise) ist über Sekundärquellen bestätigt. |
| Aussagenarten | Dieser Bericht trennt **[Fakt]** (belegbar), **[Expertenmeinung]** (Praxis-Konvention, Herstellerposition), **[Annahme]** (unsere Festlegung) und **[Modellrechnung]**. |

Das vollständige Quellenregister mit Prüfstatus steht in [`SOURCE_REGISTER.md`](SOURCE_REGISTER.md) (aus `content/sources.json` erzeugt).

---

## 1. Berufsbild: Setter, Closer, SDR, BDR

- **[Expertenmeinung]** „Setter“ ist im deutschsprachigen Online-, Coaching- und Agenturmarkt die übliche Bezeichnung für Personen, die eingehende oder angesprochene Leads qualifizieren und Termine für Closer/Berater vereinbaren. Der Begriff ist **nicht genormt**.
- **[Expertenmeinung]** Im B2B-Umfeld heißen vergleichbare Rollen SDR (häufig Inbound-Qualifizierung) und BDR (häufig Outbound-Akquise). Die Verwendung ist widersprüchlich – manche Unternehmen tauschen die Begriffe (dokumentiert in KB-002).
- **[Annahme, Kursdefinition]** Abgrenzung im Kurs:
  - Setter: Erstkontakt, Bedarfsermittlung, Qualifizierung, Terminvereinbarung, Bestätigung, Dokumentation, Übergabe.
  - Closer/Berater: Beratung, Preis, Technik, Förderung, Angebot, Abschluss.
  - Ein Setter beantwortet keine Fachfragen, deren falsche Beantwortung dem Kunden schaden kann (Preis, Förderung, Steuer, Vertrag, Technik).

### Kompetenzstufen (Annahme, aus Rollenanalyse abgeleitet, durch Pilot zu validieren)

| Stufe | Kompetenzen | Module |
|---|---|---|
| Einsteiger | Rollenverständnis, Gesprächsstruktur, offene Fragen, Pflichtkriterien der Qualifizierung, ehrliche Dokumentation, rechtliche Grundregeln (Einwilligung, Nein respektieren) | 1, 2, 4 (Basis), 5, 7 |
| Fortgeschritten | Einwandbehandlung mit Grenzen, Branchenwissen, CRM-Prozesse, Kennzahlen, Psychologie kritisch einordnen, B2B-Mehrpersonenentscheidungen (MEDDICC) | 3, 4 (MEDDICC), 6, 8, 9, 10 |
| Experte/Unternehmer | Prozessdesign, Automatisierung mit menschlicher Kontrolle, Qualitätssicherung, Multi-Client-Management, Selbstständigkeit, Rechtssicherheit | 11, 12 |

## 2. Inbound vs. Outbound, B2B vs. B2C

- **[Fakt, teilweise verifiziert]** HBR 2011 (Oldroyd, McElheran, Elkington): Analyse von 1,25 Mio. Online-Leads bei 42 US-Unternehmen. Kontakt innerhalb einer Stunde ging mit etwa 7× höherer Qualifizierungswahrscheinlichkeit einher als Kontakt eine Stunde später; Durchschnittsreaktionszeit 42 h. **Grenzen:** korrelativ, US-Daten, 15 Jahre alt. Die oft zitierte „5-Minuten / 21×“-Zahl stammt aus einer anderen (Hersteller-)Studie und wird im Kurs **nicht** verwendet.
- **[Expertenmeinung]** Inbound ist für Einsteiger der geeignetere Startpunkt: Der Kontakt ist erwünscht, die Einwilligungsfrage ist meist geklärt, der Fokus liegt auf Gesprächsqualität.
- **[Fakt]** B2B vs. B2C unterscheidet sich in Deutschland vor allem rechtlich (siehe §5) und im Entscheidungsprozess (mehrere Beteiligte, Freigaben im B2B).

## 3. Methoden der Qualifizierung

| Methode | Status | Einordnung im Kurs |
|---|---|---|
| Inbound-Methodik HubSpot (Identify, Connect, Explore, Advise) | Herstellermethodik, teilweise verifiziert | Modul 1/2 als Orientierungsmodell |
| BANT (Budget, Authority, Need, Timing) | Praxisheuristik, Herkunft IBM zugeschrieben, keine empirische Überlegenheit belegt | Modul 1 (Basis), Modul 4 kritisch |
| SPIN (Rackham 1988) | Fachliteratur; zugrunde liegende Huthwaite-Beobachtungen nicht unabhängig repliziert | Modul 4 |
| MEDDIC(C) | Praxisframework für komplexes B2B; Herkunft nur zugeschrieben | Modul 4, fortgeschritten |
| MQL/SQL, Lead Scoring | Branchenpraxis | Modul 4/8 |

**Kursentscheidung [Annahme]:** Pflichtkriterien vor einem Termin sind Bedarf, Passung, Zeitrahmen und Entscheider. Budget je nach Auftraggeber. Diese Festlegung ist pädagogisch, nicht empirisch begründet.

## 4. Verkaufspsychologie – kritisch

| Konzept | Evidenzlage | Kurskonsequenz |
|---|---|---|
| Verlustaversion | Meta-Analyse Brown et al. 2024: λ ≈ 1,96 (95 %-Intervall 1,82–2,10) über 607 Schätzungen. Gegenposition Gal & Rucker 2018 (Generalität bezweifelt). | Als kontextabhängige Tendenz lehren, **nie** als Rechtfertigung für Angstappelle. |
| Choice Overload | Meta-Analyse Scheibehenne et al. 2010: mittlerer Effekt ≈ 0, große Varianz; Chernev et al. 2015: Moderatoren. | „Zwei Terminvorschläge statt zehn“ als Klarheitsregel, nicht als psychologisches „Gesetz“. |
| Reziprozität, Social Proof, Commitment, Knappheit | Fachliteratur (Cialdini); Teile der Originalstudien in der Replikationsdebatte (unverifiziert) | Nur wahrheitsgemäß: echte Referenzen mit Einwilligung, keine künstliche Verknappung. |

**Ethik-Regel [Annahme, Produktgrundsatz]:** Manipulation = Herbeiführen einer Entscheidung, die die Person bei voller Information nicht treffen würde. Verboten im Kurs: künstliche Verknappung, erfundene Referenzen/Zahlen, Ignorieren eines Neins, Druck auf erkennbar verletzliche Personen.

## 5. Recht (Deutschland, Stand 10/2026 – keine Rechtsberatung)

### 5.1 Werbliche Kommunikation (für Kursinhalte)

| Kanal | Rechtslage nach Recherche | Status |
|---|---|---|
| Telefon B2C | Vorherige **ausdrückliche** Einwilligung (§ 7 Abs. 2 UWG); Dokumentation und 5 Jahre Aufbewahrung (§ 7a UWG, seit 01.10.2021) | teilweise verifiziert |
| Telefon B2B | Mindestens **mutmaßliche** Einwilligung; bloßer Branchenbezug genügt nach Sekundärquellen nicht | teilweise verifiziert |
| E-Mail / elektronische Post | Vorherige ausdrückliche Einwilligung, auch B2B; Ausnahme Bestandskunden § 7 Abs. 3 UWG (4 kumulative Voraussetzungen) | teilweise verifiziert |
| LinkedIn-/Instagram-Direktnachrichten | Gelten als elektronische Post; Vernetzung ≠ Einwilligung (AG Düsseldorf 20.11.2025, 23 C 120/25 – Amtsgericht, begrenzte Bindungswirkung) | teilweise verifiziert |
| WhatsApp | Zusätzlich Meta-Plattformregeln: Opt-in mit Unternehmensnamen vor Nachrichten | teilweise verifiziert |
| Lead-Reaktivierung | Abhängig von ursprünglicher Einwilligung/Bestandskundenausnahme und Widerspruch – Einzelfallprüfung | **offen** (OPEN_QUESTIONS) |
| Durchsetzung | BNetzA 2025: 39.842 Beschwerden (+6 %), 13 große Bußgeldverfahren, > 1,099 Mio. € Bußgelder; erstmals Verstöße gegen Dokumentationspflicht geahndet | teilweise verifiziert |

### 5.2 Das Produkt selbst: Fernunterrichtsschutzgesetz (FernUSG)

**Fakten (teilweise verifiziert, Sekundärquellen):**
1. § 1 FernUSG: entgeltliche Vermittlung von Kenntnissen und Fähigkeiten, Lehrende und Lernende überwiegend räumlich getrennt, Überwachung des Lernerfolgs durch Lehrende oder Beauftragte. § 7: ohne erforderliche Zulassung **nichtig**.
2. **BGH 12.06.2025, III ZR 109/24:** FernUSG gilt auch für Verträge mit **Unternehmern**; Bezeichnung als „Coaching/Mentoring“ ist unerheblich; Lernerfolgskontrolle wird **weit** ausgelegt.
3. **BGH 12.02.2026, III ZR 73/25:** Schon das vertragliche Recht, Verständnisfragen zu stellen, genügt; keine weitergehende Kontrolle nötig.
4. **BGH 05.02.2026, III ZR 137/25:** Synchrone, bidirektionale Live-Formate können Präsenzunterricht entsprechen; maßgeblich ist der **Vertragsinhalt**; aufgezeichnete Live-Calls zählen zum asynchronen Anteil.
5. **Referentenentwurf BMBFSFJ, 17.08.2026:** Aufhebung §§ 1–26 FernUSG zum 01.07.2027, vollständig bis 30.06.2028. **Nur Entwurf** – kein Kabinettsbeschluss, keine Lesung (Stand Sekundärquellen September 2026). Bis zum Inkrafttreten gilt das FernUSG.
6. ZFU-Zulassung (FIM-Leistungsbeschreibung, Snippet): Gebühr i. d. R. 150 % des Lehrgangspreises, mind. 1.050 €; ca. 3 Monate Bearbeitung.

**Analyse für SETTER OS ACADEMY [Expertenmeinung/Risikoeinschätzung – rechtlich zu prüfen]:**
- Das Produkt ist **überwiegend asynchron** (räumliche Trennung: erfüllt).
- Quiz mit Auswertung, Simulationen mit Coach-Feedback, Wiederholungsplanung und Abschlussprüfungen sind **funktional eine Lernerfolgskontrolle**. Ob eine rein automatisierte Kontrolle „durch den Lehrenden oder seinen Beauftragten“ erfolgt, ist nach den gesichteten Quellen **nicht ausdrücklich entschieden**. Wegen der weiten Auslegung durch den BGH (schon ein Fragerecht genügt) ist **davon auszugehen, dass ein Gericht das Merkmal bejahen könnte** – erst recht, wenn Support/Fragen per E-Mail angeboten werden.
- **Wir behaupten ausdrücklich nicht**, dass ein automatisiertes System von der Zulassungspflicht befreit ist.
- Bei Entgeltlichkeit würde das Produkt daher **voraussichtlich** in den Anwendungsbereich fallen → ZFU-Zulassung oder rechtssichere Alternativgestaltung erforderlich; oder Abwarten der Reform (mit Unsicherheit).
- Konsequenz: **Legal-Review-Gate** (siehe [LEGAL_REVIEW_CHECKLIST.md](LEGAL_REVIEW_CHECKLIST.md)). Bis dahin: privater, unentgeltlicher Prototyp.

### 5.3 Weitere Rechtsfelder (Kurzüberblick, Details in LEGAL_REVIEW_CHECKLIST)

- **Kleinunternehmerregelung** (§ 19 UStG ab 2025): Vorjahr ≤ 25.000 €, laufendes Jahr ≤ 100.000 € netto. [teilweise verifiziert]
- **BFSG** seit 28.06.2025; Kleinstunternehmen bei Dienstleistungen ausgenommen – wir zielen trotzdem auf WCAG 2.2 AA. [teilweise verifiziert]
- **KI-Verordnung Art. 50** (Transparenz, z. B. Chatbots) gilt laut Sekundärquellen ab 02.08.2026; Hochrisiko-Pflichten durch Digital Omnibus verschoben. Relevant, sobald ein KI-Kundensimulator aktiviert wird. Der aktuelle Simulator ist regelbasiert und ist als „keine KI, keine echte Person“ gekennzeichnet. [teilweise verifiziert]
- **Scheinselbstständigkeit** (§ 7a SGB IV): Weisungsgebundenheit und Eingliederung als Hauptkriterien; Statusfeststellung bei der DRV möglich – relevant für den späteren Setting-Service des Gründers. [teilweise verifiziert]
- **Nebentätigkeit** neben Festanstellung: Arbeitsvertrag auf Anzeige-/Genehmigungspflicht und Wettbewerbsverbot prüfen. [Annahme – nicht recherchiert, OPEN_QUESTIONS]

## 6. Lernwissenschaft (Kurzfassung, Details in LEARNING_SCIENCE.md)

- Dunlosky et al. 2013: Practice Testing und Distributed Practice mit höchster Nützlichkeit; Zusammenfassen, Markieren, Wiederlesen gering. [teilweise verifiziert]
- Sana & Yan 2022: Interleaved Quizze 63 % vs. blockiert 54 % vs. nicht abgefragt 47 % nach einem Monat (155 Schüler:innen, Naturwissenschaften). [teilweise verifiziert]
- Wisniewski, Zierer & Hattie 2020: Feedback d = 0,48, hohe Heterogenität; informationsreiches Feedback wirkt stärker. [teilweise verifiziert]
- **Transfergrenze:** Keine der Studien untersucht Vertriebs- oder Gesprächskompetenz. Die Übertragung auf Appointment Setting ist eine **begründete Annahme** und wird im Pilot gemessen (verzögerter Abruf, Simulationsleistung vor/nach).

## 7. Branchen (Vorrecherche für Modul 10 – Inhalte noch nicht erstellt)

| Branche | Setter-Rolle | Übergabe an Fachperson zwingend bei | Status |
|---|---|---|---|
| Energetische Modernisierung (PV, Wärmepumpe, Speicher) | Eigentum, Objektart, Heizung/Verbrauch, Zeitrahmen, Mitentscheider | Preis, Förderung, Technik, Wirtschaftlichkeit, Steuer | Grundsätze in SIM-001/SIM-003 umgesetzt; Förder-/Technikdetails **nicht** recherchiert (bewusst: Setter beantworten sie nicht) |
| Marketingagenturen | Ziel, Kanal, Budgetrahmen, Entscheider | Strategie, Erfolgsprognosen | SIM-002 |
| Recruiting | Vakanz, Zeitdruck, Entscheider, Modell (Retainer/Erfolg) | Vertragsmodell, Arbeitsrecht | offen |
| B2B SaaS / IT | Use Case, Stack, Buying Center, Zeitplan | Technik, Sicherheit, Preise | offen |
| Unternehmensberatung | Problem, Mandatsumfang, Sponsor | Methodik, Honorar | offen |

## 8. Name „SETTER OS ACADEMY“

- Websuche (03.10.2026) ergab **keinen identischen Produktnamen**, aber ähnliche Marken im Markt: „Setter AI“ (KI-Terminbuchung), „Setterflow“ (KI-Setting-Software). [Snippet]
- **Nicht geprüft:** DPMA-Register, EUIPO (EUTM), WIPO, Domains, Social Handles – waren in der Umgebung nicht abrufbar.
- Risiko: „Setter“ ist beschreibend (schwache Unterscheidungskraft), „OS“ wird häufig genutzt. Verwechslungsgefahr mit „Setter AI“ in Klasse 9/35/41/42 möglich. → Vor kommerzieller Nutzung Markenrecherche (DPMA/EUIPO, Klassen 9, 41, 42) und ggf. anwaltliche Prüfung. Bis dahin **Arbeitstitel**.

## 9. Wettbewerb und Preise

- Es existieren deutschsprachige Chat-Setting-Kurse (z. B. eine „Chat-Setting Masterclass“ mit acht Modulen und Teilnahmebestätigung, ZFU-Lehrgangsverzeichnis enthält Setting-Einträge) sowie englischsprachige Kurse auf Gumroad. **Belastbare Preise wurden nicht erhoben.** Es werden im Projekt daher **keine Marktpreise behauptet** (siehe MONETIZATION.md).

## 10. Widersprüche und offene Punkte

Dokumentiert in KB-Einträgen (`contradictions`) und [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md): SDR/BDR-Begriffe, Verlustaversion, Choice Overload, automatisierte Lernerfolgskontrolle (FernUSG), Status der FernUSG-Reform.
