# Golden External – unabhängige Theoriefragen (nur Auswertung)

Hier kommen Fragen hinein, die **nicht** von diesem Projekt bzw. der KI geschrieben wurden – z. B. von Emilio
selbst formuliert oder aus einer unabhängigen Quelle, die das erlaubt. **Keine** kopierten amtlichen oder
kommerziellen Prüfungsfragen.

Regeln (technisch durch Tests erzwungen, `tests/theory/test_holdout.py`):
* Nur `smart360/theory/splits.py` liest dieses Verzeichnis, und nur mit `purpose="evaluation"`
  (`python windows/tools/theory_eval.py --set golden_external`).
* Die Fragen dürfen nicht in Claims, Synonym-/Lexikon-Einträge, OCR-Vokabular, Prompts oder Generator gelangen
  (Nahe-Duplikat-Prüfung gegen die Wissensbasis).
* Fehler auf diesen Fragen werden als Fehlerklasse analysiert, nie durch Anpassen an die Frage behoben.

## Import (nie von Hand hineinkopieren)

```
python windows/tools/external_import.py neue_fragen.json --dry-run   # nur prüfen
python windows/tools/external_import.py neue_fragen.json             # prüfen + importieren
```
Der Importer prüft:
* Format: Topic, Frage, Antworten, `correct`, Quelle, **Autor**
* eindeutige IDs
* Duplikate, auch gegen frühere Importe
* **Leakage**: lexikalische und normalisierte semantische Ähnlichkeit gegen Claims, Generator, Development
  Golden, Lexikon und Prompts (`smart360/theory/leakage.py`)

Zu ähnliche Fragen werden als `POSSIBLE_LEAKAGE` markiert und **nicht** in die unabhängige Hauptmetrik
aufgenommen. Importierte Dateien werden nie wieder verändert: Ihr SHA-256 steht in `MANIFEST.json`, und die
Auswertung bricht ab, wenn eine Datei verändert wurde. Die **erste** Messung wird einmalig in
`reports/external_first_measurement.json` eingefroren.

Format: eine oder mehrere `*.json`-Dateien, jeweils
```json
{"items": [
  {"id": "EXT-0001", "topic": "05_priority",
   "question": "…", "answers": ["…", "…", "…"], "correct": [1, 3],
   "source": "external-human-authored", "author": "Emilio", "notes": ""}
]}
```
* `correct`: 1-basierte Indizes der richtigen Antworten (Mehrfachauswahl möglich).
* Zahlenfragen: `"answers": []`, `"correct": []`, `"number": "88"`.
* `topic`: einer der 14 Themenschlüssel (`01_personal` … `14_trailers`).
* `source` muss mit `external-` beginnen, `author` darf nicht leer sein.

Aktueller Stand: **leer** – es liegen noch keine extern erstellten Fragen vor.
