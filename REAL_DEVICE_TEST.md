# 360 SMART – Test auf deinem echten Windows-PC

**Version:** 0.5.0-alpha.3 · **Dauer:** ca. 60–90 Minuten · **Du brauchst:** Windows 10 oder 11,
Internet, deinen Zugang zu 360° online, optional einen API-Key (Anthropic, OpenAI oder Google).

> **Sicherheit zuerst.** Diese Version startet absichtlich im **Dry-Run-Modus**: Sie macht alles,
> zeigt dir mit einem **roten Kreuz** genau an, **wo** sie klicken würde – und klickt **nicht**.
> Echte Klicks gibt es erst, wenn du den Dry Run selbst ausschaltest (Teil 6).
> **Not-Aus jederzeit:** `Strg + Umschalt + X` oder der rote **STOP**-Knopf.

Du musst nichts debuggen. Wenn etwas komisch ist: **Diagnose erstellen** (Teil 10) und mir die ZIP-Datei
schicken. Kreuze in der Checkliste am Ende einfach ✅ oder ❌ an.

---

## Teil 1 – Herunterladen und installieren

1. Öffne die Release-Seite:
   **https://github.com/R8-CRT7/R8/releases/tag/v0.5.0-alpha.3**
2. Klicke unter **Assets** auf **`360SmartSetup.exe`** (ca. 75 MB). Speichern.
3. Öffne den Download-Ordner und mache einen **Doppelklick** auf `360SmartSetup.exe`.

### Windows SmartScreen („Der Computer wurde durch Windows geschützt“)
Das ist bei dieser Alpha **normal**, weil der Installer nicht kostenpflichtig signiert ist.
1. Klicke auf **„Weitere Informationen“** (kleiner Link im blauen Fenster).
2. Prüfe: Bei *App* steht `360SmartSetup.exe`.
3. Klicke auf **„Trotzdem ausführen“**.

> Optional (sicherer): Rechtsklick auf *Start* → *Terminal* → eingeben
> `Get-FileHash $env:USERPROFILE\Downloads\360SmartSetup.exe` → die lange Zahl muss mit der Datei
> `360SmartSetup.exe.sha256` von der Release-Seite übereinstimmen.

4. Im Installer: **Weiter → Weiter → Installieren → Fertigstellen**. Es sind **keine Administratorrechte**
   nötig, und Python wird nicht gebraucht.

✅ **Erwartet:** Im Startmenü gibt es den Ordner **„360 SMART“** mit *360 SMART*, *360 SMART (Demo)* und
*360 SMART - Diagnose erstellen*.

---

## Teil 2 – Erster Start

1. Startmenü → **360 SMART**.
2. Ein Startbildschirm prüft kurz alles (Selbsttest). Danach öffnet sich die **Einrichtung**.
3. Begrüßung → **Get started**.
4. **Choose your AI**: Für den ersten Test wähle **„Demo (offline)“** → *Continue*.
   (Den echten API-Key richten wir in Teil 4 ein.)
5. Die restlichen Schritte mit **Continue** bestätigen, am Ende **Start 360 SMART**.

✅ **Erwartet:** Rechts oben erscheint das **Overlay** (dunkle Glas-Karte „360 SMART“). Oben im Overlay steht
**„DRY RUN · …“**. Das Dashboard ist offen. Ein Fenster „360° online – Simulator“ (Übungs-Simulator) ist offen.

❌ **Wenn nicht:** Startmenü → *360 SMART - Diagnose erstellen* → ZIP schicken.

---

## Teil 3 – Test OHNE echte 360°-Software (Simulator, 5 Minuten)

Der Simulator sieht ähnlich aus wie eine Theoriefrage.

1. Warte 2–5 Sekunden. Das Overlay zeigt **QUESTION DETECTED**, eine **Empfehlung** (z. B. `1 + 3`),
   eine **Begründung** und eine **Confidence** (z. B. 94 %).
2. Drücke **ENTER** (oder den Knopf **CONFIRM (DRY RUN)**).

✅ **Erwartet:**
* Auf den richtigen Kästchen im Simulator erscheinen **rote Kreuze** (ca. 10 Sekunden).
* Im Overlay steht: **„DRY RUN - would click answer 1 at (x, y); answer 3 at (…)“**.
* Im Simulator wird **nichts** angehakt.

