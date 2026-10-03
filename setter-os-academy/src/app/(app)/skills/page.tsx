"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Badge, Card, PageHeader } from "@/components/ui";
import { concepts, curriculum, longterm } from "@/lib/content";
import { objectiveSummaries } from "@/lib/derived";
import { conceptStates, nextConcepts, trackReadiness, type ConceptLevel, type ConceptState } from "@/lib/engine/competency";
import type { ConceptArea } from "@/lib/types";
import { useAcademy } from "@/lib/store/storage";

const AREA_LABEL: Record<ConceptArea, string> = {
  grundlagen: "Grundlagen",
  gespraech: "Gesprächsführung",
  psychologie: "Psychologie",
  qualifizierung: "Qualifizierung",
  chat: "Chat",
  einwaende: "Einwände",
  termin: "Termine & Übergabe",
  daten: "Daten & Kennzahlen",
  recht: "Recht & Ethik",
  business: "Business & Automatisierung",
};
const LEVEL: Record<ConceptLevel, { label: string; tone: "neutral" | "accent" | "success" | "warning" }> = {
  in_vorbereitung: { label: "Inhalt in Vorbereitung", tone: "neutral" },
  nicht_geprueft: { label: "Nicht geprüft", tone: "neutral" },
  im_aufbau: { label: "Im Aufbau", tone: "warning" },
  gefestigt: { label: "Gefestigt", tone: "accent" },
  gesichert: { label: "Gesichert", tone: "success" },
};
const READINESS = {
  bereit: { label: "Voraussetzungen erfüllt", tone: "success" },
  teilweise: { label: "Teilweise erfüllt", tone: "accent" },
  offen: { label: "Noch offen", tone: "neutral" },
  inhalt_fehlt: { label: "Grundlagen in Vorbereitung", tone: "neutral" },
} as const;

export default function Skills() {
  const s = useAcademy();
  const [tab, setTab] = useState<"baum" | "spezial">("baum");
  const states = useMemo(() => {
    const m = Object.fromEntries(objectiveSummaries(s).map((o) => [o.objectiveId, o.mastery]));
    return conceptStates(concepts, m);
  }, [s]);
  const label = (id: string) => concepts.find((c) => c.id === id)?.label ?? id;
  const areas = [...new Set(concepts.map((c) => c.area))];
  const next = nextConcepts(states);
  const counted = states.filter((x) => x.level !== "in_vorbereitung");
  const solid = counted.filter((x) => x.level === "gefestigt" || x.level === "gesichert").length;

  return (
    <div className="fade-in">
      <PageHeader eyebrow="Kompetenzbaum" title="Was du sicher kannst">
        Jedes Konzept zählt nur so viel wie sein schwächstes geprüftes Lernziel. Kalendertage oder reines Durchklicken heben keine Stufe an.
      </PageHeader>

      <div className="mb-5 flex gap-2" role="tablist" aria-label="Ansicht">
        {(["baum", "spezial"] as const).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`min-h-11 rounded-full border px-4 text-sm ${tab === t ? "border-accent bg-accent-solid text-accent-ink" : "border-line bg-surface text-muted hover:text-fg"}`}>
            {t === "baum" ? "Konzepte" : `Spezialisierungen (${longterm.tracks.length})`}
          </button>
        ))}
      </div>

      {tab === "baum" ? (
        <>
          <div className="mb-6 grid gap-4 md:grid-cols-[1fr_1.4fr]">
            <Card>
              <p className="text-sm text-muted">Gefestigte Konzepte</p>
              <p className="mt-1 text-3xl font-semibold tabular-nums">
                {solid}
                <span className="text-lg text-faint"> / {counted.length}</span>
              </p>
              <p className="mt-2 text-xs text-faint">{states.length - counted.length} weitere Konzepte folgen mit den nächsten Modulen.</p>
            </Card>
            <Card>
              <h2 className="mb-2 font-semibold">Als Nächstes stärken</h2>
              {next.length ? (
                <ul className="grid gap-2 text-sm">
                  {next.map((n) => (
                    <li key={n.concept.id} className="flex flex-wrap items-center justify-between gap-2">
                      <span>{n.concept.label}</span>
                      <Link className="text-accent underline-offset-4 hover:underline" href={n.level === "im_aufbau" ? "/review/" : `/learn/${n.concept.moduleId}/`}>
                        {n.level === "im_aufbau" ? "Wiederholen" : "Lernen"}
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted">Alles Verfügbare ist gefestigt. Wiederhole regelmäßig, damit es so bleibt.</p>
              )}
            </Card>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {areas.map((a) => (
              <Card key={a}>
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-[0.12em] text-accent">{AREA_LABEL[a]}</h2>
                <ul className="grid gap-2">
                  {states.filter((x) => x.concept.area === a).map((x) => (
                    <ConceptRow key={x.concept.id} x={x} label={label} />
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        </>
      ) : (
        <>
          <Card className="mb-5">
            <h2 className="font-semibold">Nach Tag 90: Spezialisierungen</h2>
            <p className="mt-1 text-sm text-muted">
              Ab Stufe 8 (Tag 91) wählst du Spezialisierungen. Sie sind als Lernpfade geplant; die Inhalte werden nach den zwölf Grundlagenmodulen geschrieben. „Voraussetzungen erfüllt“ heißt: Alle Pflichtkonzepte sind bei dir gefestigt.
            </p>
          </Card>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {longterm.tracks.map((t) => {
              const r = trackReadiness(t, states);
              return (
                <Card key={t.id} className="flex flex-col">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <Badge tone={READINESS[r.readiness].tone}>{READINESS[r.readiness].label}</Badge>
                    <Badge tone="neutral">Inhalt geplant</Badge>
                  </div>
                  <h3 className="font-semibold">{t.title}</h3>
                  <p className="mt-1 text-sm text-muted">{t.summary}</p>
                  <ul className="mt-3 grid gap-1 text-sm text-muted">
                    {t.focus.map((f) => (
                      <li key={f}>• {f}</li>
                    ))}
                  </ul>
                  <p className="mt-3 text-xs text-faint">
                    Pflichtkonzepte ({r.met}/{r.total}): {t.requiredConcepts.map(label).join(", ")}
                  </p>
                  {t.legalNote && <p className="mt-2 rounded-[var(--radius-sm)] border border-warning/40 p-2 text-xs text-warning">{t.legalNote}</p>}
                </Card>
              );
            })}
          </div>
        </>
      )}
      <p className="mt-6 text-xs text-faint">
        Module mit Inhalt: {curriculum.filter((c) => c.status === "verfuegbar").map((c) => c.number).join(", ")}. Weitere sind in Vorbereitung.
      </p>
    </div>
  );
}

function ConceptRow({ x, label }: { x: ConceptState; label: (id: string) => string }) {
  const l = LEVEL[x.level];
  return (
    <li className="rounded-[var(--radius-sm)] border border-line p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link href={`/learn/${x.concept.moduleId}/`} className="font-medium hover:text-accent">
          {x.concept.label}
        </Link>
        <Badge tone={l.tone}>{l.label}</Badge>
      </div>
      <p className="mt-1 text-sm text-muted">{x.concept.description}</p>
      <p className="mt-1 text-xs text-faint">
        Modul {x.concept.moduleId.slice(1)}
        {x.total ? ` · ${x.solid}/${x.total} Lernziele gefestigt` : ""}
        {x.concept.prerequisites.length ? ` · baut auf: ${x.concept.prerequisites.map(label).join(", ")}` : ""}
      </p>
    </li>
  );
}
