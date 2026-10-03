"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { QuestionRenderer } from "@/components/QuestionRenderer";
import { Badge, Button, ButtonLink, Card, PageHeader, ProgressBar, Ring } from "@/components/ui";
import { COURSE_VERSION, questionById, quizById } from "@/lib/content";
import { scoreAttempt } from "@/lib/engine/quiz";
import { recordAnswer, recordQuizAttempt } from "@/lib/store/state";
import { update } from "@/lib/store/storage";
import type { GradeResult } from "@/lib/types";
import { ERROR_LABEL } from "@/lib/derived";

/** Interleaves exam questions by objective so the same topic rarely appears twice in a row. */
function interleave(ids: string[]) {
  const groups = new Map<string, string[]>();
  for (const id of ids) {
    const o = questionById(id)!.objectiveId;
    groups.set(o, [...(groups.get(o) ?? []), id]);
  }
  const out: string[] = [];
  const lists = [...groups.values()];
  while (lists.some((l) => l.length)) for (const l of lists) if (l.length) out.push(l.shift()!);
  return out;
}

export default function QuizRunner({ moduleId }: { moduleId: string }) {
  const m = quizById(moduleId)!;
  const ids = useMemo(() => interleave(m.questionIds), [m]);
  const [started, setStarted] = useState(false);
  const [i, setI] = useState(0);
  const [results, setResults] = useState<GradeResult[]>([]);
  const [answeredCurrent, setAnsweredCurrent] = useState(false);
  const [finished, setFinished] = useState<null | ReturnType<typeof scoreAttempt>>(null);

  if (!started) {
    return (
      <div className="fade-in mx-auto max-w-2xl">
        <PageHeader eyebrow={m.eyebrow} title={m.title} />
        <Card>
          <h2 className="font-semibold">Regeln (vorab festgelegt)</h2>
          <ul className="mt-2 grid gap-1.5 text-sm text-muted">
            <li>• {ids.length} Fragen, gemischt über alle Lernziele (Interleaving).</li>
            <li>• Bestanden ab {m.passThreshold * 100} % der automatisch bewerteten Punkte. Teilpunkte bei Mehrfachauswahl, Zuordnung und Reihenfolge.</li>
            <li>• Die Lösung wird erst nach der Antwort angezeigt. Keine Zeitbegrenzung – die Bearbeitungszeit wird nur für deine Statistik erfasst.</li>
            <li>• Wiederholung jederzeit möglich. Ergebnisse werden mit der Fragenversion gespeichert und später nicht verändert.</li>
            <li>• Ein bestandenes Quiz zeigt aktuelles Wissen – noch kein dauerhaftes Können. Deshalb folgen Wiederholungen mit Abstand.</li>
          </ul>
          <Button className="mt-5 min-h-12 w-full sm:w-auto" onClick={() => setStarted(true)}>Quiz starten</Button>
        </Card>
      </div>
    );
  }

  if (finished) {
    const cats = results.flatMap((r) => r.errorCategories);
    const counts = Object.entries(cats.reduce<Record<string, number>>((a, c) => ({ ...a, [c]: (a[c] ?? 0) + 1 }), {})).sort((a, b) => b[1] - a[1]);
    return (
      <div className="fade-in mx-auto max-w-2xl">
        <PageHeader eyebrow="Ergebnis" title={finished.passed ? "Bestanden" : "Noch nicht bestanden"} />
        <Card className="flex flex-col items-center gap-4 text-center sm:flex-row sm:text-left">
          <Ring value={finished.percent / 100} size={110} label="Ergebnis">{finished.percent}%</Ring>
          <div>
            <p className="text-sm text-muted">Bestehensgrenze {m.passThreshold * 100} % · {finished.autoGraded} automatisch bewertete Fragen</p>
            <p className="mt-2 text-sm">{finished.passed ? "Stark. Die Fragen landen jetzt in deiner Wiederholung – in ein paar Tagen prüfen wir, ob es hängen geblieben ist." : "Kein Problem: Schau dir die Fehlerschwerpunkte an, wiederhole die passenden Lektionen und versuche es erneut."}</p>
            <Badge tone={finished.passed ? "success" : "warning"} className="mt-3">{finished.passed ? (m.kind === "stage-check" ? "Stufen-Check bestanden" : "Modulquiz bestanden") : "Wiederholung empfohlen"}</Badge>
          </div>
        </Card>
        {counts.length > 0 && (
          <Card className="mt-4">
            <h2 className="mb-2 font-semibold">Fehlerschwerpunkte</h2>
            <ul className="grid gap-1.5 text-sm text-muted">
              {counts.map(([c, n]) => <li key={c}>{ERROR_LABEL[c as keyof typeof ERROR_LABEL] ?? c}: {n}×</li>)}
            </ul>
          </Card>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          <ButtonLink href="/review/">Zur Wiederholung</ButtonLink>
          <ButtonLink href={m.backHref} variant="secondary">{m.kind === "stage-check" ? "Zum Plan" : "Zur Modulübersicht"}</ButtonLink>
          <Button variant="ghost" onClick={() => { setI(0); setResults([]); setFinished(null); setAnsweredCurrent(false); }}>Erneut versuchen</Button>
        </div>
      </div>
    );
  }

  const q = questionById(ids[i]!)!;
  const isLast = i === ids.length - 1;

  function next() {
    if (isLast) {
      const score = scoreAttempt(results, m.passThreshold);
      update((st) =>
        recordQuizAttempt(st, {
          id: `quiz-${Date.now().toString(36)}`,
          moduleId: m.id,
          kind: m.kind,
          at: Date.now(),
          percent: score.percent,
          passed: score.passed,
          courseVersion: COURSE_VERSION,
          questionVersions: Object.fromEntries(ids.map((id) => [id, questionById(id)!.version])),
          scores: Object.fromEntries(results.map((r) => [r.questionId, r.score])),
          pendingManualReview: score.pendingManualReview,
        }),
      );
      setFinished(score);
    } else {
      setI(i + 1);
      setAnsweredCurrent(false);
    }
  }

  return (
    <div className="fade-in mx-auto max-w-2xl">
      <div className="mb-4 flex items-center gap-3">
        <Link href={m.backHref} className="text-sm text-faint hover:text-fg">Abbrechen</Link>
        <ProgressBar className="flex-1" value={(i + (answeredCurrent ? 1 : 0)) / ids.length} label="Quizfortschritt" />
      </div>
      <Card>
        <QuestionRenderer
          key={q.id}
          question={q}
          index={i}
          total={ids.length}
          onAnswered={(r, meta) => {
            setResults((x) => [...x, r]);
            setAnsweredCurrent(true);
            update((st) => recordAnswer(st, q, r, { ...meta, context: "quiz", now: Date.now() }));
          }}
        />
        {answeredCurrent && (
          <Button className="mt-4 min-h-12 w-full" onClick={next}>{isLast ? "Auswertung anzeigen" : "Nächste Frage"}</Button>
        )}
      </Card>
    </div>
  );
}
