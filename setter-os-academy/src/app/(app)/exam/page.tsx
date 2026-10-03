"use client";
import { Badge, ButtonLink, Card, Icon, PageHeader } from "@/components/ui";
import { modules } from "@/lib/content";
import { MASTER_EXAM } from "@/lib/masterExam";
import { moduleProgress } from "@/lib/derived";
import { useAcademy } from "@/lib/store/storage";

export default function ExamArea() {
  const s = useAcademy();
  return (
    <div className="fade-in">
      <PageHeader eyebrow="Prüfungsbereich & Abschlussübersicht" title="Prüfungen">Transparente Regeln, vorab festgelegt. Wiederholungen sind ausdrücklich vorgesehen.</PageHeader>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-faint">Modulprüfungen</h2>
      <div className="grid gap-3 md:grid-cols-2">
        {modules.map((m) => {
          const p = moduleProgress(s, m.id);
          const attempts = s.quizAttempts.filter((a) => a.moduleId === m.id);
          return (
            <Card key={m.id}>
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-semibold">Modul {m.number}: {m.title}</h3>
                {p.examPassed ? <Badge tone="success">bestanden</Badge> : <Badge>offen</Badge>}
              </div>
              <p className="mt-1 text-sm text-muted">{attempts.length} Versuch(e){p.bestExam !== null && ` · Bestwert ${p.bestExam} %`}</p>
              {attempts.length > 0 && (
                <ul className="mt-2 grid gap-1 text-xs text-faint">
                  {attempts.slice(-3).reverse().map((a) => <li key={a.id}>{new Date(a.at).toLocaleString("de-DE")} · {a.percent} % · Kursversion {a.courseVersion}</li>)}
                </ul>
              )}
              <ButtonLink href={`/quiz/${m.id}/`} variant="secondary" className="mt-3">{attempts.length ? "Erneut ablegen" : "Ablegen"}</ButtonLink>
            </Card>
          );
        })}
      </div>

      <h2 className="mb-3 mt-8 text-sm font-semibold uppercase tracking-wider text-faint">Master-Prüfung (Spezifikation {MASTER_EXAM.version})</h2>
      <Card>
        <div className="flex items-center gap-2 text-warning"><Icon name="lock" className="h-4 w-4" /><span className="text-sm font-medium">Noch nicht freigeschaltet – benötigt alle 12 Module.</span></div>
        <ol className="mt-4 grid gap-2 md:grid-cols-2">
          {MASTER_EXAM.parts.map((p) => (
            <li key={p.id} className="rounded-[var(--radius-sm)] border border-line p-3 text-sm">
              <div className="flex justify-between gap-2"><span className="font-medium">{p.title}</span><Badge>{p.rule}</Badge></div>
              <p className="mt-1 text-muted">{p.detail}</p>
              <p className="mt-1 text-xs text-faint">Prüft: {p.competencies.join(", ")}</p>
            </li>
          ))}
        </ol>
        <ul className="mt-4 grid gap-1 text-sm text-muted">{MASTER_EXAM.rules.map((r) => <li key={r}>• {r}</li>)}</ul>
      </Card>
    </div>
  );
}
