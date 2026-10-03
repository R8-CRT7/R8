# DESIGN_SYSTEM – „Midnight Editorial“ (V2)

> V1 „Deep Focus“ (Glas, Verläufe) wurde mit 0.3.0 nach einem Audit abgelöst; die Konzeptwahl in §1 ist historisch.

Stand 03.10.2026 · Implementierung: `src/app/globals.css` (Tokens), `src/components/ui.tsx` (Komponenten), `src/components/AppShell.tsx` (Layout). Referenz-Screenshots: `docs/screenshots/*.jpg` (Desktop 1440 px und iPhone-13-Viewport).

## 1. Drei Konzepte im Vergleich

| | A „Deep Focus“ (gewählt) | B „Console“ | C „Paper Calm“ |
|---|---|---|---|
| Idee | Tiefes Navy, Glasflächen, Blau→Violett-Akzent, viel Luft | Terminal/HUD-Ästhetik, Monospace, Neon-Linien | Hell, papierartig, Serifen-Headlines |
| Wirkung | Premium-SaaS, ruhig-futuristisch | Technisch, „Hacker“, eher laut | Seriös, akademisch, wenig „Produkt“ |
| Lesbarkeit langer Lektionen | gut (Off-White auf Navy 16:1, Zeilenhöhe 1,7) | schwach (Monospace, Glow) | sehr gut |
| Chat-Simulator | sehr gut (klare Blasen, Gradient = „ich“) | mittel | gut |
| Brief-Konformität (Dark-first, kein Neon) | ✔ | ✘ Neon | ✘ nicht Dark-first |
| Risiko | Glas-Effekte kosten Kontrast → Tokens geprüft | Barrierefreiheit | Wenig Differenzierung |

**Entscheidung:** A, mit optionalem Light Mode, der die Lesbarkeit von C übernimmt.

## 2. Tokens (V2 „Midnight Editorial“, seit 0.3.0)

Ergebnis des Design-Audits (docs/DESIGN_AUDIT.md): weniger Glas und Verlauf, mehr Ruhe und Lesbarkeit. Navy-Mitternacht und Anthrazit als Flächen, warmes Off-White als Text, zurückhaltendes Kobalt als einziger Akzent, Violett nur für das Kursbuch.

### Farben (dunkel / hell) – Kontrast gegen `--bg`, gerechnet nach WCAG 2.2

| Token | Dunkel | Kontrast | Hell | Kontrast | Verwendung |
|---|---|---|---|---|---|
| `--bg` | #0a0e1a | – | #f5f4ef | – | Seite |
| `--bg-elev` / `--surface` / `--surface-strong` | #131826 / #151a28 / #1b2232 | – | #ffffff / #ffffff / #eceae3 | – | Eingaben, Karten, Hervorhebung |
| `--text` | #ecebe6 | ≈ 16:1 | #141824 | ≈ 16:1 | Fließtext |
| `--text-muted` | #a7acb8 | ≈ 8,5:1 | #4a5160 | ≈ 7,2:1 | Sekundärtext |
| `--text-faint` | #868c99 | ≈ 5,7:1 | #5e6574 | ≈ 5,3:1 | Meta (≥ 4,5:1) |
| `--accent` | #8ea4ff | ≈ 8,2:1 | #2f4fc4 | ≈ 6,3:1 | Links, Fokus |
| `--accent-solid` + `--accent-ink` | #3b5bdb + #fff | ≈ 5,7:1 (Text auf Fläche) | #3451c7 + #fff | ≈ 6,7:1 | Primärbutton, eigene Chatblasen |
| `--accent-2` | #b3a3f5 | ≈ 8,7:1 | #5d43c4 | ≈ 6,2:1 | Kursbuch-Eyebrows, Hinweise |
| `--success` / `--warning` / `--danger` | #5fd38d / #e8b54a / #f08a8a | ≥ 8:1 | #17793f / #8a5a00 / #b42323 | ≥ 5,0:1 | Status, immer mit Text/Symbol |

Alle Paare gegen `--bg` ≥ 5,0:1; `--text-faint` auf `--surface-strong` ist mit 4,7:1 (dunkel) bzw. 4,9:1 (hell) knapp über der Grenze von 4,5:1. Bestätigt durch axe in E2E-Test E11 (dunkel und hell, keine serious/critical-Verstöße auf Kernseiten).

### Typografie

