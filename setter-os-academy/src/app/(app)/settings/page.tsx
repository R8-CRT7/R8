"use client";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Button, Card, PageHeader } from "@/components/ui";
import { deleteAiTranscripts, type Settings } from "@/lib/store/state";
import { monthSpend, PRICE_TABLE } from "@/lib/ai/router";
import { useAiRouter } from "@/components/ai/useAi";
import { exportJson, hasSafetyCopy, importJson, resetAll, restoreSafetyCopy, update, useAcademy } from "@/lib/store/storage";
import { checkBackup, type BackupCheck } from "@/lib/store/state";

// In the claude.ai artifact viewer file downloads are blocked → offer clipboard backup instead.
const IS_ARTIFACT = process.env.NEXT_PUBLIC_ARTIFACT === "1";

export default function SettingsPage() {
  const s = useAcademy();
  const router = useRouter();
  const [confirm, setConfirm] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const set = (patch: Partial<Settings>) => update((st) => ({ ...st, settings: { ...st.settings, ...patch } }));

  function download() {
    const blob = new Blob([exportJson()], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `setter-os-sicherung-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div className="fade-in max-w-3xl">
      <PageHeader eyebrow="Einstellungen" title="Darstellung, Lernpause & Daten" />
      <div className="grid gap-4">
        <Card>
          <h2 className="mb-3 font-semibold">Darstellung</h2>
          <fieldset className="grid gap-2">
            <legend className="mb-2 text-sm text-muted">Farbschema</legend>
            <div className="grid grid-cols-3 gap-2">
              {(["dark", "light", "system"] as const).map((t) => (
                <button key={t} aria-pressed={s.settings.theme === t} onClick={() => set({ theme: t })} className={`min-h-12 rounded-[var(--radius-sm)] border text-sm ${s.settings.theme === t ? "border-accent bg-accent/10" : "border-line text-muted"}`}>
                  {t === "dark" ? "Dunkel" : t === "light" ? "Hell" : "System"}
                </button>
              ))}
            </div>
          </fieldset>
          <label className="mt-4 flex min-h-12 items-center justify-between gap-3 text-sm">
            <span>Animationen reduzieren <span className="block text-xs text-faint">Systemeinstellung wird immer beachtet.</span></span>
            <input type="checkbox" className="h-6 w-6 accent-[var(--accent)]" checked={s.settings.motion === "reduce"} onChange={(e) => set({ motion: e.target.checked ? "reduce" : "system" })} />
          </label>
        </Card>
        <AiSettings />
        <Card>
          <h2 className="mb-1 font-semibold">Lernpause</h2>
          <label className="flex min-h-12 items-center justify-between gap-3 text-sm text-muted">
            <span>Pausieren – keine Hinweise auf fällige Wiederholungen. Erworbene Fortschritte und Erfolge bleiben vollständig erhalten.</span>
            <input type="checkbox" className="h-6 w-6 accent-[var(--accent)]" checked={s.settings.pauseMode} onChange={(e) => set({ pauseMode: e.target.checked })} />
          </label>
        </Card>
        <Card>
          <h2 className="mb-1 font-semibold">Deine Daten</h2>
          <p className="text-sm text-muted">Alles liegt nur in diesem Browser (localStorage). Es gibt keine Übertragung an Server, keine Cookies, kein Tracking.</p>
          <BackupPanel onMsg={setMsg} onDownload={download} />
          {msg && <p role="status" className="mt-2 text-sm">{msg}</p>}
          <div className="mt-6 rounded-[var(--radius-sm)] border border-danger/40 p-4">
            <h3 className="text-sm font-semibold text-danger">Alle Daten löschen</h3>
            <p className="mt-1 text-sm text-muted">Löscht Profil, Fortschritt, Antworten und Simulationen unwiderruflich von diesem Gerät.</p>
            {!confirm ? (
              <Button variant="danger" className="mt-3" onClick={() => setConfirm(true)}>Löschen …</Button>
            ) : (
              <div className="mt-3 flex flex-wrap gap-2">
                <Button variant="danger" onClick={() => { resetAll(); router.push("/"); }}>Ja, endgültig löschen</Button>
                <Button variant="ghost" onClick={() => setConfirm(false)}>Abbrechen</Button>
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function AiSettings() {
  const s = useAcademy();
  const ai = useAiRouter();
  const [budget, setBudget] = useState(String(s.ai.monthlyBudgetEur));
  const spent = monthSpend(s.ai.spendLog, Date.now());
  const calls = s.ai.spendLog.length;
  return (
    <Card>
      <h2 className="mb-1 font-semibold">KI & Kosten</h2>
      <p className="text-sm text-muted">
        Aktiver Anbieter: <span className="text-fg">{ai.providerLabel ?? (ai.status === "checking" ? "wird geprüft …" : "keiner verfügbar")}</span>.
        {ai.costKind === "claude-plan" && " Nutzt dein Claude-Kontingent im claude.ai-Viewer – kein API-Schlüssel, keine separate Rechnung."}
      </p>
      <p className="mt-2 text-xs text-faint">Bisher {calls} KI-Aufrufe protokolliert · geschätzte kostenpflichtige Ausgaben diesen Monat: {spent.toFixed(2)} €.</p>
      <div className="mt-4 rounded-[var(--radius-sm)] border border-line p-3">
        <p className="text-sm font-medium">Kostenpflichtige KI (optionaler eigener Proxy)</p>
        <p className="mt-1 text-xs text-faint">Standardmäßig gesperrt. Funktioniert nur in einer selbst gehosteten Version mit eingerichtetem Proxy. Listenpreise (USD je 1 Mio. Token): {Object.entries(PRICE_TABLE).map(([m, p]) => `${m} ${p.inputPerMTok}/${p.outputPerMTok}`).join(" · ")}.</p>
        <label className="mt-3 flex min-h-11 items-center justify-between gap-3 text-sm">
          <span>Kostenpflichtige Aufrufe erlauben</span>
          <input type="checkbox" className="h-6 w-6 accent-[var(--accent-solid)]" checked={s.ai.paidCallsEnabled} onChange={(e) => update((x) => ({ ...x, ai: { ...x.ai, paidCallsEnabled: e.target.checked } }))} />
        </label>
        <label className="mt-2 grid gap-1 text-sm">
          Monatsbudget in € (0 = gesperrt)
          <input inputMode="decimal" value={budget} onChange={(e) => setBudget(e.target.value)} onBlur={() => { const n = Math.max(0, Number(budget.replace(",", ".")) || 0); setBudget(String(n)); update((x) => ({ ...x, ai: { ...x.ai, monthlyBudgetEur: n } })); }} className="min-h-11 max-w-[160px] rounded-[var(--radius-sm)] border border-line bg-bg px-3" />
        </label>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted">{s.aiSimulations.length} gespeicherte KI-Gespräche</span>
        <Button variant="danger" className="min-h-10" disabled={!s.aiSimulations.length} onClick={() => update(deleteAiTranscripts)}>KI-Gespräche löschen</Button>
      </div>
    </Card>
  );
}

function BackupPanel({ onMsg, onDownload }: { onMsg: (m: string) => void; onDownload: () => void }) {
  const file = useRef<HTMLInputElement>(null);
  const [showExport, setShowExport] = useState(false);
  const [text, setText] = useState("");
  const [check, setCheck] = useState<BackupCheck | null>(null);
  const [undo, setUndo] = useState(() => hasSafetyCopy());
  const prepare = (t: string) => {
    setText(t);
    setCheck(t.trim() ? checkBackup(t) : null);
  };
  return (
    <div className="mt-4 grid gap-4">
      <div>
        <p className="mb-2 text-sm font-medium">Sichern</p>
        <div className="flex flex-wrap gap-2">
          {!IS_ARTIFACT && <Button variant="secondary" onClick={onDownload}>Als Datei exportieren</Button>}
          <Button variant="secondary" onClick={async () => {
            try { await navigator.clipboard.writeText(exportJson()); onMsg("Sicherung in die Zwischenablage kopiert – z. B. in Notizen einfügen."); }
            catch { setShowExport(true); onMsg("Kopieren war nicht möglich. Markiere den Text unten und kopiere ihn von Hand."); }
          }}>Sicherung kopieren</Button>
          <Button variant="ghost" onClick={() => setShowExport((x) => !x)}>{showExport ? "Text ausblenden" : "Als Text anzeigen"}</Button>
        </div>
        {showExport && (
          <textarea readOnly aria-label="Sicherung als Text" value={exportJson()} onFocus={(e) => e.currentTarget.select()} rows={6} className="mt-2 w-full rounded-[var(--radius-sm)] border border-line bg-elev p-3 font-mono text-xs" />
        )}
      </div>
      <div>
        <p className="mb-2 text-sm font-medium">Wiederherstellen</p>
        <p className="mb-2 text-xs text-faint">Die Sicherung wird zuerst geprüft. Dein aktueller Stand wird erst ersetzt, wenn du bestätigst – und vorher als Sicherheitskopie aufbewahrt.</p>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => file.current?.click()}>Datei wählen</Button>
          <input ref={file} type="file" accept="application/json,.json,.txt" className="hidden" onChange={async (e) => {
            const f = e.target.files?.[0];
            if (f) prepare(await f.text());
            e.target.value = "";
          }} />
        </div>
        <textarea aria-label="Sicherung einfügen" value={text} onChange={(e) => prepare(e.target.value)} rows={4} placeholder="… oder Sicherungstext hier einfügen" className="mt-2 w-full rounded-[var(--radius-sm)] border border-line bg-elev p-3 font-mono text-xs" />
        {check && (
          <div role="status" className={`mt-2 rounded-[var(--radius-sm)] border p-3 text-sm ${check.ok ? "border-success/40" : "border-danger/40"}`}>
            {check.ok ? (
              <>
                <p className="font-medium text-success">Sicherung gültig</p>
                <p className="text-muted">Profil „{check.summary.name}“ · {check.summary.lessons} Lektionen · {check.summary.answers} Antworten · {check.summary.simulations} Gespräche · Version {check.summary.schemaVersion}</p>
                <Button className="mt-2" onClick={() => {
                  try { importJson(text); onMsg("Sicherung importiert. Dein vorheriger Stand liegt als Sicherheitskopie bereit."); setText(""); setCheck(null); setUndo(true); }
                  catch (err) { onMsg(`Import abgebrochen – nichts wurde verändert. ${(err as Error).message}`); }
                }}>Diesen Stand übernehmen</Button>
              </>
            ) : (
              <>
                <p className="font-medium text-danger">Nicht importierbar – dein Stand bleibt unverändert</p>
                <ul className="text-muted">{check.problems.map((p) => <li key={p}>• {p}</li>)}</ul>
              </>
            )}
          </div>
        )}
        {undo && (
          <Button variant="ghost" className="mt-2" onClick={() => onMsg(restoreSafetyCopy() ? "Sicherheitskopie wiederhergestellt (der ersetzte Stand ist nun die neue Sicherheitskopie)." : "Keine gültige Sicherheitskopie vorhanden.")}>Letzten Import rückgängig machen</Button>
        )}
      </div>
    </div>
  );
}
