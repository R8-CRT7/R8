# TECHNICAL_ARCHITECTURE

Stand 03.10.2026.

## 1. Vorgefundene Umgebung

- Repository `r8-crt7/r8` enthält ein **anderes Projekt** („360 SMART“, Windows/iOS, Python/Swift). Es wurde **nicht verändert**. SETTER OS ACADEMY liegt isoliert in `setter-os-academy/`.
- Node 22.22, npm 10.9, Python 3.11, Chromium 141 (Playwright), PostgreSQL-Client vorhanden; kein Postgres-Server, keine Cloud-Zugänge, keine API-Keys.

## 2. Stack-Entscheidung

| Schicht | Wahl | Version | Begründung | Alternativen |
|---|---|---|---|---|
| UI | React | 19.3 | Standard, große Community | Svelte (kleiner, aber weniger Talent/Ökosystem) |
| Framework | Next.js App Router, **Static Export** | 16.3 | Routing, Bundling, später Server/API möglich; jetzt **kein Server nötig** → 0 € Hosting | Vite + React Router (gleichwertig; Next gewählt wegen späterer SSR/API-Routen für KI-Proxy) |
| Sprache | TypeScript strict + `noUncheckedIndexedAccess` | 5.9 | Inhalte & Engines typgeprüft | – |
| Styling | Tailwind CSS v4 + CSS-Variablen | 4.3 | Tokens zentral, Dark/Light per Attribut | CSS Modules |
| Komponenten | eigene, schlanke Bibliothek | – | volle Kontrolle über A11y & Look, keine Abhängigkeit | shadcn/ui (später möglich, gleiche Token-Idee) |
| Persistenz (jetzt) | `localStorage`, versioniertes Schema + Migrationen | – | kein Konto, keine Kosten, DSGVO-arm | IndexedDB (bei > 5 MB) |
| Datenbank (später) | PostgreSQL (Supabase) | ≥ 15 | Auth, RLS, Free Tier zum Testen | Neon + eigenes Auth |
| Tests | Vitest 5, Playwright 1.56, axe-core, PGlite (Postgres in WASM) | – | Schema gegen echtes Postgres testen ohne Server | – |

**Free-Tier-Hinweise (Sekundärquellen, vor Nutzung auf Originalseite prüfen):** Supabase Free: 2 Projekte, 500 MB DB, **Pausierung nach 1 Woche Inaktivität**. Vercel Hobby: **nur nicht-kommerziell** – für einen späteren Verkauf ungeeignet. Für den Static Export genügt jeder statische Host (z. B. GitHub Pages, Cloudflare Pages); Bedingungen vor Nutzung prüfen. **Es wurde nichts veröffentlicht oder eingerichtet.**

## 3. Modulgrenzen

```
content/                 Lerninhalte (JSON) – Quelle der Wahrheit, versioniert
  sources.json knowledge.json curriculum.json modules/ questions/ scenarios/
  program.json (Tag 1–90) longterm.json (Tag 91–180, 18 Spezialisierungen)
  concepts.json (Konzeptgraph) glossary.json
src/lib/
  ai/                    KI-Schicht: Anbieter, Router, KI-Kunde, KI-Coach, Messwerte
  engine/competency.ts   Kompetenzbaum (Konzeptstufe = schwächstes Lernziel)
  engine/errorMemory.ts  Fehlergedächtnis (Klassen, Trend, Übungsempfehlung)
  engine/challenges.ts   Wochen-Challenges, Missionen, Kompetenz-Abzeichen
  engine/recommend.ts    Empfehlungen aus Fehlern, fälligen Wiederholungen, schwachen Zielen
  types.ts               Domänentypen (Inhalte, Antworten, Simulation, Bewertung)
  content/               Laden + Validieren der Inhalte (CI-Gate)
  engine/quiz.ts         Quiz-Engine (12 Typen inkl. Fallanalyse, deterministisch)
  engine/review.ts       Wiederholungs- & Kompetenzalgorithmus
  engine/customer.ts     Customer Simulator (kennt Fakten, nie Bewertung)
  engine/coach.ts        Sales Coach / Bewertungs-Engine (kennt Rubrik, nie Antworten des Kunden)
  engine/gamification.ts XP, Level, Erfolge
  store/state.ts         Lernfortschritt (reine Zustandsübergänge, Migrationen)
  store/storage.ts       Persistenzadapter (localStorage → später Supabase)
  derived.ts             abgeleitete Sichten (Statistik, Fehleranalyse)
  masterExam.ts          Master-Prüfung (Spezifikation)
src/components/          Designsystem + QuestionRenderer + AppShell
src/app/                 Ansichten (Landing, Start, Login, (app)/…)
db/schema.sql            Ziel-Datenbankschema (getestet mit PGlite)
server/ai-proxy/         Optionaler KI-Proxy (nicht bereitgestellt, eigenes package.json)
tests/ e2e/              Unit-/Regressions-/Schema-Tests, E2E inkl. iPhone & a11y
```