- **Plus Jakarta Sans** (variabel) für Oberfläche und Überschriften, **Newsreader** (variabel, Serife) für Kursbuch-Texte (`.reader-text`: 18 px, Zeilenhöhe 1,75, max. 66 Zeichen).
- Beide Schriften liegen als WOFF2 im Projekt (`src/fonts/`, SIL Open Font License) und werden **lokal** ausgeliefert – keine Anfragen an Google (vgl. LG München I, 3 O 17493/20, SRC-197).
- Skala (Basis 16 px): `xs 12 · sm 14 · base 16 · lg 18 · xl 20 · 2xl 24 · 3xl 30 · 4xl 36`. Überschriften mit `text-wrap: balance`, Ziffern tabellarisch.

### Abstände & Radien

4-px-Raster. Karten-Padding 20 px, Seitenrand mobil 16 px, Desktop 40 px. Radien: `--radius-sm 10`, `--radius 16`, `--radius-lg 22`.

### Flächen statt Glas

`.glass` ist seit V2 eine **opake** Fläche mit 1-px-Rand und sehr leichtem Schatten. Nur Kopfzeile und Tab-Leiste (`.glass-nav`) behalten eine leichte Unschärfe, damit Inhalte beim Scrollen erkennbar bleiben. Keine Leuchteffekte mehr.

### Tastatur auf dem iPhone

Der KI-Chat liegt mobil als feste Fläche über dem *sichtbaren* Viewport (`visualViewport.height` und `offsetTop` → CSS-Variablen `--chat-h`, `--chat-top`). Öffnet sich die Tastatur, schrumpft die Fläche mit; Eingabefeld, Senden und Zurück bleiben sichtbar (E2E-Test E20).

### Bewegung

`--dur 180ms`, `--ease cubic-bezier(.2,.8,.2,1)`. Eingesetzt nur für: Einblenden (fade-in 260 ms), Fortschrittsbalken, Tipp-Indikator im Chat. `prefers-reduced-motion` **und** In-App-Schalter setzen alle Dauern auf ~0 und den Chat-Tippverzug auf 0.

## 3. Komponenten

| Komponente | Zustände | A11y |
|---|---|---|
| `Button` (primary/secondary/ghost/danger) | hover, active, focus-visible, disabled | min. 44 px Höhe |
| `ButtonLink` | wie Button | echtes `<a>` |
| `Card` | – | `<section>` |
| `Badge` (5 Töne) | – | Text, nicht nur Farbe |
| `ProgressBar` | – | `role=progressbar` + Werte |
| `Ring` | – | `role=img` + Label |
| `Callout` (info/warn/legal/ethics) | – | Icon + Titel, nicht nur Farbe |
| `Stat`, `PageHeader`, `Icon` (eigene SVGs) | – | Icons `aria-hidden` |
| `QuestionRenderer` (11 Typen) | ungewählt, gewählt, richtig, falsch, verpasst, gesperrt | native Radio/Checkbox/Select, Reihenfolge mit ↑/↓-Buttons statt Drag&Drop, Feedback `aria-live` |
| Chat-Simulator | Briefing, Gespräch, tippt…, Übergabe, Ergebnis | Verlauf als Liste `aria-live`, Sprecher als `sr-only` |
| AppShell | Sidebar (≥ 1024 px), Topbar + Bottom-Tabbar (mobil, Safe-Area) | Skip-Link, `aria-current` |

## 4. Responsive & Mobile First

- Breakpoints Tailwind (`sm 640`, `md 768`, `lg 1024`, `xl 1280`). Desktop nutzt Sidebar und zusätzliche Analyseflächen (Statistik-Tabelle, Notizen-Spalte im Simulator).
- iPhone: Bottom-Tabbar mit 5 Zielen (≥ 48 px Höhe, E2E E10), Overflow-Menü für Sekundärbereiche, `viewport-fit=cover`, `env(safe-area-inset-bottom)`.
- Chat-Simulator mobil: feste Höhe, **nur der Verlauf scrollt**, Antwortoptionen bleiben sichtbar; Eingabefelder 16 px (verhindert iOS-Zoom).
- Kein horizontales Scrollen auf Kernseiten (E2E E09, Desktop + iPhone).

## 5. Barrierefreiheit (Ziel WCAG 2.2 AA)

Fokusring 2 px `--focus` · Skip-Link · semantische Überschriften · Formular-Labels · Fehlermeldungen `role=alert` · Status `role=status` · Farbe nie alleiniger Informationsträger · Zielgrößen ≥ 44 px (2.5.8) · Tastaturbedienung (E12) · Reduced Motion.
**Ungeprüft:** Screenreader-Durchlauf mit VoiceOver/TalkBack, Zoom 200 %/400 %, Hochkontrastmodus.
