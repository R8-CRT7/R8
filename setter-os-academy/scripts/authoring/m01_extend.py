# One-off authoring script: extends Module 1 to ~2 hours with Kursbuch chapters, skill cards, myth checks,
# two new lessons and 12 new questions. JSON remains the source of truth afterwards.
import json
P='content/modules/M01.json'; Q='content/questions/M01.json'
m=json.load(open(P)); qs=json.load(open(Q))
L={l['id']:l for l in m['lessons']}

def book(ch,title,paras,src=None):
    b={"kind":"book","chapter":ch,"title":title,"paragraphs":paras}
    if src: b["sourceIds"]=src
    return b
def skill(name,cat,what,how,why,evidence,example,boundary,src):
    return {"kind":"skill","name":name,"category":cat,"what":what,"how":how,"why":why,"evidence":evidence,"example":example,"boundary":boundary,"sourceIds":src}
def myth(claim,reality,src): return {"kind":"myth","claim":claim,"reality":reality,"sourceIds":src}
def check(q): return {"kind":"check","questionId":q}
def insert_after_first(lesson, blocks):
    lesson['blocks']=lesson['blocks'][:1]+blocks+lesson['blocks'][1:]

# ---------------- L01 ----------------
insert_after_first(L['M01-L01'],[
 book("Kapitel 1.1","Der Beruf hinter dem Begriff",[
  "Stell dir vor, ein Unternehmen gibt jeden Monat Geld für Werbung aus. Menschen klicken, füllen Formulare aus, schreiben Nachrichten. Ab diesem Moment entscheidet sich, ob das Geld etwas gebracht hat – und zwar nicht in der Werbung, sondern im ersten Gespräch. Genau dort arbeitest du. Ein Setter ist die erste Person, die einem Interessenten wirklich antwortet. Du bist damit gleichzeitig Gastgeber, Detektiv und Filter.",
  "Gastgeber heißt: Der Mensch soll sich willkommen und ernst genommen fühlen. Er hat eine Frage oder ein Problem, und du bist die erste Person, die zuhört. Detektiv heißt: Du findest heraus, was wirklich hinter der Anfrage steckt. „Interesse an Wärmepumpe“ kann bedeuten, dass jemand nächste Woche bestellen will – oder dass jemand für ein Schulreferat recherchiert. Filter heißt: Du entscheidest, ob der Kalender des Beraters für diese Person die richtige Investition ist.",
  "Viele Einsteiger verwechseln den Job mit „Termine machen um jeden Preis“. Das ist der häufigste und teuerste Fehler. Ein Berater, der fünf Termine mit unpassenden Interessenten führt, verliert einen ganzen Arbeitstag. Der Interessent verliert Zeit und Vertrauen. Und du verlierst Glaubwürdigkeit, weil deine Termine als „Zeitverschwendung“ gelten. Gute Setter werden deshalb nicht an der Anzahl gebuchter Termine gemessen, sondern daran, wie viele ihrer Termine tatsächlich stattfinden und zu einem sinnvollen Ergebnis führen.",
  "Was macht den Beruf anspruchsvoll? Du musst in wenigen Nachrichten Vertrauen aufbauen, ohne zu übertreiben. Du musst Fragen stellen, ohne wie ein Formular zu wirken. Du musst Fachfragen ernst nehmen, ohne sie selbst zu beantworten. Und du musst ein Nein akzeptieren, ohne frustriert zu wirken. Das sind Kommunikationsfähigkeiten, die man trainieren kann – genau darum geht es in dieser Akademie.",
  "Ein Wort zu den Begriffen: „Setter“ und „Closer“ stammen aus dem Online-Coaching- und Agenturmarkt. In klassischen B2B-Unternehmen heißen ähnliche Rollen SDR oder BDR, im Handwerk oft „Terminierung“ oder „Innendienst“. Die Bezeichnung ist egal. Wichtig ist, dass in jedem Projekt klar ist, wo deine Verantwortung beginnt und wo sie endet. Schreib dir diese Grenze für jeden Auftraggeber auf, bevor du das erste Gespräch führst."
 ],["SRC-050","SRC-043"]),
 skill("Die Rollen-Brücke","gespraech",
  "Eine Fachfrage freundlich würdigen, an die zuständige Person übergeben und den Moment für eine eigene Frage nutzen.",
  ["Würdigen: „Gute Frage …“ oder „Das ist wichtig für Ihre Entscheidung …“","Begründen, warum du sie nicht beantwortest: „… ich möchte Ihnen nichts Ungenaues sagen.“","Übergeben: „Genau das rechnet unser Berater im Termin für Sie durch.“","Brücke: eine Bedarfsfrage, die dem Berater hilft."],
  "Menschen akzeptieren ein „Das beantworte ich nicht“ deutlich besser, wenn sie den Grund kennen und merken, dass ihre Frage ernst genommen wird. Die anschließende Frage hält das Gespräch in Bewegung.",
  "Kombiniert zwei gut belegte Prinzipien: Begründungen erhöhen Akzeptanz (Langer et al. 1978, Replikationslage gemischt) und Folgefragen erhöhen wahrgenommene Zugewandtheit (Huang et al. 2017).",
  "„Was kostet das?“ → „Gute Frage – der Preis hängt stark von Ihrem Dach ab, und ich möchte Ihnen keine falsche Zahl nennen. Das rechnet unser Berater im Termin konkret durch. Damit er vorbereitet ist: In welche Himmelsrichtung zeigt Ihr Dach ungefähr?“",
  "Die Brücke darf nie dazu dienen, eine einfache, erlaubte Frage auszuweichen. Wenn dein Auftraggeber einen Preisrahmen freigegeben hat, nennst du ihn.",
  ["SRC-058","SRC-054","SRC-050"]),
 myth("„Ein Setter ist nur ein Terminbucher – das kann jeder.“",
  "Terminbuchen ist der kleinste Teil der Arbeit. Die eigentliche Leistung ist die Qualifizierung: herausfinden, ob ein Termin für beide Seiten sinnvoll ist. Genau das unterscheidet Setter, deren Termine stattfinden und zu Ergebnissen führen, von Settern, deren Termine verpuffen.",
  ["SRC-050"])
])