Trennung laut Brief: Frontend (`src/app`, `src/components`) · Backend (noch keins; Engines sind reine Funktionen und laufen später unverändert serverseitig) · Authentifizierung (lokales Profil; später Supabase Auth) · Datenbank (`db/`) · Lerninhalte (`content/`) · Quiz-, Simulations-, Bewertungs-Engine (`engine/`) · Lernfortschritt (`store/`) · Admin (`app/(app)/admin`) · Quellenverwaltung (`content/sources.json` + Generator) · Zahlung (**bewusst nicht vorhanden**).

## 4. Sicherheit

- Keine Geheimnisse im Code; `.env.example` dokumentiert spätere Variablen, `.env*` ist ignoriert.
- Kein Server, keine Cookies, keine Drittanbieter-Requests (Fonts lokal/System). `robots: noindex`.
- Import von Sicherungen wird über `migrate()` normalisiert (unbekannte Felder werden verworfen, Müll → Neustart).
- Externe Links mit `rel="noreferrer noopener"`.
- Adminbereich im Prototyp ohne Rollenprüfung (lokal, nur eigene Daten). **Vor Cloud-Betrieb Pflicht:** Supabase RLS-Policies je Rolle, serverseitige Bewertung von Prüfungen (Client-Bewertung ist manipulierbar → für Zertifikate unzulässig).

## 5. KI-Integration (aktiv seit 0.3.0)

- Vollständige Beschreibung: **docs/AI_ARCHITECTURE.md**.
- Standard: Claude über die `sample`-Fähigkeit des claude.ai-Viewers (Konto der Person, kein Schlüssel, keine Zusatzrechnung). Der veröffentlichte Artifact deklariert dafür `capabilities: {sample: {}}`.
- Optional: eigener Proxy `server/ai-proxy` (Cloudflare-Worker-Vorlage, `@anthropic-ai/sdk`, Modell `claude-opus-5-5` mit serverseitigem Fallback). **Nicht bereitgestellt**; kostenpflichtig nur nach ausdrücklicher Freigabe und mit Budget.
- Ohne KI läuft der deterministische Simulator vollständig (Offline-Modus mit Antwortauswahl).
- Kunde und Coach getrennt; Bestehen nur über deterministische Gates; Coach-Belege werden gegen das Transkript geprüft. Kennzeichnung als KI im Chat (Art. 50 KI-VO).

## 6. Internationalisierung

`LocalizedText`-Typ und `profile.locale` (`de|en|es`) sind vorbereitet; Inhalte liegen derzeit nur auf Deutsch vor. Geplanter Weg: Inhaltsdateien je Sprache (`content/en/...`) mit identischen IDs, damit Fortschritt sprachunabhängig bleibt.

## 7. Befehle

Siehe README.md §Schnellstart.
