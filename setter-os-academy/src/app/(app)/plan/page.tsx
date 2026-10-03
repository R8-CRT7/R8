"use client";
import Link from "next/link";
import { Badge, Button, ButtonLink, Card, Icon, PageHeader, ProgressBar, cx } from "@/components/ui";
import { curriculum, lessonById, longterm, moduleById, program, scenarioById } from "@/lib/content";
import { dayState, itemDone, currentDay, programProgress, stageCheckPassed, unlockAnchor } from "@/lib/engine/program";
import { moduleProgress, objectiveSummaries } from "@/lib/derived";
import { completeProgramDay, fastTrackDay, startProgram } from "@/lib/store/state";
import { update, useAcademy } from "@/lib/store/storage";
import type { ProgramItem } from "@/lib/types";

function itemInfo(it: ProgramItem): { label: string; href: string; kind: string } {
  switch (it.type) {
    case "lesson": {
      const l = lessonById(it.ref);
      return { label: l?.title ?? it.ref, href: `/learn/${l?.moduleId}/${it.ref}/`, kind: "Lektion" };
    }
    case "quiz": {
      const m = moduleById(it.ref);
      if (m) return { label: `Abschlussquiz Modul ${m.number}`, href: `/quiz/${it.ref}/`, kind: "Quiz" };
      const st = program.find((p) => p.id === it.ref);
      return { label: st?.check.title ?? it.ref, href: `/quiz/${it.ref}/`, kind: "Stufen-Check" };
    }
    case "simulation":
      return { label: scenarioById(it.ref)?.title ?? it.ref, href: `/simulator/${it.ref}/`, kind: "Simulation" };
    case "review":
      return { label: "Wiederholung der fälligen Fragen", href: "/review/", kind: "Wiederholung" };
    case "transfer": {
      const m = moduleById(it.ref);
      return { label: `Transferaufgabe Modul ${m?.number ?? ""}`, href: `/learn/${it.ref}/`, kind: "Transfer (optional)" };
    }
  }
}

