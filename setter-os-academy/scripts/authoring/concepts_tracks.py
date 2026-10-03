# Authoring script for the concept graph, specializations and the day-91–180 architecture.
# JSON is the source of truth afterwards. Objective links for modules without content stay empty
# (shown as "Inhalt in Vorbereitung"); mastery is only ever derived from real answers.
import json
C=[]
def c(id,label,area,module,desc,pre=(),obj=()):
    C.append({"id":id,"label":label,"area":area,"moduleId":module,"description":desc,"prerequisites":list(pre),"objectiveIds":list(obj)})
# Grundlagen (M01)
c("C-ROLLE","Rolle des Setters","grundlagen","M01","Aufgaben, Abgrenzung zu Closer, SDR und BDR.",[],["LO-M01-01"])
c("C-JOURNEY","Customer Journey & Funnel","grundlagen","M01","Phasen der Kaufentscheidung und wo ein Lead steht.",["C-ROLLE"],["LO-M01-02"])
c("C-KONTEXT","Inbound/Outbound, B2B/B2C","grundlagen","M01","Folgen von Richtung und Markt für Gespräch und Recht.",["C-ROLLE"],["LO-M01-03"])
c("C-STRUKTUR","Gesprächsstruktur in vier Phasen","gespraech","M01","Eröffnung, Bedarf, Zusammenfassung, nächster Schritt.",["C-JOURNEY"],["LO-M01-04"])
c("C-STATUS","Lead-Status & Kaufbereitschaft","qualifizierung","M01","Status nach Kriterien bestimmen und dokumentieren.",["C-JOURNEY"],["LO-M01-05"])
c("C-GRENZEN","Ethische & rechtliche Grenzen","recht","M01","Kein Druck, Nein respektieren, keine Fachberatung.",["C-ROLLE"],["LO-M01-06"])
# Kommunikation (M02)
c("C-SCHREIBEN","Klar schreiben","gespraech","M02","Ein Gedanke pro Nachricht, mobil lesbar.",[],["LO-M02-01"])
c("C-ZUHOEREN","Aktives Zuhören","gespraech","M02","Paraphrase, Gefühle benennen, Folgefrage.",["C-SCHREIBEN"],["LO-M02-02"])
c("C-FRAGEN","Fragetechnik & Trichter","gespraech","M02","Offene, geschlossene, Folgefragen in sinnvoller Reihenfolge.",["C-ZUHOEREN"],["LO-M02-03"])
c("C-EROEFFNUNG","Eröffnung & Erlaubnis","gespraech","M02","Respektvoll beginnen, Erlaubnis einholen.",["C-SCHREIBEN","C-GRENZEN"],["LO-M02-04"])
c("C-TON","Ton & Stil","gespraech","M02","Anrede und Stil an Kanal und Person anpassen.",["C-SCHREIBEN"],["LO-M02-05"])
c("C-VERTRAUEN","Vertrauen aufbauen","psychologie","M02","Kompetenz, Wohlwollen, Verlässlichkeit.",["C-ZUHOEREN"],["LO-M02-06"])
c("C-TYPEN","Unterschiedliche Kundentypen","psychologie","M02","Heuristiken nutzen, ohne Schubladen.",["C-ZUHOEREN"],["LO-M02-07"])
# Psychologie (M03)
c("C-ENTSCHEIDUNG","Entscheidungsverhalten","psychologie","M03","Motivation, Unsicherheit und Risiko in Kaufentscheidungen.",["C-VERTRAUEN"])
c("C-EFFEKTE","Wirkmechanismen kritisch","psychologie","M03","Verlustaversion, Framing, Reziprozität, Social Proof – mit Evidenzlage.",["C-ENTSCHEIDUNG"])
c("C-MANIPULATION","Seriös vs. manipulativ","recht","M03","Grenze zu aggressiven und irreführenden Praktiken (UWG).",["C-EFFEKTE","C-GRENZEN"])
# Qualifizierung (M04)
c("C-ICP","ICP & Buyer Persona","qualifizierung","M04","Wer passt – und wer nicht.",["C-STATUS"])
c("C-FRAMEWORKS","BANT, SPIN, MEDDICC","qualifizierung","M04","Qualifizierungsraster zweckmäßig einsetzen.",["C-ICP","C-FRAGEN"])
c("C-SCORING","MQL/SQL & Lead Scoring","daten","M04","Bewertung von Leads nachvollziehbar machen.",["C-FRAMEWORKS"])
c("C-DISQUALI","Ehrlich disqualifizieren","qualifizierung","M04","Unpassende Leads respektvoll beenden.",["C-FRAMEWORKS","C-GRENZEN"])
# Chat (M05)
c("C-CHATFLOW","Chat-Struktur & Tempo","chat","M05","Gesprächsführung, Antwortzeit, Übergänge im Chat.",["C-STRUKTUR","C-SCHREIBEN"])
c("C-KANAELE","Zulässige Kanäle","recht","M05","Einwilligung, Plattformregeln für WhatsApp, Instagram & Co.",["C-KONTEXT","C-GRENZEN"])
c("C-UEBERGABE","Übergabe an Berater/Closer","termin","M05","Vollständige, wahre Übergabe.",["C-CHATFLOW","C-STATUS"])
# Einwände (M06)
c("C-EINWAND","Einwände verstehen","einwaende","M06","Preis, Zeit, Vertrauen, Partner – Hintergrund klären.",["C-ZUHOEREN","C-EFFEKTE"])
c("C-NEIN","Nein respektieren","einwaende","M06","Grenzen der Einwandbehandlung.",["C-EINWAND","C-GRENZEN"])
# Termine (M07)
c("C-TERMIN","Qualifizierte Termine","termin","M07","Vereinbarung, Bestätigung, Erinnerung.",["C-UEBERGABE","C-FRAMEWORKS"])
c("C-NOSHOW","No-Show-Recovery","termin","M07","Verschiebung und Wiederaufnahme ohne Druck.",["C-TERMIN","C-NEIN"])
# CRM (M08)
c("C-CRM","CRM & Pipeline","daten","M08","Datenpflege, Pipeline, Aufgaben.",["C-STATUS","C-UEBERGABE"])
c("C-DSGVO","Datenschutz im Vertrieb","recht","M08","Rechtsgrundlagen, Löschung, Auskunft.",["C-KANAELE","C-CRM"])
# Kennzahlen (M09)
c("C-KPI","Kennzahlen","daten","M09","Show Rate, Booking Rate, CAC, CLV, Pipeline Value.",["C-CRM","C-SCORING"])
# Branchen (M10)
c("C-BRANCHE","Branchenwissen & Fachgrenzen","business","M10","Wann zwingend an Fachberater übergeben wird.",["C-GRENZEN","C-TERMIN"])
# Selbstständigkeit (M11)
c("C-SELBST","Selbstständig als Setter","business","M11","Gewerbe, Steuern, Scheinselbstständigkeit (Grundlagen).",["C-KPI"])
c("C-AKQUISE","Zulässige Kundengewinnung","business","M11","Eigene Kunden rechtssicher gewinnen.",["C-SELBST","C-KANAELE"])
# Automatisierung (M12)
c("C-KI","KI mit menschlicher Kontrolle","business","M12","Recherche und Entwürfe, Verantwortung bleibt beim Menschen.",["C-SCHREIBEN","C-DSGVO"])
c("C-PROZESS","Prozesse & Skalierung","business","M12","Wiederholbare Abläufe, Qualitätssicherung.",["C-KPI","C-KI"])

