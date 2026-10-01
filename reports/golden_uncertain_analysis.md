# Golden v1/v2 – Analyse der UNCERTAIN-Fälle

Analyse-Zeitpunkt (vor dem Meilenstein): 117 UNCERTAIN von 160. Jeder Fall wurde **einzeln von Hand** einer Hauptursache zugeordnet (`windows/tools/analysis/golden_uncertain_labels.py`); die Engine nutzt diese Labels nicht. Behoben wurden nur Ursachen-Klassen (allgemeine Sprach-/Logikregeln), keine einzelnen Fragen.

Jetzt (frischer Lauf): **89 UNCERTAIN (56%)**.

| Kategorie | vorher | vorher % | jetzt | Nebenursache in (jetzt) | Beschreibung | Empfohlene Verbesserung |
|---|---|---|---|---|---|---|
| CONTRARY_NOT_DERIVABLE | 28 | 24% | 16 | 6 | Die richtige Option wird gefunden, die falschen Optionen lassen sich aber nicht widerlegen, weil keine Regel die abweichende Handlung ausdrücklich verbietet | Handlungs-Konzepte mit Unverträglichkeiten (WARTEN vs. WEITERFAHREN, ANHALTEN vs. DURCHROLLEN …): eine Option, die der von der Regel verlangten Handlung in derselben Situation widerspricht, ist FALSCH |
| PARAPHRASE_MISMATCH | 26 | 22% | 21 | 8 | Regel vorhanden, die Antwort sagt dasselbe mit anderen Worten/Satzbau | semantische Normalisierung (Konzepte statt Wörter), Handlungs-/Objekt-Konzepte |
| YES_NO_PROPOSITION | 16 | 14% | 11 | 0 | Ja/Nein-Frage; die Aussage steckt in der Frage, die Antwort ist nur 'Ja'/'Nein' | Frage in eine Proposition umbauen (Modalverb + Prädikat) und strukturell prüfen |
| NUMERIC_CONTEXT | 14 | 12% | 11 | 3 | Zahl hängt an einer Bedingung der Frage (Fahrzeug, Sicht, Ort) oder an einer anderen Größe/Einheit; die Zahlenregel wird nicht der Frage zugeordnet | Bedingungs-Extraktion (Fahrzeug, Sicht, Ort, Größe) + Zahlenregeln strukturell abrufen (quantity, applies_to) |
| ANSWER_REFERENCE_UNKNOWN | 8 | 7% | 6 | 1 | Kurzantwort verweist auf eine Rolle der Frage ('Ich', 'Der Gegenverkehr', 'Rechts', 'Die gelben') | Antwort-Rollen auflösen: Sprecher/Akteur/Gegenüber aus der Frage übernehmen |
| SIGN_NAME_MATCH | 8 | 7% | 5 | 0 | 'Was bedeutet Zeichen X?' mit dem amtlichen Namen als Antwort wird nicht sicher zugeordnet | Zeichen-Antworten zuerst gegen die amtlichen Namen aller Zeichen prüfen |
| QUESTION_TYPE_UNKNOWN | 7 | 6% | 5 | 1 | Fragetyp nicht erkannt ('Was ist untersagt?', 'Ab wann …?', 'Welche Aussage ist falsch?' ohne Kontext) | Intent-Erkennung (PROHIBITION, PERMISSION, REQUIRED_ACTION …) und Antwort im Licht des Intents lesen |
| CONDITION_EXTRACTION | 5 | 4% | 5 | 5 | Bedingungen der Frage (Alter, Größe, 'ohne', 'ausgefallen') werden nicht strukturiert und nicht mit den Regelbedingungen verglichen | Bedingungs-Rahmen (Akteur, Fahrzeug, Ort, Wetter, Zustand, Ausnahme) aus der Frage |
| SOURCE_UNVERIFIED | 4 | 3% | 4 | 0 | Regel nur aus nicht verifizierbarer Quelle (FeV/StVG) | amtliche Quelle beschaffen |
| COMPOSITE_RULE | 1 | 1% | 1 | 3 | Antwort braucht mehrere Regeln oder eine Folgerung aus einer Regel (z. B. 'rechten Blinker setzen' widerspricht 'nicht blinken') | Regel-Komposition + Ableitungen über Konzepte |

## Beispiele je Kategorie (eigene Kurzbeschreibung)

**CONTRARY_NOT_DERIVABLE**
- G014: Polizei Arme quer - 'ich darf fahren' widerspricht 'Halt'
- G016: Einsatzfahrzeug - 'normal weiterfahren', 'auf Vorfahrt bestehen' widersprechen 'freie Bahn schaffen'
- G021: Bahnübergang Stau - 'auf den Übergang fahren' widerspricht 'vor dem Andreaskreuz warten'
- G022: Bus mit Warnblinklicht, Gegenverkehr - 'unvermindert' widerspricht 'Schrittgeschwindigkeit'
- G024: Stau hinter Kreuzung - 'einfahren, weil Grün' widerspricht der Regel

