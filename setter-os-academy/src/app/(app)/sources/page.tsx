"use client";
import { useMemo, useState } from "react";
import { Badge, Card, PageHeader } from "@/components/ui";
import { knowledge, sources } from "@/lib/content";

const EV: Record<string, string> = { gesetz: "Gesetz", rechtsprechung: "Rechtsprechung", behoerde: "Behörde", peer_review: "Peer Review", fachliteratur: "Fachliteratur", hersteller: "Hersteller", fachpresse: "Fachpresse", expertenmeinung: "Expertenmeinung", annahme: "Annahme" };

export default function Sources() {
  const [q, setQ] = useState("");
  const [tab, setTab] = useState<"sources" | "kb">("sources");
  const now = Date.parse("2026-10-03");
  const list = useMemo(() => sources.filter((s) => (s.title + s.authorOrPublisher + s.id).toLowerCase().includes(q.toLowerCase())), [q]);
  const kb = useMemo(() => knowledge.filter((k) => (k.statement + k.topic + k.subtopic).toLowerCase().includes(q.toLowerCase())), [q]);
  return (
    <div className="fade-in">
      <PageHeader eyebrow="Quellenbibliothek" title="Woher das Wissen kommt">
        Jede Quelle mit Evidenzkategorie, Prüfstatus und Zugriffshinweis. „Teilweise verifiziert“ heißt: Kernaussage über Sekundärquellen abgeglichen, Primärtext in dieser Arbeitsumgebung nicht abrufbar.
      </PageHeader>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row">
        <div className="flex rounded-[var(--radius-sm)] border border-line p-1" role="tablist">
          {(["sources", "kb"] as const).map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`min-h-10 rounded-lg px-4 text-sm ${tab === t ? "bg-surface-strong text-fg" : "text-muted"}`}>
              {t === "sources" ? `Quellen (${sources.length})` : `Wissensdatenbank (${knowledge.length})`}
            </button>
          ))}
        </div>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Suchen …" aria-label="Suchen" className="min-h-12 flex-1 rounded-[var(--radius-sm)] border border-line bg-surface px-3" />
      </div>
      {tab === "sources" ? (
        <div className="grid gap-3">
          {list.map((s) => {
            const overdue = (now - Date.parse(s.lastCheckedAt)) / 86_400_000 > s.reviewIntervalDays;
            return (
              <Card key={s.id}>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge>{s.id}</Badge>
                  <Badge tone="accent">{EV[s.evidence]}</Badge>
                  <Badge tone={s.verification === "verifiziert" ? "success" : s.verification === "teilweise_verifiziert" ? "warning" : "danger"}>{s.verification.replace("_", " ")}</Badge>
                  {overdue && <Badge tone="danger">Prüfung überfällig</Badge>}
                </div>
                <h2 className="mt-2 font-medium">{s.title}</h2>
                <p className="text-sm text-muted">{s.authorOrPublisher}{s.publishedAt && ` · ${s.publishedAt}`}</p>
                <a href={s.url} target="_blank" rel="noreferrer noopener" className="mt-1 block break-all text-xs text-accent hover:underline">{s.doi ? `doi:${s.doi}` : s.url}</a>
                <p className="mt-2 text-xs text-faint">{s.accessNote} · geprüft {s.lastCheckedAt} · Prüfintervall {s.reviewIntervalDays} Tage</p>
              </Card>
            );
          })}
        </div>
      ) : (
        <div className="grid gap-3">
          {kb.map((k) => (
            <Card key={k.id}>
              <div className="flex flex-wrap items-center gap-2"><Badge>{k.id} · v{k.version}</Badge><Badge tone="accent">{EV[k.evidence]}</Badge><span className="text-xs text-faint">{k.topic} › {k.subtopic} · {k.scope}</span></div>
              <p className="mt-2 font-medium">{k.statement}</p>
              <p className="mt-1 text-sm text-muted">{k.explanation}</p>
              {k.contradictions && <p className="mt-2 rounded-[var(--radius-sm)] border border-warning/40 p-2 text-xs text-warning">Widerspruch/Grenze: {k.contradictions}</p>}
              <p className="mt-2 text-xs text-faint">Quellen: {k.sourceIds.join(", ")}{k.lessonIds.length > 0 && ` · Lektionen: ${k.lessonIds.join(", ")}`}{k.questionIds.length > 0 && ` · Fragen: ${k.questionIds.join(", ")}`}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