3. Drücke **`Strg + Umschalt + X`** (Not-Aus).

✅ **Erwartet:** Das Overlay zeigt groß **STOPPED** (rot). Es passiert nichts mehr.

4. Klicke im Overlay auf **RESUME** (oder drücke **F8**). Das Overlay zeigt wieder „WATCHING“ /
   „QUESTION DETECTED“.

---

## Teil 4 – API-Key einrichten und KI-Anbieter wählen

> Dein API-Key wird im **Windows-Anmeldeinformationsmanager** gespeichert – nie in Dateien, Logs oder der
> Diagnose. **Schicke deinen Key niemals in einen Chat oder an mich.**

1. Key besorgen (nur einer nötig):
   * **Anthropic (empfohlen):** https://console.anthropic.com → *API Keys* → *Create Key*
   * **OpenAI:** https://platform.openai.com/api-keys
   * **Google Gemini:** https://aistudio.google.com/apikey
   * Lege beim Anbieter ein kleines Guthaben bzw. Limit an (z. B. 5 €). Die App zeigt die geschätzten Kosten auf
     der Seite *AI* – bitte nach dem Test ablesen und mitschicken. (Echte Kosten wurden noch nicht gemessen.)
2. Dashboard → links **AI**.
3. Oben die Karte deines Anbieters anklicken (z. B. **Anthropic Claude**).
4. Bei **API key**: Key einfügen (`Strg + V`) → **Save key**.
5. **Test connection** klicken.

✅ **Erwartet:** grüne Meldung, dass die Verbindung funktioniert.
❌ **Wenn nicht:** Key nochmal kopieren (ohne Leerzeichen), Guthaben prüfen, dann *Diagnose erstellen*.

6. Dashboard → **Settings** → **Demo mode** ausschalten. Der Simulator schließt sich.

---

## Teil 5 – Test MIT der echten 360°-Software (weiter im Dry Run)

### 5.1 Fenstererkennung
1. Öffne **360° online** wie gewohnt (Browser oder App) und melde dich an.
2. Öffne eine **Übungsfrage** mit Ankreuz-Antworten. Fenster **nicht minimieren**, am besten maximiert.
3. Schau ins Overlay.

✅ **Erwartet:** Es steht **nicht** mehr „Looking for the 360° window…“, sondern **„Calibration required“**
(beim allerersten Mal) oder es wird schon eine Frage erkannt.
❌ **Wenn „Looking for the 360° window…“ bleibt:** Dashboard → **Detection** → *Learning window*: Dort steht,
nach welchen Fenstertiteln gesucht wird. Trage eine Zeile mit einem Wort aus dem Titel deines
360-Fensters ein (steht oben in der Titelleiste / im Browser-Tab) → *Save patterns*. Hilft das nicht: *Diagnose
erstellen*.

### 5.2 Kalibrierung (einmalig, ca. 2 Minuten)
1. Lass die Frage in 360° online sichtbar. Dashboard → **Detection** → **Calibrate new profile**.
2. Es erscheint ein Standbild deines Bildschirms.
   * **Schritt 1:** Ziehe mit der Maus einen Rahmen **um den Fragetext** → *Next*.
   * **Schritt 2:** Ziehe einen Rahmen **um alle Antworten – inklusive der Kästchen links** → *Next*.
   * **Schritt 3 (optional):** Rahmen um das Situationsbild (falls vorhanden) → sonst *Skip*.
3. Im Testschritt siehst du die erkannten Texte und **farbige Rahmen um die Kästchen**:
   **grün = Kästchen sicher gefunden**, **orange = nur geschätzt**.
4. Namen eingeben (z. B. „360 Browser“) → **Save**.

✅ **Erwartet:** Frage und Antworten sind richtig gelesen, Kästchen **grün**.
❌ **Wenn orange:** Den Antwort-Rahmen etwas größer ziehen (Kästchen ganz einschließen). Bleibt es orange: Im
Sicherheitsmodus wird dann **nicht geklickt** (richtig so) – bitte *Diagnose erstellen* und schicken.

