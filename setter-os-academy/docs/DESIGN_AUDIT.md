# DESIGN_AUDIT – Prüfung der Oberfläche V1 und Entscheidungen für V2

Stand 03.10.2026. Grundlage: Screenshots `docs/screenshots/*.jpg` (Desktop 1440 px, iPhone-13-Viewport), axe-Ergebnisse, eigene Durchsicht aller Kernseiten.

## 1. Befunde V1 „Deep Focus“

| # | Bereich | Befund | Schwere | Entscheidung V2 |
|---|---|---|---|---|
| 1 | Gesamteindruck | Glasflächen, zwei Hintergrundverläufe und Glow-Buttons wirken eher nach Marketing-Seite als nach Lernwerkzeug. | mittel | Opake Flächen, ein Akzent, kein Glow |
| 2 | Kontrast | Text auf halbtransparenten Flächen hängt vom Hintergrund ab; axe meldet teils nur „incomplete“. | hoch | Opake Flächen, alle Textpaare gerechnet ≥ 4,7:1 (Grenze 4,5:1) |
| 3 | Primärbutton | Verlauf Blau→Violett mit weißer Schrift: Kontrast am violetten Ende knapp. | mittel | Volle Kobaltfläche `--accent-solid`, 5,7:1 |
| 4 | Lange Texte | Kursbuch in UI-Schrift 16 px, Initiale in Akzentfarbe – unruhig, ermüdet bei 2 h Lernzeit. | hoch | Serifenschrift Newsreader 18 px, 66 Zeichen, keine Initiale |
| 5 | Schriften | Systemschrift-Stack – je nach Gerät sehr unterschiedlich. | niedrig | Lokale WOFF2 (Jakarta, Newsreader), keine externen Anfragen |
| 6 | Navigation | Sidebar ohne Kursbuch, Fehlergedächtnis, Module. | mittel | Sekundärnavigation ergänzt |
| 7 | Dashboard | Viele gleich gewichtete Karten; „Was mache ich heute?“ nicht sofort klar. | hoch | Oben „Heute“-Karte, dann Aktivität, Challenge, Empfehlungen |
| 8 | Chat mobil | Tastatur verdeckt beim Tippen teils Eingabe und Senden (bekanntes iOS-Verhalten mit `100vh`). | hoch | Chat an `visualViewport` gekoppelt, E2E-Test E20 |
| 9 | Chatblasen | Eigene Blase mit Verlauf; Lesbarkeit hängt von Blasenlänge ab. | niedrig | Volle Fläche `--accent-solid` |
| 10 | Diagramme | Kein Verlauf der eigenen Aktivität sichtbar. | mittel | 14-Tage-Balken mit Tooltip und Tabelle für Screenreader |
| 11 | Hell-Modus | Kaltes Weiß, wirkt klinisch. | niedrig | Warmes Off-White #f5f4ef |

## 2. Was bewusst gleich bleibt

- Dark-first, optional hell, Schalter in den Einstellungen.
- Mobile Tableiste mit fünf Zielen ≥ 44 px (E2E E10).
- Bewegung nur zur Orientierung; `prefers-reduced-motion` und In-App-Schalter.

## 3. Offene Punkte

- Echte iPhone-Prüfung (Safari/WebKit) steht aus; in dieser Umgebung nur Chromium mit iPhone-Viewport.
- Screenreader-Durchlauf (VoiceOver) manuell noch nicht durchgeführt.