# ---------------- L02 ----------------
insert_after_first(L['M01-L02'],[
 book("Kapitel 1.2","Wie Menschen kaufen",[
  "Kaum jemand kauft eine Wärmepumpe, eine Agenturbetreuung oder eine Software spontan. Zwischen dem ersten Gedanken („Unsere Heizung ist alt“) und der Unterschrift liegen oft Wochen oder Monate. In dieser Zeit sammeln Menschen Informationen, sprechen mit Familie oder Kollegen, vergleichen Anbieter und schieben die Entscheidung manchmal wieder auf. Das ist normal – und es ist der Grund, warum der Zeitpunkt deines Kontakts so wichtig ist.",
  "Drei Fragen helfen dir, die Phase eines Interessenten einzuschätzen. Erstens: Weiß er, welches Problem er lösen will? Zweitens: Kennt er schon mögliche Lösungen? Drittens: Vergleicht er bereits konkrete Anbieter? Wer bei Frage eins noch unsicher ist, braucht Orientierung, keinen Verkaufstermin. Wer bei Frage drei angekommen ist, braucht schnell einen kompetenten Ansprechpartner – sonst entscheidet er sich für den Anbieter, der zuerst geantwortet hat.",
  "Der Funnel ist die Brille des Unternehmens auf denselben Vorgang. Er zeigt, wie viele Menschen von Stufe zu Stufe weiterkommen. Als Setter beeinflusst du vor allem drei Übergänge: vom Lead zum qualifizierten Lead, vom qualifizierten Lead zum gebuchten Termin und vom gebuchten zum tatsächlich wahrgenommenen Termin. Wenn du diese drei Übergänge sauber machst, ist dein Beitrag messbar.",
  "Ein häufiger Denkfehler: „Wer ein Formular ausfüllt, will kaufen.“ Ein Formular zeigt Interesse, keine Kaufbereitschaft. Manche wollen nur einen Leitfaden, andere sind schon bei drei Anbietern im Gespräch. Deshalb fragst du nach, statt zu vermuten. Ein einfacher Satz reicht: „Planen Sie schon konkret, oder sammeln Sie erst Informationen?“ Die Antwort sagt dir, welcher nächste Schritt passt – und der Interessent fühlt sich verstanden statt bedrängt.",
  "Und noch etwas: Menschen springen zwischen den Phasen. Wer heute „nur Infos“ will, kann nach einem schlechten Winter plötzlich dringend handeln wollen. Deshalb ist ein sauber dokumentiertes „Nurturing“ – mit Erlaubnis des Kunden – oft mehr wert als ein erzwungener Termin."
 ],["SRC-043","SRC-050"]),
 skill("Phase erfragen statt raten","gespraech",
  "Mit einer neutralen Entweder-oder-Frage herausfinden, wie weit der Interessent ist.",
  ["Bezug auf die Aktion nehmen (Formular, Download, Nachricht).","Zwei ehrliche Optionen anbieten: konkret planen oder Infos sammeln.","Beide Antworten als in Ordnung signalisieren.","Den nächsten Schritt an der Antwort ausrichten."],
  "Wer zwei gleichwertige Optionen bekommt, muss sich nicht rechtfertigen und antwortet ehrlicher. Du vermeidest, jemanden in eine Phase zu drängen, in der er nicht ist.",
  "Praxisheuristik (Expertenmeinung). Grundprinzip: Autonomie respektieren senkt Widerstand – vgl. Forschung zu Reaktanz und „But you are free“ (Carpenter 2013; Effekt in strengen Studien deutlich kleiner, Fillon et al.).",
  "„Sie haben sich unseren Altbau-Leitfaden angesehen – planen Sie schon konkret etwas, oder sammeln Sie erst Informationen? Beides ist völlig in Ordnung.“",
  "Nicht als Trick verwenden, um anschließend trotzdem auf einen Termin zu drängen. Wenn jemand „nur Infos“ sagt, gibst du Infos.",
  ["SRC-052","SRC-053","SRC-050"])
])

# ---------------- L03 ----------------
insert_after_first(L['M01-L03'],[
 book("Kapitel 1.3","Warm, kalt, privat, geschäftlich",[
  "Im Vertrieb spricht man von warmen und kalten Kontakten. Warm ist ein Kontakt, der sich selbst gemeldet oder einer Kontaktaufnahme zugestimmt hat. Kalt ist ein Kontakt, der noch nie mit dem Unternehmen zu tun hatte. Für dich als Einsteiger ist die Unterscheidung doppelt wichtig: Warme Kontakte sind leichter, und sie sind rechtlich meist unproblematischer.",
  "In Deutschland regelt vor allem § 7 des Gesetzes gegen den unlauteren Wettbewerb (UWG), wann Werbung belästigend ist. Vereinfacht gilt: Privatpersonen darfst du nur mit vorheriger ausdrücklicher Einwilligung zu Werbezwecken anrufen; diese Einwilligung muss nachweisbar dokumentiert sein. Bei Unternehmen genügt für Anrufe eine sogenannte mutmaßliche Einwilligung – das heißt, es müssen konkrete Umstände vorliegen, aus denen man schließen kann, dass der Anruf erwünscht ist. Werbe-E-Mails und Werbe-Direktnachrichten brauchen grundsätzlich eine vorherige Einwilligung, auch bei Unternehmen. Das ist Lernstoff, keine Rechtsberatung – im Zweifel entscheidet dein Auftraggeber mit seiner Rechtsberatung.",
  "Warum ist das für dich relevant, wenn du „nur“ Termine machst? Weil Verstöße teuer werden können – für den Auftraggeber und manchmal auch für dich. Die Bundesnetzagentur hat 2025 knapp 40.000 Beschwerden über unerlaubte Werbeanrufe erhalten und über eine Million Euro Bußgelder verhängt. Ein Setter, der diese Regeln kennt, ist für Auftraggeber wertvoller als einer, der „einfach anruft“.",
  "Bei B2B und B2C unterscheidet sich außerdem das Gespräch selbst. Im B2B sprichst du oft mit jemandem, der nicht allein entscheidet: Es gibt Vorgesetzte, Einkauf, IT oder eine Geschäftsführung. Deine Frage „Wer ist noch beteiligt?“ ist dort Pflicht. Im B2C sind es meist Partnerin, Partner oder Familie. Auch hier gilt: Wer den Mitentscheider nicht kennt, bucht Termine, die platzen.",
  "Und schließlich die Geschwindigkeit: Eine viel zitierte Auswertung von 1,25 Millionen Online-Leads (Harvard Business Review, 2011) fand, dass Unternehmen, die innerhalb einer Stunde reagierten, Leads etwa siebenmal häufiger qualifizierten als Unternehmen, die erst eine Stunde später reagierten. Das ist ein Zusammenhang aus US-Daten, kein Naturgesetz. Die Botschaft ist trotzdem klar: Wer sich gemeldet hat, erwartet eine zügige, persönliche Antwort."
 ],["SRC-019","SRC-020","SRC-021","SRC-005"]),
 skill("Speed-to-Lead mit Substanz","prozess",
  "Schnell antworten – aber mit einer persönlichen, vorbereiteten Nachricht statt einer leeren Floskel.",
  ["Benachrichtigungen für neue Leads aktivieren (in deinen Arbeitszeiten).","30 Sekunden Vorbereitung: Was hat die Person angefragt? Name richtig?","Vorlage mit festen Bausteinen nutzen, aber den Bezug individuell schreiben.","Wenn du nicht sofort kannst: kurze ehrliche Zwischennachricht („Ich melde mich heute bis 17 Uhr“) – und das Versprechen halten."],
  "Wer gerade aktiv sucht, hat das Thema im Kopf. Eine Stunde später kann er schon mit einem anderen Anbieter sprechen oder abgelenkt sein.",
  "HBR 2011 (Oldroyd et al.): Kontakt innerhalb einer Stunde ≈ 7× höhere Qualifizierungswahrscheinlichkeit (korrelativ, US-Daten). Eine angekündigte und eingehaltene Rückmeldung stärkt Vertrauen (Integrität im Vertrauensmodell von Mayer et al. 1995).",
  "„Hallo Herr Weber, danke für Ihre Anfrage zur PV-Anlage von vorhin! Ich bin Mira von SolarNord. Passt es, wenn ich Ihnen zwei kurze Fragen stelle?“",
  "Schnelligkeit rechtfertigt keine Kontaktaufnahme ohne Einwilligung und keine Nachrichten außerhalb vereinbarter Kanäle oder zu unpassenden Zeiten.",
  ["SRC-005","SRC-059"]),
 check("Q-M01-031")
])