export default function PlanPage() {
  const s = useAcademy();
  const now = Date.now();
  const prog = programProgress(s, program);
  const today = currentDay(s, program);
  const objectives = objectiveSummaries(s);

  if (!s.program.startedAt) {
    return (
      <div className="fade-in mx-auto max-w-3xl">
        <PageHeader eyebrow="Dein Ausbildungsplan" title="90 Tage bis zum Setter">
          Sieben Stufen, jeden Tag eine Einheit von etwa 30–45 Minuten. Am Ende jeder Stufe prüft ein Stufen-Check, ob du die Themen wirklich beherrschst – erst dann öffnet die nächste Stufe.
        </PageHeader>
        <Card>
          <ol className="grid gap-3">
            {program.map((st) => (
              <li key={st.id} className="flex gap-3">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-line text-sm font-semibold text-accent">{st.number}</span>
                <div className="min-w-0">
                  <p className="font-medium">{st.title} <span className="text-xs font-normal text-faint">· Tag {st.dayFrom}–{st.dayTo}</span></p>
                  <p className="text-sm text-muted">{st.goal}</p>
                </div>
              </li>
            ))}
          </ol>
          <ul className="mt-5 grid gap-1 text-sm text-muted">
            <li>• Ein neuer Tag öffnet sich am nächsten Kalendertag – Abstand hilft beim Behalten. Du kannst früher weitermachen, wenn du möchtest.</li>
            <li>• Pausen sind erlaubt. Es geht nichts verloren, und es gibt keine Strafpunkte.</li>
            <li>• Ausgearbeitet: Stufe {program.filter((p) => p.available).map((p) => p.number).join(", ")}. Weitere Stufen bleiben gesperrt, bis ihre Inhalte fertig sind.</li>
          </ul>
          <Button className="mt-5 min-h-12 w-full sm:w-auto" onClick={() => update((st) => startProgram(st, Date.now()))}>Plan starten – Tag 1</Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="fade-in">
      <PageHeader eyebrow="Dein Ausbildungsplan" title={today ? `Tag ${today} von ${prog.totalDays}` : "Alle verfügbaren Tage erledigt"}>
        {prog.completed} Tage abgeschlossen. Jede Stufe endet mit einem Stufen-Check.
      </PageHeader>
      <ProgressBar value={prog.ratio} label="Fortschritt 90-Tage-Plan" className="mb-6" />

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="grid content-start gap-4">
          {program.map((st) => {
            const passed = stageCheckPassed(s, st);
            const active = today !== null && today >= st.dayFrom && today <= st.dayTo;
            return (
              <Card key={st.id} className={cx(active && "border-accent/50")}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">Stufe {st.number} · Tag {st.dayFrom}–{st.dayTo}</p>
                    <h2 className="text-lg font-semibold">{st.title}</h2>
                    <p className="mt-1 text-sm text-muted">{st.goal}</p>
                  </div>
                  {passed ? <Badge tone="success">bestanden</Badge> : active ? <Badge tone="accent">aktuell</Badge> : !st.available ? <Badge>in Vorbereitung</Badge> : <Badge>offen</Badge>}
                </div>

                {st.available ? (
                  <ol className="mt-4 grid gap-2">
                    {st.days.map((d) => {
                      const ds = dayState(s, program, d.day, now);
                      const isToday = d.day === today;
                      return (
                        <li key={d.day} className={cx("rounded-[var(--radius-sm)] border p-3", isToday ? "border-accent/50 bg-accent/5" : "border-line")}>
                          <div className="flex items-center gap-3">
                            <span className={cx("grid h-8 w-8 shrink-0 place-items-center rounded-lg text-xs font-semibold", ds.status === "completed" ? "bg-success/15 text-success" : ds.status === "open" ? "bg-accent/15 text-accent" : "bg-surface-strong text-faint")}>
                              {ds.status === "completed" ? <Icon name="check" className="h-4 w-4" /> : ds.status === "locked" ? <Icon name="lock" className="h-3.5 w-3.5" /> : d.day}
                            </span>
                            <div className="min-w-0 flex-1">
                              <p className="text-sm font-medium">Tag {d.day}: {d.title}</p>
                              <p className="text-xs text-faint">
                                {ds.status === "completed" ? `abgeschlossen am ${new Date(ds.at).toLocaleDateString("de-DE")}` : ds.status === "open" ? `${ds.doneCount} von ${ds.total} erledigt` : ds.reason}
                              </p>
                            </div>
                          </div>
                          {ds.status === "open" && (
                            <div className="mt-3 grid gap-2">
                              {d.items.map((it, idx) => {
                                const info = itemInfo(it);
                                const done = itemDone(s, it, unlockAnchor(s, d.day), now);
                                return (
                                  <Link key={idx} href={info.href} className="flex min-h-12 items-center gap-3 rounded-[var(--radius-sm)] border border-line bg-surface px-3 py-2 text-sm hover:border-line-strong">
                                    <span className={cx("grid h-6 w-6 shrink-0 place-items-center rounded-full border", done ? "border-success bg-success/15 text-success" : "border-line-strong")}>{done && <Icon name="check" className="h-3.5 w-3.5" />}</span>
                                    <span className="min-w-0 flex-1"><span className="block text-[11px] uppercase tracking-wider text-faint">{info.kind}</span>{info.label}</span>
                                    <Icon name="arrow" className="h-4 w-4 text-faint" />
                                  </Link>
                                );
                              })}
                              <Button className="mt-1 min-h-12" disabled={!ds.allDone} onClick={() => update((x) => completeProgramDay(x, d.day, Date.now()))}>
                                {ds.allDone ? `Tag ${d.day} abschließen` : "Erst alle Punkte erledigen"}
                              </Button>
                            </div>
                          )}
                          {ds.status === "locked" && ds.canFastTrack && (
                            <Button variant="ghost" className="mt-2" onClick={() => update((x) => fastTrackDay(x, d.day))}>Heute schon weitermachen</Button>
                          )}
                        </li>
                      );
                    })}
                  </ol>
                ) : (
                  <div className="mt-4">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-faint">Geplante Inhalte</p>
                    <ul className="grid gap-1 text-sm text-muted sm:grid-cols-2">{st.plannedTopics?.map((t) => <li key={t}>• {t}</li>)}</ul>
                  </div>
                )}

                {st.available && (
                  <div className="mt-4 rounded-[var(--radius-sm)] border border-line bg-surface p-3 text-sm">
                    <p className="font-medium">{st.check.title}</p>
                    <p className="mt-1 text-muted">{st.check.questionIds.length} gemischte Fragen, bestanden ab {st.check.passThreshold * 100} %. Außerdem bestanden: {st.check.requiredSimulations.map((id) => scenarioById(id)?.title).join(" und ")}.</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {st.check.requiredSimulations.map((id) => {
                        const ok = s.simulations.some((x) => x.scenarioId === id && x.passed) || s.aiSimulations.some((x) => x.scenarioId === id && x.mode === "pruefung" && x.evaluation.passed === true);
                        return <Badge key={id} tone={ok ? "success" : "neutral"}>{ok ? "✓" : "○"} {scenarioById(id)?.title}</Badge>;
                      })}
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
          <Card>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-accent-2">Nach Tag 90 · Architektur bis Tag 180</p>
            <h2 className="mt-1 text-lg font-semibold">Aufbaustufen und Spezialisierungen</h2>
            <p className="mt-1 text-sm text-muted">Geplant und strukturiert; die Inhalte entstehen, nachdem die Grundlagenmodule fertig sind. Jede Stufe öffnet nur über einen bestandenen Stufen-Check.</p>
            <ol className="mt-4 grid gap-3">
              {longterm.stages.map((st) => (
                <li key={st.id} className="rounded-[var(--radius-sm)] border border-line p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">Stufe {st.number} · Tag {st.dayFrom}–{st.dayTo}: {st.title}</p>
                    <Badge>geplant</Badge>
                  </div>
                  <p className="mt-1 text-sm text-muted">{st.goal}</p>
                  <ul className="mt-2 grid gap-1 text-sm text-muted">{st.structure.map((x) => <li key={x}>• {x}</li>)}</ul>
                  <p className="mt-2 text-xs text-faint">Freischaltung: {st.unlock}</p>
                </li>
              ))}
              <li className="rounded-[var(--radius-sm)] border border-dashed border-line p-3">
                <p className="font-medium">{longterm.open.title}</p>
                <p className="mt-1 text-sm text-muted">{longterm.open.text}</p>
              </li>
            </ol>
            <ButtonLink href="/skills/" variant="secondary" className="mt-4">18 Spezialisierungen ansehen</ButtonLink>
          </Card>
        </div>

        <aside className="grid content-start gap-4">
          <Card>
            <h2 className="mb-1 font-semibold">Themen beherrscht</h2>
            <p className="mb-3 text-xs text-faint">„Beherrscht“ = Modulquiz bestanden und mindestens 80 % der Lernziele gefestigt oder gesichert (verzögerter Abruf).</p>
            <ul className="grid gap-2">
              {curriculum.map((c) => {
                const objs = objectives.filter((o) => o.moduleId === c.id);
                const firm = objs.filter((o) => o.mastery === "gefestigt" || o.mastery === "gesichert").length;
                const mp = moduleProgress(s, c.id);
                const mastered = objs.length > 0 && mp.examPassed && firm / objs.length >= 0.8;
                return (
                  <li key={c.id} className="flex items-center justify-between gap-2 text-sm">
                    <span className={cx("min-w-0 truncate", c.status !== "verfuegbar" && "text-faint")}>{c.number}. {c.title}</span>
                    {c.status !== "verfuegbar" ? <Badge>bald</Badge> : mastered ? <Badge tone="success">beherrscht</Badge> : <Badge>{firm}/{objs.length}</Badge>}
                  </li>
                );
              })}
            </ul>
          </Card>
          <Card>
            <h2 className="mb-2 font-semibold">So funktioniert der Plan</h2>
            <ul className="grid gap-1.5 text-sm text-muted">
              <li>• Pro Tag 30–45 Minuten.</li>
              <li>• Neue Tage öffnen am nächsten Kalendertag. „Heute schon weitermachen“ ist erlaubt.</li>
              <li>• Die Wiederholung holt alte Themen gezielt zurück, damit sie bleiben.</li>
              <li>• Nach dem Stufen-Check öffnet die nächste Stufe.</li>
            </ul>
            <ButtonLink href="/learn/" variant="secondary" className="mt-4 w-full">Alle Module ansehen</ButtonLink>
          </Card>
        </aside>
      </div>
    </div>
  );
}
