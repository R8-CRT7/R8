# AI_ARCHITECTURE – Freier KI-Kundensimulator und KI-Coach (V3)

Stand: 03.10.2026. Gilt für Version 0.3.0.

## 1. Grundsätze

1. **Keine vorgetäuschte KI.** Wenn keine KI erreichbar ist, sagt die App das und bietet den regelbasierten Offline-Modus an. Es gibt keine eingebauten „KI-Antworten“.
2. **Kein API-Schlüssel im Client.** Der statische Build enthält keine Geheimnisse. Kostenpflichtige Aufrufe laufen nur über einen optionalen, selbst betriebenen Proxy.
3. **Kostenpflichtige Aufrufe sind standardmäßig gesperrt.** Freischalten geht nur ausdrücklich in den Einstellungen und nur mit einem Monatsbudget > 0 €.
4. **Kunde und Coach sind getrennt.** Der Kunde kennt Persona und verdeckte Fakten, aber keine Bewertung. Der Coach sieht nur Transkript, Messwerte und Regeln, aber nie den Kunden-Prompt.
5. **Bestehen entscheidet nicht die KI allein.** Die Prüfungsentscheidung folgt festen Regeln (Gates G1–G6) auf Basis gemessener Werte und *belegter* Coach-Aussagen.

## 2. Bausteine (`src/lib/ai/`)

| Datei | Aufgabe |
|---|---|
| `types.ts` | Rollen (`customer`, `coach`, `hint`), Modellstufe (`quick`/`default`/`complex`), Fehlercodes, Kostenmodell |
| `providers.ts` | `claude-artifact` (Claude über das Konto der Person im claude.ai-Viewer) und `proxy` (eigener Server, optional) |
| `router.ts` | Auswahl je Rolle mit Fallback, Kostenschätzung, Budget- und Sperrprüfung, Ausgaben-Log |
| `customerAI.ts` | Kunden-Prompt (zustandslos, enthält Persona, Fakten mit Freigaberegeln, Verlauf), JSON-Protokoll, Validierung |
| `coachAI.ts` | Coach-Prompt ohne Punktzahlen, Zitat-Prüfung gegen das Transkript, Gates, Hinweise im Lernmodus |
| `metrics.ts` | Deterministische Messwerte (Fragen, offene Fragen, Mehrfachfragen, Länge, Warnsätze) |

### Ablauf eines Gesprächszugs

```
Setter tippt → applySetterMessage (max. 800 Zeichen)
  → buildCustomerPrompt (letzte 24 Nachrichten, ältere als gekürzt markiert)
  → router.complete(role "customer", tier "quick")
  → parseCustomerReply: JSON prüfen, unbekannte Faktenschlüssel verwerfen, Stimmung 0–10 begrenzen
  → applyCustomerReply: Fakten als „preisgegeben“ merken; nach maxTurns+6 Setter-Nachrichten endet das Gespräch
```

Bei einem Fehler (Limit, Abbruch, ungültige Ausgabe) wird die Setter-Nachricht zurückgenommen und bleibt im Eingabefeld – nichts geht verloren.

### Auswertung

1. **Gemessen** (ohne KI): Anzahl Nachrichten, Fragen, offene Fragen, Mehrfachfragen, Wörter, Pflichtkriterien erfragt, Übergabe korrekt, Warnsätze (z. B. „nur heute“, „100 % Garantie“, „Förderung sicher“).
2. **Coach** (KI, Stufe `default`): Einschätzung je Kriterium (stark/solide/ausbaufähig/kritisch/nicht beobachtet) **nur mit wörtlichem Beleg**. `verifyQuote` prüft jeden Beleg gegen die Setter-Nachrichten; unbelegte Aussagen und unbelegte Grenzverletzungen werden verworfen. Ein Kriterium ohne gültigen Beleg wird „nicht beobachtet“. Keine Prozentwerte.
3. **Gates** (nur Prüfungsmodus): G1 Warnsatz oder belegte Grenzverletzung · G2 Termin ohne Pflichtkriterien · G3 Termin, obwohl Nein/Disqualifizierung richtig war · G4 erfundene Angaben in der Übergabe · G5 unzulässiges Ergebnis · G6 ein Kriterium „kritisch“. Ist der Coach nicht erreichbar, gibt es **keine** Prüfungsentscheidung.

## 3. Anbieter und Kosten