# ---------------- L04 ----------------
insert_after_first(L['M01-L04'],[
 book("Kapitel 1.4","Anatomie eines guten Erstgesprächs",[
  "Ein gutes Erstgespräch fühlt sich für den Kunden nicht wie ein Verhör an, sondern wie ein angenehmes, kurzes Gespräch mit jemandem, der sich auskennt und zuhört. Trotzdem steckt dahinter eine klare Struktur. Die vier Phasen – Eröffnung, Bedarf, Zusammenfassung, nächster Schritt – sind dein Geländer. Du kannst daran entlanggehen, ohne dass der Kunde es merkt.",
  "Die Eröffnung entscheidet, ob du überhaupt eine Antwort bekommst. Sie hat drei Aufgaben: Wer bist du? Warum meldest du dich? Darf es jetzt sein? Fehlt eine davon, wirkt die Nachricht wie Spam oder wie ein Überfall. Gerade die Erlaubnisfrage („Passt es gerade?“) ist mächtiger, als sie aussieht: Sie gibt dem Kunden Kontrolle, und Menschen, die Kontrolle haben, öffnen sich eher.",
  "In der Bedarfsphase stellst du Fragen – aber nicht zehn auf einmal. Beginne breit („Was hat Sie dazu gebracht …?“) und werde dann konkreter. Eine Studie mit Live-Gesprächen (Huang et al., 2017) fand: Menschen, die mehr Fragen stellen, vor allem Folgefragen zu dem, was der andere gerade gesagt hat, werden als sympathischer wahrgenommen. Folgefragen beweisen, dass du zugehört hast. Eine Folgefrage greift ein Wort des Kunden auf: „Sie sagten, die Kosten sind gestiegen – um wie viel ungefähr?“",
  "Die Zusammenfassung ist die Phase, die Einsteiger am häufigsten überspringen – und sie ist eine der wirksamsten. Wer zusammenfasst, korrigiert Missverständnisse, bevor sie den Termin ruinieren. Und der Kunde hört seine eigenen Ziele noch einmal klar formuliert. In einer Studie zu aktivem Zuhören (Weger et al., 2014) fühlten sich Menschen, deren Aussagen in eigenen Worten wiedergegeben wurden, stärker verstanden als Menschen, die nur ein „Okay“ oder einen Ratschlag bekamen.",
  "Der nächste Schritt ist kein Abschluss, sondern eine logische Folge. Wenn Bedarf, Passung, Zeitrahmen und Entscheider stimmen, schlägst du den Termin vor – mit Dauer, Format und zwei konkreten Zeitfenstern. Wenn etwas fehlt, ist der nächste Schritt eine weitere Frage, Information oder eine spätere Kontaktaufnahme mit Erlaubnis. Und wenn es nicht passt, ist der nächste Schritt eine ehrliche, freundliche Verabschiedung."
 ],["SRC-054","SRC-055","SRC-013"]),
 skill("Die Folgefrage","gespraech",
  "Eine Frage stellen, die ein konkretes Wort oder Detail aus der letzten Antwort aufgreift.",
  ["Achte auf Signalwörter in der Antwort (z. B. „teuer“, „endlich“, „mein Mann“).","Greife genau dieses Wort auf.","Frage offen nach: Wie? Was genau? Woran merken Sie das?","Nur eine Frage pro Nachricht."],
  "Folgefragen zeigen Zuhören und bringen dich von der Oberfläche zum eigentlichen Motiv.",
  "Huang et al. (2017, JPSP): Folgefragen erhöhen Sympathie über wahrgenommene Responsivität; im Speed-Dating mehr Zusagen für ein zweites Treffen.",
  "Kunde: „Wir wollen da endlich was ändern.“ → „Sie sagen ‚endlich‘ – beschäftigt Sie das Thema schon länger?“",
  "Folgefragen dienen dem Verstehen, nicht dem Aushorchen privater Details, die für das Angebot irrelevant sind.",
  ["SRC-054"]),
 skill("Der Weil-Satz","psychologie",
  "Bei jeder Bitte einen kurzen, wahren Grund nennen.",
  ["Bitte formulieren („Darf ich zwei Fragen stellen …“).","Mit „damit“ oder „weil“ einen echten Grund anhängen („… damit unser Berater gut vorbereitet ist“).","Grund aus Sicht des Kunden formulieren."],
  "Eine Begründung macht eine Bitte nachvollziehbar und weniger willkürlich.",
  "Klassische Kopierer-Studie (Langer, Blank & Chanowitz 1978): Begründungen erhöhten Zustimmung bei kleinen Bitten. Kleine Stichprobe, Replikationen gemischt – als plausibles Prinzip nutzen, nicht als Garantie.",
  "„Darf ich kurz fragen, wie Sie aktuell heizen? Damit unser Energieberater im Termin nicht bei null anfangen muss.“",
  "Nur echte Gründe. Ein erfundener Grund („weil das Angebot morgen endet“) ist Täuschung.",
  ["SRC-058"])
])