### 5.3 OCR- und Antworterkennung
1. Zurück zu 360° online (Frage sichtbar). Das Overlay zeigt nach 2–6 Sekunden die Frage, die
   **empfohlenen Antworten**, **Begründung** und **Confidence**.
2. Vergleiche: Ist der **Fragetext** im Overlay richtig? Stimmen die **Antwortnummern**?

### 5.4 Bestätigung und „wo würde geklickt“
1. Drücke **ENTER** (oder *CONFIRM (DRY RUN)*).

✅ **Erwartet:** **Rote Kreuze** genau **auf den Kästchen** der empfohlenen Antworten. **Nichts wird angeklickt.**
❌ **Wenn die Kreuze daneben liegen:** Foto/Screenshot machen (`Windows + Umschalt + S`), *Diagnose erstellen*.

2. Beantworte die Frage danach **selbst** in 360° online und gehe zur nächsten Frage. Wiederhole 5.3–5.4 für
   **10 Fragen**.

---

## Teil 6 – Echter Klick (erst wenn die Kreuze bei 10 Fragen richtig lagen)

1. Dashboard → **Settings** → Abschnitt **Safety** → **Dry run (never click)** ausschalten.
   **Safe mode** bleibt **an**!
2. Overlay: Oben steht jetzt **nicht** mehr „DRY RUN“.

### 6.1 Tatsächlicher Klick
1. Neue Frage öffnen, Empfehlung abwarten, **ENTER**.

✅ **Erwartet:** Die App liest die Frage **nochmal**, klickt die Kästchen, prüft das Ergebnis und meldet
**„Selected and verified (1 attempt)“** (grün). In 360° online sind die richtigen Kästchen angehakt.

### 6.2 Niedrige Confidence → kein Klick
Wenn das Overlay **„CHECK THIS ONE“ / MANUAL CHECK** (orange) zeigt, heißt der Knopf **„ACCEPT · NO CLICK“**.
ENTER funktioniert dann absichtlich nicht.

✅ **Erwartet:** Nach Klick auf den Knopf: **„Not clicked: confidence … below the safety threshold“** – es wird
**nicht** geklickt. Beantworte selbst.

### 6.3 Hotkeys
* **F9** = Frage neu lesen · **F8** = Pause/Weiter · **ESC** = Empfehlung ablehnen ·
  **Strg+Umschalt+M** = Overlay-Größe · **Strg+Umschalt+X** = **NOT-AUS**

✅ **Erwartet:** Alle funktionieren, auch während der Browser im Vordergrund ist.

### 6.4 Not-Aus während der Ausführung
1. Neue Frage mit **zwei** richtigen Antworten, Empfehlung abwarten.
2. **ENTER** drücken und **sofort** `Strg + Umschalt + X`.

✅ **Erwartet:** **STOPPED**. Je nachdem, wie schnell du warst: kein Kästchen, nur das erste – oder der
Vorgang war schon fertig. **Nach STOPPED wird nie mehr geklickt.** Weiter mit **RESUME**.

### 6.5 Verdecktes Klickziel
1. Empfehlung abwarten. Öffne z. B. den **Editor** (Notepad) und schiebe ihn **über die Kästchen**.
2. Klicke zurück in 360° online (Editor bleibt über den Kästchen) und drücke **ENTER**.

✅ **Erwartet:** **„not clicked: another window covers the answer“**. Im Editor und in 360 wird **nichts**
angeklickt. Editor schließen, **F9**, normal weiter.

> Tipp: Schiebe auch das **Overlay** nie über die Antworten – auch dann wird aus Sicherheit nicht geklickt.

### 6.6 Verändertes Fenster
1. Empfehlung abwarten. Ziehe das 360-Fenster an der Titelleiste etwas zur Seite (oder ändere die Größe).
2. Sofort **ENTER**.

✅ **Erwartet (beides ist richtig):**
* Die App liest die Frage **neu** (kurz „ANALYZING“) und zeigt die Empfehlung erneut, **oder**
* sie meldet **„window moved or resized since the question was read - nothing was clicked“**.
❌ **Falsch wäre:** ein Klick an der alten Stelle → sofort Not-Aus, *Diagnose erstellen*.

### 6.7 Mehrere Fragen hintereinander
Beantworte **5 Fragen** nacheinander: Empfehlung → ENTER → verifiziert → selbst zur nächsten Frage.