**PARAPHRASE_MISMATCH**
- G008: spielende Kinder: 'langsamer und bremsbereit' anders formuliert als die Regel
- G011: aus Waldweg einbiegen - 'durchfahren lassen' statt 'Vorfahrt gewähren'
- G015: Polizei vor Ampel - 'anhalten' statt 'Haltezeichen befolgen'
- G017: Grünpfeil - 'zuerst anhalten', Fußgänger nicht behindern
- G023: Grundstücksausfahrt - 'Gefährdung ausschließen' wörtlich anders

**YES_NO_PROPOSITION**
- G046: Hupen innerorts zum Überholen - 'Nein, nur außerorts'
- G061: Handy bei Start-Stopp - 'Nein'
- G068: Radwegbenutzung ohne Schild - 'Ja, jeder Radweg' nicht widerlegt
- G069: Mofa 25 km/h auf Autobahn - 'Nein'
- H021: Stau am Zebrastreifen - 'Nein'

**NUMERIC_CONTEXT**
- G002: Pkw mit Wohnanhänger außerorts - Anhänger-Tempo wird nicht eindeutig der Frage zugeordnet
- G009: Faustregel-Abstand bei 100 km/h - die Rechenregel wird nicht erkannt, Seitenabstand-Zahlen gewinnen
- G031: eingeschränktes Haltverbot - Aussteigen erlaubt, '10 Minuten parken' nicht
- G036: einstreifige Bake - Zahl hängt am Bakentyp
- G048: Parkverbot vor Kreuzung (ohne Radweg) - 5 m vs. 8 m

**ANSWER_REFERENCE_UNKNOWN**
- G010: rechts vor links - Antwort nennt nur 'den Pkw von rechts'
- G034: gelbe vs. weiße Markierung - Antworten 'Die gelben'/'Die weißen'
- G079: Hindernis auf meiner Seite - Antworten 'Ich'/'Der Gegenverkehr'
- H011: Linksabbieger vs. entgegenkommender Rechtsabbieger - 'Ich'
- H013: Ampel vs. Vorfahrtsschild - Antworten 'Die Ampel'/'Das Schild'

**SIGN_NAME_MATCH**
- G026: Zeichen 306 - amtlicher Name als Antwort
- G027: Zeichen 206 - amtlicher Name als Antwort
- G029: Tempo-30-Zone - Bedeutung umschrieben
- G080: Zeichen 301 - Bedeutung als Antwort
- H026: Zeichen 205

**QUESTION_TYPE_UNKNOWN**
- G039: 'Was ist untersagt?' - Antwort ist eine Handlung ohne Modalverb
- G047: 'Ab wann parken Sie?' - Antwort als Bedingung
- G075: 'Was ist NICHT erlaubt?' beim Linksabbiegen
- G076: 'Welche Aussage ist falsch?' ohne Situationskontext
- H018: 'Was ist verboten?' + Infinitiv-Antwort 'Ihn zu überholen'

**CONDITION_EXTRACTION**
- G064: Kind 7 Jahre - Alter < 8 muss mit der Regel verglichen werden
- G067: Kind 10 Jahre, 140 cm - Bedingungen der Kindersitzpflicht
- H012: Blaulicht ohne Martinshorn - 'Es warnt'
- H014: Ampel ausgefallen - Verkehrszeichen gelten
- H065: Gehweg-Alter 10 vs. 8 (müssen vs. dürfen)

**SOURCE_UNVERIFIED**
- G071: Klasse B mit 750-kg-Anhänger (FeV)
- G072: Probezeit (StVG)
- G073: Alkoholabbau
- H075: Punkte (StVG)

**COMPOSITE_RULE**
- G012: Kreisverkehr: 'rechten Blinker beim Einfahren' widerspricht 'nicht blinken'

## Versteckte Fehlurteile

In UNCERTAIN-Fragen gab es **1 Einzelurteile**, die dem erwarteten Ergebnis widersprechen, aber durch die Gesamt-Unsicherheit verdeckt waren. Wer UNCERTAIN einfach senkt, macht daraus falsch-sichere Antworten – deshalb werden sie hier mitgezählt und jede Verbesserung muss sie beseitigen statt aufdecken.

G080#1

## Neu UNCERTAIN (vorher beantwortet, z. B. durch strengere Sicherheitsregeln)

G003, G063, H038, H061