# ---------------- L05 ----------------
insert_after_first(L['M01-L05'],[
 book("Kapitel 1.5","Qualifizieren heißt aussortieren dürfen",[
  "Qualifizieren klingt technisch. Im Kern ist es eine einfache Frage: Passt dieses Angebot zu diesem Menschen, jetzt? Die Antwort kann Ja, Noch nicht oder Nein sein – und alle drei Antworten sind gute Ergebnisse, wenn sie stimmen. Ein schlechtes Ergebnis ist nur ein falsches Ja.",
  "Für dieses Training merkst du dir vier Pflichtkriterien: Bedarf, Passung, Zeitrahmen und Entscheider. Eine Eselsbrücke: „B-P-Z-E – Bevor Planung Zeit Erfordert.“ Bedarf: Gibt es ein konkretes Problem oder Ziel? Passung: Gehört der Mensch zur Zielgruppe – Eigentümer statt Mieter, Firma mit passender Größe? Zeitrahmen: Soll in absehbarer Zeit etwas passieren? Entscheider: Wer entscheidet mit, und ist diese Person beim Termin dabei?",
  "Budget ist ein heikles Thema. In manchen Branchen fragt der Setter gar nicht danach, weil das der Berater klärt. In anderen – etwa bei Agenturen mit Mindestbudget – ist es das wichtigste Kriterium überhaupt. Frag deinen Auftraggeber vor Projektbeginn, wie mit Budget umzugehen ist. Wenn du fragst, dann offen und mit Begründung: „Damit ich einschätzen kann, ob wir passen: Welchen Rahmen haben Sie eingeplant?“",
  "Bekannte Raster wie BANT (Budget, Authority, Need, Timing) helfen beim Strukturieren. Sie sind Erfahrungswissen aus der Praxis, kein wissenschaftlich bewiesenes Optimum. Nutze sie als Checkliste im Kopf, nie als Fragebogen, den du abarbeitest. Der Kunde soll ein Gespräch erleben, kein Formular.",
  "Und dann die Dokumentation. Alles, was du erfahren hast, gehört ins CRM – und zwar so, wie der Kunde es gesagt hat. Was du nicht erfahren hast, markierst du als „nicht erfragt“. Das ist kein Eingeständnis von Schwäche, sondern Professionalität: Der Berater weiß dann genau, wo er ansetzen muss."
 ],["SRC-047","SRC-050"]),
 skill("B-P-Z-E im Kopf","prozess",
  "Vor jedem Terminvorschlag gedanklich vier Kriterien abhaken.",
  ["Bedarf geklärt? (konkretes Problem/Ziel)","Passung geklärt? (Zielgruppe, Eigentum, Firmengröße)","Zeitrahmen geklärt?","Entscheider geklärt und beim Termin dabei?","Fehlt etwas: erst fragen, dann vorschlagen."],
  "Ein fehlendes Kriterium ist der häufigste Grund für geplatzte oder ergebnislose Termine.",
  "Praxisheuristik, abgeleitet aus BANT (Expertenmeinung). Im Simulator wird ein Termin ohne vollständige Kriterien hart begrenzt (Gate G2).",
  "Innerer Check vor dem Vorschlag: „Bedarf ✓ – Eigentum ✓ – vor dem Winter ✓ – Ehemann? ✗ → erst fragen: ‚Wer entscheidet bei Ihnen mit?‘“",
  "Die Kriterien dienen der Passung, nicht dem Ausfragen. Keine Fragen zu Einkommen, Gesundheit oder anderen sensiblen Daten.",
  ["SRC-047","SRC-050"]),
 check("Q-M01-032")
])

# ---------------- L06 ----------------
insert_after_first(L['M01-L06'],[
 book("Kapitel 1.6","Wo Überzeugung endet",[
  "Es gibt eine Menge Videos und Kurse, die „Psychotricks“ für den Vertrieb versprechen. Manche davon sind harmlos, manche wirken kaum, und manche sind schlicht Manipulation. In dieser Akademie lernst du psychologische Prinzipien – aber immer mit der Frage: Hilft das dem Kunden, eine gute Entscheidung zu treffen?",
  "Ein Beispiel ist die Knappheit. Es stimmt, dass Menschen Dinge begehrenswerter finden, wenn sie knapp sind. Wenn ein Berater wirklich nur noch zwei Termine in dieser Woche frei hat, darfst du das sagen. Wenn du aber „Nur noch heute!“ schreibst, obwohl das nicht stimmt, ist das eine Täuschung – und in vielen Fällen auch wettbewerbswidrig. Die Regel ist einfach: Wahre Informationen dürfen wirken. Erfundene nicht.",
  "Ein zweites Beispiel ist der Umgang mit einem Nein. In vielen „Closing“-Trainings wird gelehrt, ein Nein sei nur der Anfang. Für einen Setter gilt das Gegenteil: Ein ausdrückliches Nein beendet die Werbeansprache. Du darfst fragen, ob du etwas falsch verstanden hast, wenn die Antwort unklar ist. Aber „Nein, ich möchte keinen Termin“ ist klar. Wer hier nachbohrt, erzeugt Beschwerden, schadet dem Auftraggeber und – nicht zuletzt – sich selbst.",
  "Interessanterweise wirkt Respekt oft besser als Druck. Wer betont, dass der andere frei entscheiden darf („Sie entscheiden das natürlich ganz in Ruhe“), senkt den inneren Widerstand. Eine Meta-Analyse über 42 Studien fand für diese „But you are free“-Formulierung einen positiven Effekt. Eine neuere Re-Analyse zeigt aber: In methodisch strengen Studien war der Effekt kaum noch messbar. Das ist typisch für Psychologie im Vertrieb – viele Effekte sind kleiner, als Bestseller behaupten. Deshalb lernst du hier die ehrliche Version: Respekt ist richtig, auch wenn er kein Zaubertrick ist.",
  "Zum Schluss deine Rolle: Du bist kein Fachberater. Das schützt den Kunden vor falschen Auskünften – und dich vor Verantwortung, die du nicht tragen kannst. Wenn du unsicher bist, ob eine Frage in deine Rolle fällt, gilt: Würde eine falsche Antwort dem Kunden Geld oder Sicherheit kosten? Dann übergibst du."
 ],["SRC-038","SRC-052","SRC-053","SRC-019"]),
 skill("Autonomie betonen","psychologie",
  "Ausdrücklich sagen, dass der Kunde frei entscheidet.",
  ["Vorschlag machen.","Freiheit benennen: „Sie entscheiden das ganz in Ruhe.“","Alternative anbieten (z. B. Infos statt Termin).","Die Entscheidung akzeptieren – egal wie sie ausfällt."],
  "Druck erzeugt Widerstand (Reaktanz). Freiheit nimmt den Druck heraus und macht ehrliche Antworten wahrscheinlicher.",
  "Carpenter (2013): 42 Studien, positiver Effekt. Fillon et al. (Re-Meta-Analyse): g = 0,44 insgesamt, aber g = 0,11 (nicht signifikant) in Studien mit geringem Verzerrungsrisiko. Fazit: ethisch richtig, Wirkung möglicherweise klein.",
  "„Ein Gespräch mit unserer Beraterin wäre der nächste Schritt. Ob das für Sie gerade passt, entscheiden natürlich Sie – ich kann Ihnen alternativ auch erst unseren Leitfaden schicken.“",
  "Die Formel darf nicht als Verkaufsfloskel missbraucht werden, nach der man trotzdem weiter drängt.",
  ["SRC-052","SRC-053"]),
 myth("„NLP-Techniken wie ‚Pacing & Leading‘ oder Augenbewegungen verraten, wie du Kunden steuerst.“",
  "Eine Übersicht über 35 Jahre Forschung zu Neuro-Linguistischem Programmieren fand kaum empirische Belege für die zentralen NLP-Annahmen. Was in NLP-Seminaren funktioniert, sind meist allgemeine Kommunikationsgrundlagen – Zuhören, Zusammenfassen, Rapport –, die du hier ohne Mythen lernst.",
  ["SRC-062"]),
 check("Q-M01-033")
])