✅ **Erwartet:** Jede neue Frage wird automatisch erkannt. Keine Klicks auf die vorherige Frage.

---

## Teil 7 – Der 50-Fragen-Test

Ziel: echte Zahlen (OCR-Genauigkeit, Erfolgsquote, Fehlklicks, Geschwindigkeit). Die App protokolliert
**jede Frage automatisch**.

1. **360 SMART neu starten** (Tray-Symbol unten rechts → *Quit*, dann wieder starten) – damit beginnt ein
   neues, sauberes Protokoll.
2. **Safe mode an**, **Dry run aus** (wie in Teil 6).
3. Beantworte **50 Fragen** wie in 6.7. Bei jeder Frage:
   * Ist die Empfehlung **richtig** → **ENTER**.
   * Ist sie **falsch** oder unsicher → **ESC**, und beantworte selbst.
   * Wenn 360° online dir nach dem Antworten die Lösung zeigt und die App **falsch** lag: kurz notieren
     („Frage 17 falsch, richtig wäre 2“) – ein Zettel reicht.
4. Danach: **Diagnose erstellen** (Teil 10).

> Optional für genauere Zahlen: Die Datei `protocol.csv` (liegt im ZIP und unter
> `%APPDATA%\360Smart\trace\protocol.csv`) mit Excel öffnen und in den Spalten **OCR Question Correct**,
> **Answers Correct**, **Expected Answer**, **Click Correct** `ja`/`nein` bzw. die richtige Antwort eintragen,
> speichern, dann nochmal *Diagnose erstellen*. Deine Einträge bleiben erhalten. Wenn du das nicht machst, ist
> das okay – ich werte die Bilder im ZIP selbst aus.

Die App berechnet daraus: *Question OCR Accuracy, Answer OCR Accuracy, End-to-End Success Rate, False Click Rate,
Prevented Unsafe Clicks, Median/P95 Latency* (Datei `metrics.txt` im ZIP).

---

## Teil 8 – Was die Sicherheitsfunktionen bedeuten

| Situation | Was die App tut |
|---|---|
| Keine Bestätigung von dir | **Nie** ein Klick |
| Niedrige Confidence | Kein Klick („ACCEPT · NO CLICK“) |
| Frage/Antworten zwischen Lesen und Klick verändert | Kein Klick („the visible question changed“) |
| Fenster verschoben / Größe geändert | Kein Klick oder neu lesen |
| Ein anderes Fenster liegt über dem Kästchen | Kein Klick („another window covers the answer“) |
| Kästchen nicht sicher gefunden / Ziel nicht eindeutig | Kein Klick |
| Kästchen-Zustand nicht lesbar | Kein Klick |
| Klick ließ sich nicht verifizieren | Meldung, **keine** Wiederholung (Safe mode) |
| `Strg+Umschalt+X` | Sofort STOPPED, ausstehende Klicks verworfen |

---

## Teil 9 – Logging: wo liegt was?

Drücke `Windows + R`, gib `%APPDATA%\360Smart` ein, Enter:

| Ordner/Datei | Inhalt |
|---|---|
| `logs\360smart.log` | Protokoll der App (ohne API-Keys) |
| `trace\session-….jsonl` | jeder Schritt jeder Frage: OCR → KI-Antwort → Confidence → Bestätigung → Klick/kein Klick + Grund |
| `trace\…-q001-detect.png` usw. | Bilder **nur vom Frage-/Antwortbereich**, mit Kästchen-Rahmen und Klick-Kreuzen |
| `trace\protocol.csv` | Tabelle aller Fragen (Excel) |

Screenshots von dir selbst (`Windows + Umschalt + S`) kannst du einfach mitschicken.

---

## Teil 10 – Diagnose erstellen (bei JEDEM Problem und am Ende)

Eine der drei Möglichkeiten:
* Dashboard → **Diagnostics** → **Create diagnosis (ZIP)**, **oder**
* Tray-Symbol (unten rechts, ggf. `^` klicken) → Rechtsklick → **Create diagnosis (ZIP)**, **oder**
* falls die App gar nicht startet: Startmenü → **360 SMART - Diagnose erstellen**.

