"use client";
import Link from "next/link";
import { useState } from "react";
import { Badge, Button, Card, PageHeader } from "@/components/ui";
import { lessonById, scenarioById } from "@/lib/content";
import { MISTAKE_PRACTICE, mistakeEvents, mistakeSummary } from "@/lib/engine/errorMemory";
import { recommendations } from "@/lib/engine/recommend";
import { deleteErrorMemory } from "@/lib/store/state";
import { update, useAcademy } from "@/lib/store/storage";

export default function Mistakes() {
  const s = useAcademy();
  const now = Date.now();
  const sum = mistakeSummary(s, now);
  const recs = recommendations(s, now, 5);
  const [confirm, setConfirm] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div className="page-enter">
      <PageHeader eyebrow="Persönliches Fehlergedächtnis" title="Was dir wiederholt passiert">
        Aus Quizantworten, Offline-Simulationen und KI-Coach-Auswertungen. Daraus entstehen gezielte Übungsvorschläge. Die Daten liegen nur auf diesem Gerät.
      </PageHeader>
      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <div className="grid content-start gap-3">
          {sum.length === 0 && <Card><p className="text-sm text-muted">Noch keine Fehler gespeichert. Sie erscheinen hier, sobald du übst.</p></Card>}
          {sum.map((m) => (
            <Card key={m.cls}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-semibold">{m.label}</h2>
                <div className="flex gap-1.5"><Badge>{m.total} gesamt</Badge><Badge tone={m.trend === "besser" ? "success" : m.trend === "häufiger" ? "warning" : "neutral"}>{m.recent} in 14 Tagen · {m.trend}</Badge></div>
              </div>
              <ul className="mt-2 grid gap-1 text-xs text-muted">{m.examples.map((e, i) => <li key={i}>{new Date(e.at).toLocaleDateString("de-DE")} · {e.source === "quiz" ? "Quiz" : e.source === "ki-coach" ? "KI-Coach" : "Simulation"} · {e.detail}</li>)}</ul>
              <div className="mt-3 flex flex-wrap gap-2 text-sm">
                {MISTAKE_PRACTICE[m.cls].lessons.map((l) => { const x = lessonById(l); return x ? <Link key={l} href={`/learn/${x.moduleId}/${l}/`} className="rounded-full border border-line px-3 py-1 text-accent hover:border-accent/60">{x.title}</Link> : null; })}
                {MISTAKE_PRACTICE[m.cls].scenarios.map((id) => <Link key={id} href={`/simulator/${id}/`} className="rounded-full border border-line px-3 py-1 text-accent hover:border-accent/60">Üben: {scenarioById(id)?.title}</Link>)}
              </div>
            </Card>
          ))}
        </div>
        <aside className="grid content-start gap-4">
          <Card>
            <h2 className="mb-2 font-semibold">Empfohlen für dich</h2>
            {recs.length === 0 ? <p className="text-sm text-muted">Gerade nichts – mach im Plan weiter.</p> : (
              <ul className="grid gap-2">{recs.map((r) => <li key={r.href}><Link href={r.href} className="block rounded-[var(--radius-sm)] border border-line p-3 text-sm hover:border-line-strong"><span className="font-medium">{r.title}</span><span className="block text-xs text-faint">{r.reason}</span></Link></li>)}</ul>
            )}
          </Card>
          <Card>
            <h2 className="mb-2 font-semibold">Deine Daten</h2>
            <p className="text-sm text-muted">{mistakeEvents(s).length} gespeicherte Fehlereinträge.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button variant="secondary" onClick={async () => { try { await navigator.clipboard.writeText(JSON.stringify(mistakeEvents(s), null, 2)); setMsg("Fehlergedächtnis als JSON kopiert."); } catch { setMsg("Kopieren nicht möglich."); } }}>Exportieren (kopieren)</Button>
              {!confirm ? <Button variant="danger" onClick={() => setConfirm(true)}>Löschen …</Button> : (
                <>
                  <Button variant="danger" onClick={() => { update(deleteErrorMemory); setConfirm(false); setMsg("Fehlergedächtnis gelöscht. Lernfortschritt bleibt erhalten."); }}>Ja, löschen</Button>
                  <Button variant="ghost" onClick={() => setConfirm(false)}>Abbrechen</Button>
                </>
              )}
            </div>
            {msg && <p role="status" className="mt-2 text-sm">{msg}</p>}
          </Card>
        </aside>
      </div>
    </div>
  );
}