# ---------------- New lessons L07, L08 ----------------
m['lessons'].append({
 "id":"M01-L07","moduleId":"M01","title":"Ein Arbeitstag als Setter","minutes":16,"objectiveIds":["LO-M01-01","LO-M01-05"],
 "sourceIds":["SRC-005","SRC-056","SRC-050"],
 "blocks":[
  {"kind":"text","title":"Worum es geht","body":"Gute Setter sind nicht nur gute Gesprächspartner, sondern auch gut organisiert. In dieser Lektion lernst du, wie ein realistischer Arbeitstag aufgebaut ist und welche Routinen dir Stress ersparen."},
  book("Kapitel 1.7","Struktur schlägt Talent",[
   "Ein typischer Setter-Tag besteht aus vier Arten von Arbeit: neue Anfragen beantworten, laufende Gespräche weiterführen, Termine bestätigen und erinnern sowie dokumentieren. Wer alles gleichzeitig macht, macht vieles halb. Erfahrene Setter arbeiten deshalb in Blöcken.",
   "Ein Beispiel für einen Halbtag: Zu Beginn 15 Minuten Überblick – welche Termine stehen heute und morgen an, welche Leads sind neu, welche Gespräche warten auf Antwort? Danach ein Block für neue Leads, weil Geschwindigkeit hier am meisten zählt. Dann ein Block für laufende Gespräche. Danach Bestätigungen und Erinnerungen für die Termine von morgen. Am Ende 15 Minuten Dokumentation und ein kurzer Blick auf deine eigenen Zahlen.",
   "Neben der Struktur zählt die Vorbereitung. Bevor du einem Lead schreibst, nimmst du dir 30 Sekunden: Wie heißt die Person? Was hat sie angefragt? Über welchen Kanal kam sie? Gibt es eine Notiz aus einem früheren Kontakt? Diese 30 Sekunden machen den Unterschied zwischen einer persönlichen Nachricht und einer Massennachricht.",
   "Vorlagen sind erlaubt und sinnvoll – aber als Baukasten, nicht als Kopiervorlage. Eine gute Vorlage hat feste Bausteine (Vorstellung, Erlaubnisfrage, erste Bedarfsfrage) und eine Lücke für den persönlichen Bezug. Lies jede Nachricht vor dem Absenden einmal laut im Kopf: Würdest du so mit einem Menschen sprechen?",
   "Und schließlich deine eigenen Zahlen. Nicht, um dich unter Druck zu setzen, sondern um zu lernen. Wie viele Leads hast du kontaktiert? Wie viele wurden qualifiziert? Wie viele Termine fanden statt? Wenn eine Zahl auffällig niedrig ist, weißt du, wo du üben solltest. Diese Kennzahlen vertiefst du in Modul 9."
  ],["SRC-005","SRC-050"]),
  {"kind":"workedExample","title":"Ein Beispiel-Halbtag (4 Stunden)","steps":[
   "08:00–08:15 Überblick: Kalender heute/morgen, neue Leads, offene Gespräche.",
   "08:15–09:30 Neue Leads: jede Anfrage innerhalb deines Blocks persönlich beantworten.",
   "09:30–10:30 Laufende Gespräche weiterführen, Fragen notieren, Übergaben vorbereiten.",
   "10:30–10:45 Pause – wirklich weg vom Bildschirm.",
   "10:45–11:30 Terminbestätigungen und Erinnerungen für morgen.",
   "11:30–12:00 Dokumentation im CRM, Tageszahlen notieren, eine Sache aufschreiben, die du morgen besser machst."
  ]},
  skill("Zeitblöcke statt Dauerfeuer","prozess",
   "Gleichartige Aufgaben bündeln und feste Zeiten dafür einplanen.",
   ["Plane für jede Aufgabenart einen Block.","Schalte während eines Blocks andere Ablenkungen aus.","Lege für neue Leads den frühesten Block fest.","Notiere am Ende des Tages eine konkrete Verbesserung für morgen."],
   "Häufiges Umschalten zwischen Aufgaben kostet Konzentration. Feste Blöcke machen den Tag planbar.",
   "Praxisheuristik (Expertenmeinung). Die Abendnotiz nutzt das Prinzip konkreter Pläne (Gollwitzer & Sheeran 2006: Wenn-dann-Pläne, d = 0,65 auf Zielerreichung).",
   "„Wenn ich morgen um 8:15 Uhr den Lead-Block starte, beantworte ich zuerst alle Anfragen von über Nacht.“",
   "Arbeitszeiten und Erreichbarkeit mit dem Auftraggeber klären; keine Kundennachrichten spät abends, nur weil das Tool es erlaubt.",
   ["SRC-056","SRC-050"]),
  check("Q-M01-034"),
  check("Q-M01-035"),
  {"kind":"reflect","prompt":"Wann am Tag bist du am konzentriertesten? Welcher Block gehört in diese Zeit?"}
 ],
 "summary":["Arbeite in Blöcken: neue Leads, laufende Gespräche, Bestätigungen, Dokumentation.","30 Sekunden Vorbereitung vor jeder Nachricht.","Vorlagen als Baukasten mit persönlichem Bezug.","Eigene Zahlen zum Lernen nutzen, nicht zum Stressen."]
})
m['lessons'].append({
 "id":"M01-L08","moduleId":"M01","title":"Die Übergabe, die der Berater liebt","minutes":16,"objectiveIds":["LO-M01-05","LO-M01-04"],
 "sourceIds":["SRC-056","SRC-057","SRC-050"],
 "blocks":[
  {"kind":"text","title":"Worum es geht","body":"Ein Termin ist erst dann gut, wenn er stattfindet und der Berater bestens vorbereitet ist. In dieser Lektion lernst du, wie du Termine verbindlich bestätigst und eine Übergabe schreibst, mit der der Berater sofort starten kann."},
  book("Kapitel 1.8","Vom Ja zum stattfindenden Termin",[
   "Ein Ja im Chat ist ein guter Moment – aber noch kein stattfindender Termin. Zwischen Buchung und Gespräch passiert das Leben: Der Kunde vergisst den Termin, ihm kommt etwas dazwischen, oder er bekommt kalte Füße. Deshalb endet deine Arbeit nicht mit der Buchung.",
   "Die erste Stellschraube ist die Bestätigung direkt im Gespräch. Wiederhole Datum, Uhrzeit, Format und Teilnehmer. Frage, ob der Kunde sich den Termin direkt eintragen kann. Das klingt banal, hat aber einen psychologisch gut untersuchten Hintergrund: Menschen setzen Vorhaben deutlich häufiger um, wenn sie einen konkreten Plan haben – wann, wo, wie. In einer Meta-Analyse über 94 Tests hatten solche Wenn-dann-Pläne einen mittleren bis großen Effekt auf die Zielerreichung. In einer Feldstudie erhöhte schon die Aufforderung, Datum und Uhrzeit für eine Impfung aufzuschreiben, die Impfquote spürbar.",
   "Die zweite Stellschraube ist die Erinnerung. Eine kurze Nachricht am Vortag mit Uhrzeit, Link und der Möglichkeit, unkompliziert zu verschieben, ist für die meisten Kunden hilfreich – vorausgesetzt, sie haben dieser Art der Kontaktaufnahme zugestimmt. Die Möglichkeit zu verschieben ist wichtig: Wer ehrlich absagen kann, erscheint nicht einfach nicht.",
   "Die dritte Stellschraube ist die Übergabe. Ein Berater, der den Kunden mit „Erzählen Sie mal, worum geht es?“ begrüßt, obwohl der Kunde dir schon alles erklärt hat, verschenkt Vertrauen. Deine Übergabe enthält deshalb: Anlass der Anfrage, Bedarf in den Worten des Kunden, Passung, Zeitrahmen, Entscheider, offene Fragen des Kunden und was ausdrücklich nicht erfragt wurde.",
   "Schreibe die Übergabe so, dass jemand, der den Kunden nie gesehen hat, in einer Minute weiß, worum es geht. Und schreibe nur Fakten. „Wirkt wohlhabend“ ist keine Information. „Kunde nannte Budget von etwa 20.000 €“ schon."
  ],["SRC-056","SRC-057","SRC-050"]),
  {"kind":"example","title":"Beispiel-Übergabe (erfundene Daten)","body":"Anlass: Formular „Wärmepumpe“, 02.10.\nBedarf (Zitat): „Gasheizung 24 Jahre alt, Kosten stark gestiegen, wir wollen endlich etwas ändern.“\nPassung: Eigentümerin, Einfamilienhaus Baujahr 1978.\nZeitrahmen: vor dem nächsten Winter.\nEntscheider: gemeinsam mit Ehemann Tom – beide beim Termin.\nOffene Fragen der Kundin: Förderung? Lautstärke der Außeneinheit?\nNicht erfragt: Budget, aktueller Gasverbrauch.\nTermin: Do 19:00 Uhr, Video, Bestätigung + Erinnerung am Vortag."},
  skill("Der Wenn-dann-Termin","psychologie",
   "Den Termin so konkret machen, dass der Kunde ihn in seinen Alltag einplant.",
   ["Datum, Uhrzeit, Dauer, Format und Teilnehmer wiederholen.","Fragen, ob der Kunde den Termin direkt in den Kalender einträgt.","Kurz klären, was er vorbereiten kann (z. B. letzte Heizkostenabrechnung).","Verschieben ausdrücklich erlauben."],
   "Konkrete Pläne verbinden eine Situation („Donnerstag 19 Uhr“) mit einer Handlung („Videocall öffnen“) und machen das Vergessen unwahrscheinlicher.",
   "Gollwitzer & Sheeran (2006): Wenn-dann-Pläne d = 0,65 (94 Tests). Milkman et al. (2011): Planungsaufforderung erhöhte Impfquote leicht. Übertragung auf Show-Rates ist plausibel, aber nicht direkt untersucht.",
   "„Dann tragen wir Donnerstag, 19 Uhr, per Video ein – mit Ihnen und Tom. Mögen Sie sich den Termin gleich in den Kalender legen? Falls etwas dazwischenkommt, schreiben Sie mir einfach, dann finden wir einen neuen Termin.“",
   "Keine Schuldgefühle erzeugen („Unser Berater hält sich extra die Zeit frei …“). Ein abgesagter Termin ist besser als ein No-Show.",
   ["SRC-056","SRC-057"]),
  check("Q-M01-036"),
  check("Q-M01-037"),
  check("Q-M01-038")
 ],
 "summary":["Ein Ja ist noch kein stattfindender Termin.","Termin konkret bestätigen und eintragen lassen (Wenn-dann-Plan).","Erinnerung nur mit Einwilligung, Verschieben ausdrücklich erlauben.","Übergabe: Fakten in Kundenworten, offene Fragen, „nicht erfragt“."]
})