T=[]
def t(id,title,area,summary,req,focus,legal=None):
    T.append({"id":id,"title":title,"area":area,"summary":summary,"requiredConcepts":req,"focus":focus,"legalNote":legal,"status":"geplant"})
t("T01","Solar & Photovoltaik","branche","Beratungsintensive Investition, Förderung und Technik bleiben beim Fachberater.",["C-BRANCHE","C-TERMIN"],["Eigenverbrauch und Speicher verständlich erfragen","Förderfragen sauber übergeben","Haushalts-Entscheidungsprozesse"],"Keine Förder- oder Ertragszusagen durch Setter.")
t("T02","Wärmepumpe & Heizung","branche","Lange Entscheidungswege, viele Fachfragen, GEG-Unsicherheit.",["C-BRANCHE","C-EINWAND"],["Gebäudedaten erfragen ohne Beratung","Unsicherheit ernst nehmen","Partner-Rücksprache einplanen"],"Keine Aussagen zu Pflichten aus dem GEG – an Fachberater.")
t("T03","Coaching & Online-Kurse","branche","Hohes Risiko unseriöser Versprechen; Einkommens- und Erfolgsversprechen sind tabu.",["C-MANIPULATION","C-DISQUALI"],["Erwartungen realistisch klären","Disqualifizieren bei Fehlpassung","Widerruf und FernUSG-Bezug kennen"],"FernUSG/ZFU-Relevanz bei Fernunterricht prüfen lassen; keine Einkommensversprechen.")
t("T04","Agenturen & Marketing-Dienstleister","branche","B2B, mehrere Entscheider, Ergebnisunsicherheit.",["C-FRAMEWORKS","C-KPI"],["Buying Center erfassen","Ziele messbar machen ohne Zusagen","Discovery-Call vorbereiten"])
t("T05","SaaS & Software B2B","branche","Demo-Termine, Testphasen, mehrere Stakeholder.",["C-FRAMEWORKS","C-SCORING"],["MEDDICC-Grundlagen anwenden","Demo vs. Discovery unterscheiden","Technische Fragen übergeben"])
t("T06","Recruiting & Personalberatung","branche","Zwei Zielgruppen: Unternehmen und Kandidaten.",["C-ICP","C-DSGVO"],["Vakanzen qualifizieren","Kandidatendaten datenschutzkonform behandeln","Diskriminierungsfreie Sprache (AGG)"],"AGG beachten; Bewerberdaten nur zweckgebunden.")
t("T07","Immobilien & Finanzierung","branche","Hohe Beträge, regulierte Beratung.",["C-BRANCHE","C-GRENZEN"],["Suchprofil erfassen","Finanzierungsfragen strikt übergeben","Vertrauen ohne Druck"],"Keine Finanzierungs- oder Anlageberatung (KWG/GewO § 34c/i).")
t("T08","Versicherungen & Finanzen","branche","Streng reguliert; Setter vermittelt nur Termine.",["C-GRENZEN","C-KANAELE"],["Abgrenzung Terminvermittlung vs. Vermittlung","Einwilligungen dokumentieren","Bedarf ohne Produktempfehlung"],"Versicherungsvermittlung erlaubnispflichtig (GewO § 34d) – nur Termin, keine Beratung.")
t("T09","Fitness & Gesundheit","branche","Sensible Daten und Heilversprechen-Verbot.",["C-MANIPULATION","C-DSGVO"],["Ziele erfragen ohne Gesundheitsdaten zu horten","Keine Heilversprechen","Probetraining sauber übergeben"],"HWG/UWG: keine Heil- oder Erfolgsversprechen; Gesundheitsdaten Art. 9 DSGVO.")
t("T10","IT-Dienstleistungen & Managed Services","branche","Technische Käufer, lange Zyklen.",["C-FRAMEWORKS","C-UEBERGABE"],["Ist-Situation strukturiert erfassen","Technische Übergabe vollständig","Dringlichkeit ohne Druck klären"])
t("T11","Telefon-Setting (Outbound B2B)","kanal","Kaltakquise nur im zulässigen Rahmen.",["C-KANAELE","C-EROEFFNUNG"],["Mutmaßliche Einwilligung B2B prüfen","Erste 20 Sekunden","Gatekeeper respektvoll"],"B2C-Kaltanrufe ohne Einwilligung verboten (UWG § 7 Abs. 2 Nr. 1).")
t("T12","Social-Media-DM-Setting","kanal","Instagram, Facebook, LinkedIn – nur nach Kontaktwunsch.",["C-CHATFLOW","C-KANAELE"],["Inbound-DMs strukturieren","Plattformregeln einhalten","Übergang in Termin"],"Keine unaufgeforderten Massen-DMs; Plattform-AGB.")
t("T13","E-Mail- & LinkedIn-Prospecting B2B","kanal","Recherche, Personalisierung, Einwilligung.",["C-ICP","C-KANAELE"],["Recherche statt Massenversand","Einwilligung und Opt-out","Follow-up-Rhythmus"],"Werbe-E-Mails brauchen Einwilligung (UWG § 7 Abs. 2 Nr. 2), Ausnahme § 7 Abs. 3 eng.")
t("T14","Team Lead Setting","fuehrung","Qualität im Team sichern, coachen statt drücken.",["C-KPI","C-PROZESS"],["Gesprächsanalysen im Team","Faire Kennzahlen","Onboarding neuer Setter"])
t("T15","Sales Operations & CRM-Administration","daten","Datenqualität, Automatisierung, Reporting.",["C-CRM","C-KPI"],["Pipeline-Hygiene","Dashboards aus echten Daten","Löschkonzepte"])
t("T16","KI-gestütztes Setting","technik","KI für Recherche und Entwürfe – Mensch entscheidet.",["C-KI","C-DSGVO"],["Prompting für Entwürfe","Prüfen statt blind übernehmen","Transparenz gegenüber Kunden"],"KI-VO-Transparenzpflichten und DSGVO beachten; keine Kundendaten in ungeprüfte Tools.")
t("T17","Selbstständiger Setter & Freelancing","business","Eigenes Business seriös aufbauen.",["C-SELBST","C-AKQUISE"],["Angebot und Preise","Verträge und Scheinselbstständigkeit","Zulässige Eigenakquise"],"Steuer- und Rechtsfragen mit Fachleuten klären.")
t("T18","Closing-Grundlagen für Setter","gespraech","Verstehen, was nach der Übergabe passiert – ohne die Rolle zu wechseln.",["C-UEBERGABE","C-EINWAND"],["Beratungsgespräch verstehen","Bessere Übergaben durch Closer-Sicht","Grenzen der Setter-Rolle"])

