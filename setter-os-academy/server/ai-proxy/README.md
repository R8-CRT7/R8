# Optionaler KI-Proxy (nicht aktiv, nicht deployt)

**Standard: aus.** Die Akademie nutzt im claude.ai-Viewer Claude über dein eigenes Claude-Konto (`sample`-Capability) – ohne API-Schlüssel und ohne separate Rechnung. Dieser Proxy ist nur für einen späteren selbst gehosteten Betrieb gedacht und verursacht **API-Kosten** (Claude Opus 5.5: 4 $ / 20 $ pro 1 Mio. Input-/Output-Token, Stand 2026-09-25).

Voraussetzungen vor Aktivierung (alle nötig):
1. Ausdrückliche Freigabe des Gründers.
2. API-Schlüssel als Secret im Hosting (nie im Code, nie im Frontend).
3. `ALLOWED_ORIGIN` = Domain der selbst gehosteten App, `DAILY_REQUEST_LIMIT` setzen, optional KV-Zähler.
4. App mit `NEXT_PUBLIC_AI_PROXY_URL` bauen; in der App unter Einstellungen „Kostenpflichtige KI erlauben“ + Monatsbudget > 0 setzen.

Kostenschutz: Rollenbezogene `max_tokens` (Kunde 600, Hinweis 300, Coach 4000), Prompt-Obergrenze 60.000 Zeichen, Tageslimit (402), clientseitiges Monatsbudget mit Kostenschätzung, Herkunftsprüfung.
Hinweis: Der claude.ai-Viewer blockiert Anfragen an fremde Server – dieser Proxy funktioniert nur in einer selbst gehosteten Version.
