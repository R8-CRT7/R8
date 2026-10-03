"use client";
import Link from "next/link";
import { Badge, Card, Icon, PageHeader } from "@/components/ui";
import { curriculum } from "@/lib/content";
import { moduleProgress, objectiveSummaries } from "@/lib/derived";
import { useAcademy } from "@/lib/store/storage";

// Skill tree: three branches built from module prerequisites (see CURRICULUM.md).
const BRANCHES = [
  { title: "Gespräch", ids: ["M02", "M03", "M05", "M06"] },
  { title: "Prozess & Daten", ids: ["M04", "M07", "M08", "M09"] },
  { title: "Business & Skalierung", ids: ["M10", "M11", "M12"] },
];

export default function Skills() {
  const s = useAcademy();
  const objs = objectiveSummaries(s);
  const root = curriculum[0]!;
  const p = moduleProgress(s, root.id);
  return (
    <div className="fade-in">
      <PageHeader eyebrow="Skill Tree" title="Deine Kompetenzlandkarte">Ein Zweig öffnet sich, wenn das Fundament steht. Freischaltungen sind Empfehlungen – du kannst jederzeit überall reinschauen.</PageHeader>
      <Card className="mx-auto max-w-xl text-center">
        <Badge tone={p.examPassed ? "success" : "accent"}>{p.examPassed ? "Fundament gelegt" : "Fundament"}</Badge>
        <h2 className="mt-2 text-lg font-semibold">Modul 1: {root.title}</h2>
        <div className="mt-3 flex flex-wrap justify-center gap-1.5">
          {objs.filter((o) => o.moduleId === "M01").map((o) => (
            <span key={o.objectiveId} title={o.text} className={`h-3 w-8 rounded-full ${o.mastery === "gesichert" ? "bg-success" : o.mastery === "gefestigt" ? "bg-accent" : o.mastery === "im_aufbau" ? "bg-accent/35" : "bg-surface-strong"}`} />
          ))}
        </div>
        <p className="mt-2 text-xs text-faint">Ein Balken pro Lernziel: grau = nicht geprüft, hell = im Aufbau, blau = gefestigt, grün = gesichert</p>
      </Card>
      <div aria-hidden className="mx-auto h-8 w-px bg-line" />
      <div className="grid gap-4 md:grid-cols-3">
        {BRANCHES.map((b) => (
          <Card key={b.title}>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent">{b.title}</h2>
            <ol className="grid gap-2">
              {b.ids.map((id) => {
                const c = curriculum.find((x) => x.id === id)!;
                return (
                  <li key={id}>
                    <Link href={`/learn/${id}/`} className="flex min-h-12 items-center gap-3 rounded-[var(--radius-sm)] border border-line p-2.5 text-sm hover:border-line-strong">
                      <span className="grid h-8 w-8 place-items-center rounded-lg bg-surface-strong text-xs text-faint">{c.status === "verfuegbar" ? c.number : <Icon name="lock" className="h-3.5 w-3.5" />}</span>
                      <span className="flex-1">{c.title}</span>
                    </Link>
                  </li>
                );
              })}
            </ol>
          </Card>
        ))}
      </div>
    </div>
  );
}
