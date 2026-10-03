"use client";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { QuestionRenderer } from "@/components/QuestionRenderer";
import { Badge, Button, ButtonLink, Card, PageHeader, Stat } from "@/components/ui";
import { questionById } from "@/lib/content";
import { BOX_INTERVAL_DAYS } from "@/lib/engine/review";
import { dueReviews } from "@/lib/derived";
import { recordAnswer, recordReviewSession } from "@/lib/store/state";
import { update, useAcademy } from "@/lib/store/storage";

export default function ReviewCenter() {
  const s = useAcademy();
  const params = useSearchParams();
  const focus = params.get("focus")?.split(",").filter((id) => questionById(id)) ?? [];
  // Session queue is fixed when the session starts (answers re-schedule items, the list must not jump).
  const [queue, setQueue] = useState<string[] | null>(null);
  const [i, setI] = useState(0);
  const [answered, setAnswered] = useState(false);
  const due = useMemo(() => dueReviews(s, Date.now()), [s]);
  const sessionDone = queue !== null && i >= queue.length;
  useEffect(() => {
    if (sessionDone) update((st) => recordReviewSession(st, Date.now()));
  }, [sessionDone]);
  const boxes = [1, 2, 3, 4, 5].map((b) => Object.values(s.reviews).filter((r) => r.box === b).length);

  if (queue === null) {
    const next = Object.values(s.reviews).sort((a, b) => a.nextDueAt - b.nextDueAt)[0];
    return (
      <div className="fade-in">
        <PageHeader eyebrow="Wiederholungszentrum" title="Abrufen statt Wiederlesen">
          Fällige Fragen kommen vermischt aus verschiedenen Lernzielen. Richtig & sicher → längerer Abstand. Falsch → morgen wieder. Nichts geht verloren.
        </PageHeader>
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            {focus.length > 0 ? (
              <>
                <h2 className="font-semibold">Gezielte Wiederholung aus deiner Simulation</h2>
                <p className="mt-1 text-sm text-muted">{focus.length} Fragen passend zu deinen Verbesserungspunkten.</p>
                <Button className="mt-4 min-h-12" onClick={() => setQueue(focus)}>Starten</Button>
              </>
            ) : due.length ? (
              <>
                <h2 className="font-semibold">{due.length} Fragen fällig</h2>
                <p className="mt-1 text-sm text-muted">Dauer ca. {Math.max(2, Math.round(due.length * 0.75))} Minuten.</p>
                <Button className="mt-4 min-h-12" onClick={() => setQueue(due.map((d) => d.questionId))}>Wiederholung starten</Button>
              </>
            ) : (
              <>
                <h2 className="font-semibold">Gerade nichts fällig</h2>
                <p className="mt-1 text-sm text-muted">
                  {next ? `Nächste Wiederholung: ${new Date(next.nextDueAt).toLocaleString("de-DE", { weekday: "long", hour: "2-digit", minute: "2-digit" })}.` : "Beantworte Fragen in Lektionen oder im Quiz – sie erscheinen dann hier."}
                </p>
                <ButtonLink href="/learn/" variant="secondary" className="mt-4">Zum Lernpfad</ButtonLink>
              </>
            )}
          </Card>
          <Card>
            <h2 className="mb-3 font-semibold">So funktioniert es</h2>
            <ul className="grid gap-1.5 text-sm text-muted">
              {[1, 2, 3, 4, 5].map((b) => (
                <li key={b} className="flex justify-between"><span>Box {b} · {BOX_INTERVAL_DAYS[b]} {BOX_INTERVAL_DAYS[b] === 1 ? "Tag" : "Tage"}</span><Badge>{boxes[b - 1]}</Badge></li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-faint">„Geraten“ und richtig → bleibt in der Box. Transparenter Leitner-Algorithmus (LEARNING_SCIENCE.md).</p>
          </Card>
        </div>
      </div>
    );
  }

  if (i >= queue.length) {
    return (
      <div className="fade-in mx-auto max-w-xl text-center">
        <PageHeader title="Wiederholung erledigt" />
        <div className="grid grid-cols-2 gap-3"><Stat label="Bearbeitet" value={queue.length} /><Stat label="Noch fällig" value={due.length} /></div>
        <div className="mt-6 flex justify-center gap-2">
          <ButtonLink href="/dashboard/">Zum Dashboard</ButtonLink>
          <Button variant="secondary" onClick={() => { setQueue(null); setI(0); }}>Übersicht</Button>
        </div>
      </div>
    );
  }

  const q = questionById(queue[i]!)!;
  return (
    <div className="fade-in mx-auto max-w-2xl">
      <p className="mb-3 text-sm text-faint">Wiederholung {i + 1} von {queue.length}</p>
      <Card>
        <QuestionRenderer key={`${q.id}-${i}`} question={q} onAnswered={(r, meta) => { update((st) => recordAnswer(st, q, r, { ...meta, context: "review", now: Date.now() })); setAnswered(true); }} />
        {answered && <Button className="mt-4 min-h-12 w-full" onClick={() => { setI(i + 1); setAnswered(false); }}>Weiter</Button>}
      </Card>
    </div>
  );
}
