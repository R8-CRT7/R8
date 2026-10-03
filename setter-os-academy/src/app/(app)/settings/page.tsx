"use client";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Button, Card, PageHeader } from "@/components/ui";
import type { Settings } from "@/lib/store/state";
import { exportJson, importJson, resetAll, update, useAcademy } from "@/lib/store/storage";

export default function SettingsPage() {
  const s = useAcademy();
  const router = useRouter();
  const file = useRef<HTMLInputElement>(null);
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
          <div className="mt-4 flex flex-wrap gap-2">
            <Button variant="secondary" onClick={download}>Daten exportieren (JSON)</Button>
            <Button variant="secondary" onClick={() => file.current?.click()}>Sicherung importieren</Button>
            <input ref={file} type="file" accept="application/json" className="hidden" onChange={async (e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              try { importJson(await f.text()); setMsg("Sicherung importiert."); } catch { setMsg("Import fehlgeschlagen – Datei ungültig."); }
            }} />
          </div>
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
