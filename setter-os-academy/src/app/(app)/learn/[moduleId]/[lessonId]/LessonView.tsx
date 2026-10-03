"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { QuestionRenderer } from "@/components/QuestionRenderer";
import { Badge, Button, Callout, Card, Icon } from "@/components/ui";
import { COURSE_VERSION, moduleById, questionById, sourceById } from "@/lib/content";
import { completeLesson, recordAnswer } from "@/lib/store/state";
import { update, useAcademy } from "@/lib/store/storage";
import type { LessonBlock } from "@/lib/types";

export default function LessonView({ moduleId, lessonId }: { moduleId: string; lessonId: string }) {
  const router = useRouter();
  const s = useAcademy();
  const m = moduleById(moduleId)!;
  const idx = m.lessons.findIndex((l) => l.id === lessonId);
  const lesson = m.lessons[idx]!;
  const next = m.lessons[idx + 1];
  const done = !!s.lessonsCompleted[lesson.id];
  const checks = lesson.blocks.filter((b) => b.kind === "check").length;
  const [answered, setAnswered] = useState<Set<string>>(new Set());

  function finish() {
    update((st) => completeLesson(st, lesson.id, COURSE_VERSION, Date.now()));
    router.push(next ? `/learn/${m.id}/${next.id}/` : `/learn/${m.id}/`);
  }

  return (
    <div className="fade-in mx-auto max-w-3xl">
      <nav className="mb-4 flex items-center gap-2 text-sm text-faint" aria-label="Brotkrumen">
        <Link href={`/learn/${m.id}/`} className="hover:text-fg">Modul {m.number}</Link>
        <span aria-hidden>/</span>
        <span>Lektion {idx + 1} von {m.lessons.length}</span>
      </nav>
      <header className="mb-6">
        <h1 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight sm:text-3xl">{lesson.title}</h1>
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge>{lesson.minutes} Min.</Badge>
          <Badge tone="accent">{checks} Abrufübungen</Badge>
          {done && <Badge tone="success">abgeschlossen</Badge>}
        </div>
      </header>

      <div className="grid gap-5">
        {lesson.blocks.map((b, i) => (
          <Block key={i} block={b} onAnswered={(qid) => setAnswered((x) => new Set(x).add(qid))} />
        ))}

        <Card>
          <h2 className="mb-2 font-semibold">Zusammenfassung</h2>
          <ul className="grid gap-1.5 text-sm text-muted">
            {lesson.summary.map((x) => <li key={x} className="flex gap-2"><Icon name="check" className="mt-0.5 h-4 w-4 shrink-0 text-accent" />{x}</li>)}
          </ul>
          <p className="mt-4 text-xs text-faint">Quellen: {lesson.sourceIds.map((id) => sourceById(id)?.title ?? id).join(" · ")}</p>
        </Card>

        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-faint">{answered.size} von {checks} Abrufübungen beantwortet{answered.size < checks && " – empfohlen vor dem Abschluss"}</p>
          <Button onClick={finish} className="min-h-12">
            {done ? (next ? "Nächste Lektion" : "Zur Modulübersicht") : "Lektion abschließen"} <Icon name="arrow" className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function Block({ block: b, onAnswered }: { block: LessonBlock; onAnswered: (qid: string) => void }) {
  switch (b.kind) {
    case "text":
      return (
        <section>
          {b.title && <h2 className="mb-2 text-lg font-semibold">{b.title}</h2>}
          <div className="prose-lesson text-[15px] text-fg/90 sm:text-base">{b.body}</div>
        </section>
      );
    case "example":
      return (
        <Card className="border-l-2 border-l-accent">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-accent">Beispiel</p>
          <h3 className="mb-2 font-semibold">{b.title}</h3>
          <div className="prose-lesson text-sm text-muted">{b.body}</div>
        </Card>
      );
    case "workedExample":
      return (
        <Card>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-accent-2">Lösungsweg Schritt für Schritt</p>
          <h3 className="mb-3 font-semibold">{b.title}</h3>
          <ol className="grid gap-2">
            {b.steps.map((st, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-accent-2/15 text-xs font-semibold text-accent-2">{i + 1}</span>
                <span className="text-muted">{st}</span>
              </li>
            ))}
          </ol>
        </Card>
      );
    case "caseStudy":
      return (
        <Card>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-warning">Fallstudie</p>
          <h3 className="mb-2 font-semibold">{b.title}</h3>
          <p className="text-sm text-muted">{b.situation}</p>
          <details className="mt-3 rounded-[var(--radius-sm)] border border-line p-3">
            <summary className="min-h-8 cursor-pointer text-sm font-medium">Erst selbst überlegen – dann Analyse anzeigen</summary>
            <p className="mt-2 text-sm text-muted">{b.analysis}</p>
          </details>
          {b.simulationNote && <p className="mt-2 text-xs text-faint">{b.simulationNote}</p>}
        </Card>
      );
    case "callout":
      return <Callout tone={b.tone} title={b.title}>{b.body}</Callout>;
    case "reflect":
      return (
        <Card className="border-dashed">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-faint">Reflexion</p>
          <p className="text-sm">{b.prompt}</p>
          <textarea rows={3} aria-label="Notiz zur Reflexion (wird nicht gespeichert)" className="mt-3 w-full rounded-[var(--radius-sm)] border border-line bg-elev p-3 text-base" placeholder="Nur für dich – wird nicht gespeichert." />
        </Card>
      );
    case "check": {
      const q = questionById(b.questionId)!;
      return (
        <Card className="border-accent/30">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-accent">Abrufübung</p>
          <QuestionRenderer
            question={q}
            onAnswered={(r, meta) => {
              update((st) => recordAnswer(st, q, r, { ...meta, context: "lesson", now: Date.now() }));
              onAnswered(q.id);
            }}
          />
        </Card>
      );
    }
  }
}