# ---------------- New questions ----------------
def q(id,obj,diff,typ,**kw):
    d={"id":id,"moduleId":"M01","objectiveId":obj,"difficulty":diff,"version":1,"type":typ}; d.update(kw); return d
new=[
q("Q-M01-031","LO-M01-03",2,"single",prompt="Was ist die beste Reaktion, wenn ein neuer Inbound-Lead eingeht, du aber gerade in einem anderen Gespräch steckst?",
  options=[{"id":"a","text":"Lead bis morgen liegen lassen, dann in Ruhe antworten","misconception":"Lange Wartezeit hängt mit deutlich geringerer Qualifizierung zusammen.","errorCategory":"prozessfehler"},
           {"id":"b","text":"Kurze persönliche Zwischennachricht mit konkretem Zeitpunkt senden und das Versprechen einhalten"},
           {"id":"c","text":"Sofort eine Standardnachricht mit Terminlink schicken","misconception":"Schnell, aber unpersönlich und ohne Qualifizierung.","errorCategory":"qualifizierungsfehler"},
           {"id":"d","text":"Den Lead anrufen, ohne zu prüfen, ob telefonischer Kontakt vereinbart ist","misconception":"Schnelligkeit rechtfertigt keinen Kanal ohne Einwilligung.","errorCategory":"rechtsfehler"}],
  correct="b",explanation="Eine ehrliche Zwischennachricht hält die Erwartung, und ein eingehaltenes Versprechen stärkt Vertrauen. Speed-to-Lead heißt: schnell UND persönlich.",sourceIds=["SRC-005","SRC-059"]),
q("Q-M01-032","LO-M01-05",2,"ordering",prompt="Bringe die Schritte vor einem Terminvorschlag in eine sinnvolle Reihenfolge.",
  items=[{"id":"propose","text":"Termin mit zwei Zeitfenstern vorschlagen"},{"id":"need","text":"Bedarf erfragen"},{"id":"summary","text":"Zusammenfassen und bestätigen lassen"},{"id":"authority","text":"Entscheider klären"}],
  correctOrder=["need","authority","summary","propose"],explanation="Erst verstehen, dann den Entscheider klären, dann zusammenfassen und erst danach vorschlagen. (Entscheider kann auch vor dem Bedarf geklärt werden – hier zählt: alle Kriterien vor dem Vorschlag.)",sourceIds=["SRC-050"]),
q("Q-M01-033","LO-M01-06",3,"truefalse",prompt="Die „But you are free“-Formulierung hat in methodisch strengen Studien einen großen, gut belegten Effekt auf Zustimmung.",
  correct=False,errorCategory="ueberinterpretation",explanation="Die erste Meta-Analyse (Carpenter 2013) fand einen positiven Effekt; eine Re-Analyse zeigte in Studien mit geringem Verzerrungsrisiko nur g = 0,11 (nicht signifikant). Autonomie zu betonen ist trotzdem ethisch richtig.",sourceIds=["SRC-052","SRC-053"]),
q("Q-M01-034","LO-M01-01",1,"single",prompt="Welche Aufgabe gehört an den Anfang eines Setter-Arbeitstages?",
  options=[{"id":"a","text":"Überblick über Termine, neue Leads und offene Gespräche"},
           {"id":"b","text":"Sofort alle alten Leads der letzten Monate anschreiben","misconception":"Reaktivierung ohne Prüfung der Einwilligung ist rechtlich heikel und nicht dringend.","errorCategory":"rechtsfehler"},
           {"id":"c","text":"Zuerst die Dokumentation von gestern löschen","misconception":"Dokumentation wird gepflegt, nicht gelöscht.","errorCategory":"prozessfehler"},
           {"id":"d","text":"Social Media scrollen, um in Stimmung zu kommen","misconception":"Keine Arbeitsaufgabe.","errorCategory":"prozessfehler"}],
  correct="a",explanation="Ein kurzer Überblick verhindert, dass dringende Dinge (neue Leads, heutige Termine) untergehen.",sourceIds=["SRC-050"]),
q("Q-M01-035","LO-M01-05",2,"multi",prompt="Was macht eine gute Nachrichten-Vorlage aus? (Mehrere Antworten möglich)",
  options=[{"id":"a","text":"Feste Bausteine für Vorstellung und Erlaubnisfrage"},{"id":"b","text":"Eine Lücke für den persönlichen Bezug zur Anfrage"},
           {"id":"c","text":"Sie wird ohne Anpassung an alle Leads gleichzeitig verschickt","misconception":"Massennachrichten wirken unpersönlich und sind oft unzulässig.","errorCategory":"kommunikationsfehler"},
           {"id":"d","text":"Sie klingt laut gelesen wie ein echtes Gespräch"},
           {"id":"e","text":"Sie enthält immer einen Countdown bis zum Angebotsende","misconception":"Künstliche Verknappung ist tabu.","errorCategory":"ethikfehler"}],
  correct=["a","b","d"],explanation="Vorlagen sparen Zeit, wenn sie ein Baukasten mit persönlichem Bezug sind.",sourceIds=["SRC-050"]),
q("Q-M01-036","LO-M01-04",2,"situation",prompt="Wie bestätigst du den Termin am besten?",
  situation="Die Kundin hat gerade „Donnerstag 19 Uhr passt“ geschrieben. Ihr Mann soll dabei sein.",
  options=[{"id":"a","text":"„Super, bis dann!“","quality":"poor","feedback":"Keine Wiederholung der Details, kein Kalendereintrag, keine Info zu Format und Teilnehmern.","errorCategory":"prozessfehler"},
           {"id":"b","text":"„Perfekt: Donnerstag, 19 Uhr, 45 Minuten per Video mit Ihnen und Ihrem Mann. Mögen Sie sich den Termin gleich eintragen? Falls etwas dazwischenkommt, schreiben Sie mir einfach.“","quality":"best","feedback":"Konkreter Plan, Kalendereintrag, Verschieben erlaubt – genau richtig."},
           {"id":"c","text":"„Super. Bitte unbedingt erscheinen, unser Berater hält sich extra frei!“","quality":"poor","feedback":"Erzeugt Schuldgefühle statt Verbindlichkeit.","errorCategory":"kommunikationsfehler"},
           {"id":"d","text":"„Notiert. Falls Sie nicht kommen, berechnen wir 50 € Ausfallgebühr.“","quality":"unacceptable","feedback":"Erfundene Gebühr – Täuschung und Druck.","errorCategory":"ethikfehler"}],
  explanation="Konkrete Wenn-dann-Pläne erhöhen die Umsetzung; ehrliches Verschieben ist besser als ein No-Show.",sourceIds=["SRC-056","SRC-050"]),
q("Q-M01-037","LO-M01-05",3,"errorspot",prompt="Markiere die problematischen Zeilen dieser Übergabenotiz.",
  lines=[{"id":"l1","text":"Anlass: Formular „PV-Anlage“, 01.10.","faulty":False},
         {"id":"l2","text":"Bedarf: „Stromkosten senken, möglichst unabhängig werden“ (Zitat)","faulty":False},
         {"id":"l3","text":"Budget: wirkt wohlhabend, eher hoch","faulty":True,"why":"Vermutung statt Information – „nicht erfragt“ wäre korrekt."},
         {"id":"l4","text":"Entscheider: vermutlich allein","faulty":True,"why":"Vermutung – Entscheider muss erfragt oder als offen markiert werden."},
         {"id":"l5","text":"Offene Frage des Kunden: Wie lange dauert die Montage?","faulty":False}],
  explanation="Übergaben enthalten nur Gesagtes. Vermutungen führen den Berater in die Irre.",sourceIds=["SRC-050"]),
q("Q-M01-038","LO-M01-05",2,"cloze",prompt="Ergänze die Lücken.",
  text="Ein Termin wird verbindlicher, wenn Datum, Uhrzeit und {{g1}} konkret wiederholt werden. Was nicht erfragt wurde, wird in der Übergabe als „nicht {{g2}}“ markiert.",
  gaps=[{"id":"g1","accepted":["Format","das Format","Teilnehmer","die Teilnehmer"]},{"id":"g2","accepted":["erfragt"]}],
  explanation="Konkrete Details machen aus einem Ja einen Plan; „nicht erfragt“ ist ehrliche, nützliche Information.",sourceIds=["SRC-056","SRC-050"]),
q("Q-M01-039","LO-M01-02",2,"situation",prompt="Was ist der passende nächste Schritt?",
  situation="Ein Lead schreibt: „Ich sammle gerade nur Infos, wir wollen frühestens nächstes Jahr etwas machen.“",
  options=[{"id":"a","text":"Trotzdem sofort einen Beratungstermin vorschlagen","quality":"poor","feedback":"Ignoriert die genannte Phase.","errorCategory":"qualifizierungsfehler"},
           {"id":"b","text":"Hilfreiche Infos anbieten und fragen, ob und wann eine spätere Rückmeldung gewünscht ist","quality":"best","feedback":"Passend zur Phase und mit Erlaubnis für späteren Kontakt."},
           {"id":"c","text":"Lead als „kein Interesse“ markieren und nie wieder kontaktieren","quality":"acceptable","feedback":"Respektvoll, aber verschenkt ein mögliches späteres Interesse – er hat nicht Nein gesagt."},
           {"id":"d","text":"„Nächstes Jahr wird es viel teurer, buchen Sie lieber jetzt!“","quality":"unacceptable","feedback":"Unbelegte Angstbotschaft.","errorCategory":"ethikfehler"}],
  explanation="Nurturing mit Erlaubnis ist der passende Schritt für frühe Phasen.",sourceIds=["SRC-043","SRC-050"]),
q("Q-M01-040","LO-M01-04",3,"single",prompt="Welche Antwort ist eine echte Folgefrage?",
  options=[{"id":"a","text":"Kunde: „Die Kosten sind stark gestiegen.“ → „Um wie viel ungefähr sind sie gestiegen?“"},
           {"id":"b","text":"Kunde: „Die Kosten sind stark gestiegen.“ → „Wann haben Sie Zeit für einen Termin?“","misconception":"Wechselt das Thema, statt anzuknüpfen.","errorCategory":"kommunikationsfehler"},
           {"id":"c","text":"Kunde: „Die Kosten sind stark gestiegen.“ → „Haben Sie auch ein Auto?“","misconception":"Irrelevant für den Bedarf.","errorCategory":"kommunikationsfehler"},
           {"id":"d","text":"Kunde: „Die Kosten sind stark gestiegen.“ → „Das geht allen so.“","misconception":"Keine Frage; wirkt abwertend.","errorCategory":"kommunikationsfehler"}],
  correct="a",explanation="Folgefragen greifen ein Detail der letzten Antwort auf und vertiefen es (Huang et al. 2017).",sourceIds=["SRC-054"]),
q("Q-M01-041","LO-M01-06",2,"truefalse",prompt="Wenn ein Berater tatsächlich nur noch zwei freie Termine diese Woche hat, darf ein Setter das wahrheitsgemäß sagen.",
  correct=True,errorCategory="ethikfehler",explanation="Wahre Knappheit ist eine Information. Tabu ist erfundene oder übertriebene Knappheit.",sourceIds=["SRC-038","SRC-050"]),
q("Q-M01-042","LO-M01-06",3,"single",prompt="Was sagt die Forschung zu NLP-Techniken wie dem Deuten von Augenbewegungen?",
  options=[{"id":"a","text":"Sie sind gut belegt und sollten in jedem Verkaufsgespräch genutzt werden","misconception":"Die zentralen NLP-Annahmen sind empirisch kaum gestützt.","errorCategory":"ueberinterpretation"},
           {"id":"b","text":"Die zentralen Annahmen sind empirisch kaum gestützt"},
           {"id":"c","text":"Sie funktionieren nur im Chat","misconception":"Augenbewegungen sind im Chat gar nicht sichtbar – und belegt ist es auch sonst nicht.","errorCategory":"ueberinterpretation"},
           {"id":"d","text":"Sie sind gesetzlich verboten","misconception":"Kein Verbot – aber wissenschaftlich kaum belegt.","errorCategory":"rechtsfehler"}],
  correct="b",explanation="Witkowski (2010) fand nach 35 Jahren Forschung kaum Belege für NLP-Kernannahmen. Wirksam sind die allgemeinen Kommunikationsgrundlagen dieses Kurses.",sourceIds=["SRC-062"]),
]
qs+=new
m['examQuestionIds']+= ["Q-M01-039","Q-M01-040","Q-M01-041","Q-M01-042"]
m['version']="1.1.0"
m['sourceIds']=sorted(set(m['sourceIds']+["SRC-052","SRC-053","SRC-054","SRC-055","SRC-056","SRC-057","SRC-058","SRC-059","SRC-062"]))
json.dump(m,open(P,'w'),ensure_ascii=False,indent=2)
json.dump(qs,open(Q,'w'),ensure_ascii=False,indent=2)
print(len(qs), len(m['lessons']))