| Anbieter | Wann aktiv | Kosten | Datenschutz |
|---|---|---|---|
| **Claude im claude.ai-Viewer** (`sample`-Fähigkeit) | Akademie über den privaten claude.ai-Link geöffnet, Person stimmt beim ersten Aufruf zu | Läuft über das eigene Claude-Abo/-Kontingent, **keine zusätzliche Rechnung** | Inhalte gehen an Anthropic wie bei normaler Claude-Nutzung |
| **Eigener Proxy** (`server/ai-proxy`, nicht bereitgestellt) | Nur wenn `NEXT_PUBLIC_AI_PROXY_URL` gesetzt **und** in den Einstellungen freigeschaltet **und** Budget > 0 € | Pro Token (siehe unten) | Schlüssel nur serverseitig |
| **Offline-Modus** | Immer | 0 € | Keine Übertragung |

### Kostenschätzung bei eigenem Proxy

Annahmen (`router.ts`): 1 Token ≈ 3,5 Zeichen, 1 US-$ = 0,92 €. Preise laut Claude-API-Dokumentation (SRC-196): Opus 5.5 4 $/20 $, Sonnet 5.5 2 $/10 $, Haiku 4.5 1 $/5 $ je Million Ein-/Ausgabe-Token.

Ein typisches Übungsgespräch (12 Setter-Nachrichten, Kunden-Prompt ≈ 2.500–5.000 Token je Zug, Antwort ≈ 120 Token, dazu eine Coach-Auswertung mit ≈ 6.000 Token Eingabe und ≈ 1.500 Token Ausgabe):

| Modell | ca. Kosten je Gespräch |
|---|---|
| Haiku 4.5 | 0,05–0,08 € |
| Sonnet 5.5 | 0,10–0,16 € |
| Opus 5.5 | 0,20–0,32 € |

Das sind Schätzungen; die tatsächlichen Kosten zeigt der Anbieter. Der Router bucht jede Schätzung in ein lokales Ausgaben-Log und blockiert, sobald das Monatsbudget erreicht würde.

## 4. Geprüfte kostenlose Kontingente (Recherche 03.10.2026)

| Anbieter | Kostenlose Stufe | Haken |
|---|---|---|
| Google Gemini API (SRC-190/191) | grob 500–1.500 Anfragen/Tag für Flash-Modelle | Daten können in der kostenlosen Stufe zur Verbesserung genutzt werden |
| Groq (SRC-192) | ca. 30 Anfragen/Minute, 1.000–14.400/Tag je Modell | Offene Modelle; deutsche Rollenspielqualität ungeprüft |
| Mistral „Experiment“ (SRC-193) | kostenlos mit Telefonverifizierung | Daten können zum Training genutzt werden |
| Cloudflare Workers AI (SRC-194) | 10.000 Neurons/Tag | Kleinere Modelle |
| OpenRouter (SRC-195) | ca. 50 Anfragen/Tag für Gratis-Modelle | Wechselnde Modelle |

**Entscheidung:** Der Standardweg ist Claude über den claude.ai-Viewer, weil er ohne Schlüssel, Server und Zusatzkosten auskommt und Deutsch gut beherrscht. Die anderen Anbieter wären nur mit eigenem Proxy nutzbar (der Artifact-Viewer blockiert Aufrufe zu fremden Servern) und nutzen in den Gratisstufen teils die Eingaben. Ein Adapter dafür ist **nicht** gebaut; die Router-Schnittstelle (`AiProvider`) erlaubt es später ohne Umbau.

## 5. Bedrohungen und Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| KI-Kunde gibt alles auf einmal preis | Freigaberegel je Fakt, „BEREITS PREISGEGEBEN“-Liste, unbekannte Schlüssel werden verworfen |
| KI-Kunde arbeitet auf den Termin hin | Regel 4 im Prompt; Nein, Nachfassen und Disqualifizieren als gleichwertige Ausgänge |
| Coach erfindet Belege | Zitat-Prüfung; unbelegte Aussagen werden verworfen (Test C02, E2E E17) |
| Coach würfelt Punktzahlen | Keine Punktzahlen; Bestehen nur über Gates |
| Prompt-Injection durch Setter-Text | Setter-Text ist auf 800 Zeichen begrenzt und steht nur im Verlauf; Ausgabe wird streng validiert; Bestehen hängt nicht an freiem KI-Text |
| Unerwartete Kosten | Kostenpflichtig standardmäßig aus, Budget-Sperre, keine Schlüssel im Client |
| Personenbezogene Daten | Hinweis „nur erfundene Daten“ im Chat; Transkripte nur lokal, löschbar in Einstellungen und Fehlergedächtnis |

## 6. Tests

`tests/ai.test.ts` (28 Fälle A01–H04) und die Browser-Tests E15–E20 mit nachgebildeter Claude-Laufzeit. Die Nachbildung existiert nur in den Tests; die App selbst enthält keine vorgefertigten KI-Antworten.