✅ **Erwartet:** Auf deinem **Desktop** liegt `360SMART-Diagnose-JJJJMMTT-HHMMSS.zip` (der Ordner öffnet sich).

**Enthalten:** App-Version und Build, Windows-Version, Bildschirmauflösung, DPI/Skalierung, Anzahl Monitore,
erkanntes 360-Fenster und Größe, OCR-Engine, OCR-Ergebnisse, Confidence-Werte, Aufnahme- und Klick-Koordinaten,
letzte Statuswechsel, Fehlermeldungen, Logs, das Fragen-Protokoll.
**Nicht enthalten:** API-Keys, Passwörter, Tokens, Zugangsdaten (wird automatisch entfernt und getestet).

---

## Teil 11 – Was du mir zurückschickst

1. Die **Diagnose-ZIP** vom Ende des 50-Fragen-Tests (und ggf. weitere ZIPs von Problemen).
2. Die ausgefüllte **Checkliste** unten (einfach kopieren und ✅/❌ eintragen).
3. Optional: deine Notizen („Frage 17 falsch …“) und eigene Screenshots.

**Nicht schicken:** deinen API-Key, deine 360-Zugangsdaten.

---

## Checkliste (kopieren und ausfüllen)

```
Windows-Version (Einstellungen → System → Info):
Bildschirm(e) + Skalierung (z. B. 1920x1080, 125 %):
Browser/App für 360° online:
KI-Anbieter:

[ ] 1  Installer gestartet (SmartScreen „Trotzdem ausführen“)
[ ] 2  Installation ohne Fehler, Startmenü-Einträge vorhanden
[ ] 3  Erster Start: Overlay + Dashboard + „DRY RUN“ sichtbar
[ ] 4  Simulator: Frage erkannt, Empfehlung + Confidence angezeigt
[ ] 5  Simulator: rote Kreuze auf den richtigen Kästchen, nichts angeklickt
[ ] 6  Not-Aus (Strg+Umschalt+X) zeigt STOPPED, RESUME geht
[ ] 7  API-Key gespeichert, „Test connection“ grün
[ ] 8  360-Fenster wird gefunden
[ ] 9  Kalibrierung: Kästchen grün
[ ] 10 Fragetext richtig gelesen (bei ___ von 10 Fragen)
[ ] 11 Antworten richtig gelesen (bei ___ von 10 Fragen)
[ ] 12 Dry Run: rote Kreuze genau auf den Kästchen (bei ___ von 10 Fragen)
[ ] 13 Echter Klick: „Selected and verified“
[ ] 14 Niedrige Confidence: kein Klick
[ ] 15 Hotkeys F8/F9/ESC/ENTER funktionieren
[ ] 16 Not-Aus während der Ausführung: danach kein Klick mehr
[ ] 17 Verdecktes Kästchen: kein Klick
[ ] 18 Fenster verschoben: kein Klick an falscher Stelle
[ ] 19 5 Fragen hintereinander ohne Fehler
[ ] 20 50-Fragen-Test durchgeführt, Diagnose-ZIP erstellt
Probleme / Notizen:
```

---

## Wenn etwas schiefgeht

| Problem | Lösung |
|---|---|
| „Looking for the 360° window…“ | Fenster nicht minimieren; Teil 5.1 (Fenstertitel eintragen) |
| „Calibration required“ | Teil 5.2 |
| Umlaute (ä, ö, ü) falsch gelesen | Windows-Einstellungen → *Zeit und Sprache* → *Sprache* → Deutsch → *Optionen* → **Optische Zeichenerkennung** installieren, App neu starten |
| „AI OFFLINE“ | Internet prüfen; Key/Guthaben prüfen (Teil 4) |
| Es wird gar nichts geklickt | Steht oben „DRY RUN“? → Teil 6. Steht eine Meldung „Not clicked: …“? → das ist eine Sicherheitsregel (Teil 8) |
| App reagiert nicht | `Strg+Umschalt+X`, dann Tray → *Quit*; Startmenü → *360 SMART - Diagnose erstellen* |
| Deinstallieren | Windows-Einstellungen → *Apps* → *360 SMART* → *Deinstallieren* (deine Daten in `%APPDATA%\360Smart` bleiben; Ordner kann gelöscht werden) |