STAGES=[
 {"id":"ST8","number":8,"title":"Vertiefung & erste Spezialisierung","dayFrom":91,"dayTo":120,
  "goal":"Du wählst eine Spezialisierung, vertiefst schwache Konzepte adaptiv und übst branchenspezifische Simulationen.",
  "structure":["Woche 1: Diagnose – adaptive Wiederholung aller Konzepte unter „gefestigt“","Wochen 2–4: Spezialisierung 1 (Lektionen, 3 Simulationen, Fallstudie)","Täglich: 10–15 Min. gemischte Wiederholung","Stufen-Check 8: Spezialisierungsprüfung im Prüfungsmodus"],
  "unlock":"Stufen-Check 7 bestanden"},
 {"id":"ST9","number":9,"title":"Zweite Spezialisierung & Praxisprojekt","dayFrom":121,"dayTo":150,
  "goal":"Zweite Spezialisierung (Kanal oder Branche) und ein eigenes Praxisprojekt: Leitfaden, Übergabeprotokoll und Kennzahlen-Plan für ein fiktives Unternehmen.",
  "structure":["Spezialisierung 2 (Kanal empfohlen, wenn 1 eine Branche war)","Praxisprojekt in 4 Abgaben mit KI-Coach-Feedback","Boss-Simulationen mit wechselnden Personas","Stufen-Check 9"],
  "unlock":"Stufen-Check 8 bestanden"},
 {"id":"ST10","number":10,"title":"Meisterstufe II","dayFrom":151,"dayTo":180,
  "goal":"Du zeigst stabile Leistung über alle Bereiche: Prüfungssimulationen ohne Hilfen, Gesprächsanalysen fremder Transkripte und eine Abschlussreflexion.",
  "structure":["Gemischte Prüfungssimulationen (alle Bereiche)","Gesprächsanalysen: fremde Transkripte bewerten","Persönliches Kompetenzprofil mit Belegen","Abschluss: Meisterprüfung II"],
  "unlock":"Stufen-Check 9 bestanden"},
]
OPEN={"title":"Offene Fortbildung ab Tag 181","text":"Nach Tag 180 gibt es keinen festen Plan mehr. Die Akademie schlägt täglich Wiederholungen nach dem Abstandsprinzip vor, öffnet weitere Spezialisierungen und neue Simulationen. Fortschritt zeigt sich nur an geprüften Leistungen – nicht an Kalendertagen."}

ids={x["id"] for x in C}
for x in C:
    for p in x["prerequisites"]: assert p in ids,(x["id"],p)
for x in T:
    for p in x["requiredConcepts"]: assert p in ids,(x["id"],p)
assert len(T)==18
json.dump(C,open("content/concepts.json","w"),ensure_ascii=False,indent=2)
json.dump({"tracks":T,"stages":STAGES,"open":OPEN},open("content/longterm.json","w"),ensure_ascii=False,indent=2)
print(len(C),"concepts",len(T),"tracks")
