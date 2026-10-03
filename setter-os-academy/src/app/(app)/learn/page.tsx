"use client";
import Link from "next/link";
import { Badge, Card, Icon, PageHeader, ProgressBar } from "@/components/ui";
import { curriculum } from "@/lib/content";
import { moduleProgress } from "@/lib/derived";
import { useAcademy } from "@/lib/store/storage";

export default function LearningPath() {
  const s = useAcademy();
  return (
    <div className="fade-in">
      <PageHeader eyebrow="Lernpfad" title="12 Module zum selbstständigen Setter">
        Vom ersten Gespräch bis zum eigenen Setting-Service. Im Vertical Slice ist Modul 1 vollständig verfügbar; die übrigen Module sind inhaltlich geplant (siehe Lehrplan).
      </PageHeader>
      <ol className="relative grid gap-3 before:absolute before:bottom-6 before:left-[27px] before:top-6 before:w-px before:bg-line">
        {curriculum.map((c) => {
          const p = moduleProgress(s, c.id);
          const available = c.status === "verfuegbar";
          return (
            <li key={c.id} className="relative">
              <Link href={`/learn/${c.id}/`} className="group flex gap-4">
                <span className={`relative z-10 grid h-14 w-14 shrink-0 place-items-center rounded-2xl border text-sm font-semibold ${available ? "border-accent/50 bg-accent/15 text-accent" : "border-line bg-elev text-faint"}`}>
                  {p.examPassed ? <Icon name="check" /> : available ? c.number : <Icon name="lock" className="h-4 w-4" />}
                </span>
                <Card className="flex-1 transition-colors group-hover:border-line-strong">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="font-semibold">Modul {c.number}: {c.title}</h2>
                    {available ? <Badge tone="success">verfügbar</Badge> : <Badge>in Vorbereitung</Badge>}
                  </div>
                  <p className="mt-1 text-sm text-muted">{c.subtitle}</p>
                  {available && <ProgressBar className="mt-3" value={p.ratio} label={`Fortschritt ${c.title}`} />}
                  {c.prerequisites.length > 0 && <p className="mt-2 text-xs text-faint">Empfohlen nach: {c.prerequisites.join(", ")}</p>}
                </Card>
              </Link>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
