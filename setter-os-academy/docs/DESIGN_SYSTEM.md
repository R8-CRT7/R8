# DESIGN_SYSTEM – „Deep Focus“

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

## 2. Tokens

### Farben (dunkel / hell) – Kontrast gegen `--bg`

| Token | Dunkel | Kontrast | Hell | Kontrast | Verwendung |
|---|---|---|---|---|---|
| `--bg` | #0a0f1e | – | #f6f7fb | – | Seite |
| `--bg-elev` | #111829 | – | #ffffff | – | Eingaben, Chatblasen |
| `--text` | #eef1f7 | ≈ 16:1 | #0f172a | ≈ 17:1 | Fließtext |
| `--text-muted` | #a3adc2 | ≈ 8:1 | #475569 | ≈ 7,5:1 | Sekundärtext |
| `--text-faint` | #7d879c | ≈ 5:1 | #5b6779 | ≈ 5,6:1 | Meta (≥ 4,5:1) |
| `--accent` | #7c9cff | ≈ 7:1 | #3554d1 | ≈ 6,3:1 | Links, Fokus, Primär |
| `--accent-2` | #a78bfa | ≈ 6,4:1 | #6d4bd8 | ≈ 5,9:1 | Violett-Akzent |
| `--success` / `--warning` / `--danger` | #4ade80 / #fbbf24 / #f87171 | ≥ 7:1 | #15803d / #a16207 / #b91c1c | ≥ 4,5:1 | Status |

Kontrastwerte sind gerechnete Näherungen; automatisiert bestätigt durch axe (E2E-Test E11, dunkel + hell, keine serious/critical-Verstöße). Text auf Glas/Verläufen wird von axe teils nur als „incomplete“ gemeldet → manuelle Prüfung offen (TEST_PLAN).

### Typografie (Basis 16 px, Faktor ≈ 1,2)

`xs 12 · sm 14 · base 16 · lg 18 · xl 21,6 · 2xl 26 · 3xl 31 · 4xl 40 · Hero 60 (Desktop)`. Systemschrift-Stack (Inter, falls installiert; sonst SF Pro / Segoe UI / system-ui) – **keine externen Font-Requests** (Datenschutz, Offline-Fähigkeit). Tabellarische Ziffern (`tnum`) für Kennzahlen. Überschriften `tracking-tight`, Eyebrows `uppercase tracking-[0.14em]`.

### Abstände & Radien

4-px-Raster (Tailwind-Skala). Karten-Padding 20 px, Seitenrand mobil 16 px, Desktop 40 px. Radien: `--radius-sm 10` (Buttons, Eingaben), `--radius 16` (Karten), `--radius-lg 22` (Chat, Hero-Flächen).

### Tiefe & Glas

`.glass`: zweistufiger Flächenverlauf, 1 px Rand, innerer Lichtrand, `backdrop-filter: blur(14px) saturate(140%)`. Hintergrund: zwei sehr dezente radiale Akzentverläufe. Primärbutton mit Gradient und weichem Glow – das einzige „leuchtende“ Element.

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
