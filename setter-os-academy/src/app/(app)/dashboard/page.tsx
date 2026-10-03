"use client";
import Link from "next/link";
import { Badge, ButtonLink, Card, Icon, PageHeader, ProgressBar, Ring, Stat } from "@/components/ui";
import { program } from "@/lib/content";
import { ActivityChart } from "@/components/ActivityChart";
import { competenceBadges, MISSIONS, weeklyChallenges } from "@/lib/engine/challenges";
import { recommendations } from "@/lib/engine/recommend";
import { stageCheckPassed } from "@/lib/engine/program";
import { allDays, currentDay, dayState, programProgress } from "@/lib/engine/program";
import { ACHIEVEMENTS } from "@/lib/engine/gamification";
import { moduleProgress, objectiveSummaries, overview } from "@/lib/derived";
import { useAcademy } from "@/lib/store/storage";

const MASTERY_LABEL = { nicht_geprueft: "nicht geprüft", im_aufbau: "im Aufbau", gefestigt: "gefestigt", gesichert: "gesichert" } as const;

export default function Dashboard() {
  const s = useAcademy();
  const now = Date.now();
  const o = overview(s, now);
  const objectives = objectiveSummaries(s);
  const DAYMS = 86_400_000;
  const today0 = new Date(); today0.setHours(0, 0, 0, 0);
  const days = Array.from({ length: 14 }, (_, i) => {
    const start = today0.getTime() - (13 - i) * DAYMS;
    return { date: new Date(start), count: s.attempts.filter((a) => a.at >= start && a.at < start + DAYMS).length };
  });
  const wc = weeklyChallenges(s, now);
  const recs = recommendations(s, now, 3);
  const badges = competenceBadges(s, (id) => { const st = program.find((p) => p.id === id); return st ? stageCheckPassed(s, st) : false; });
  const lastSim = s.simulations[s.simulations.length - 1];
  const aiCount = s.aiSimulations.length;

  return (
    <div className="fade-in">
      <PageHeader eyebrow={new Date().toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" })} title={`Hallo ${s.profile!.displayName}`}>
        {s.settings.pauseMode ? "Lernpause aktiv – nichts geht verloren. Du kannst jederzeit weitermachen." : "Kurze Einheiten, regelmäßig wiederholt: So bleibt Wissen hängen."}
      </PageHeader>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Today in the 90-day plan */}
        <Card className="lg:col-span-2">
          <TodayCard />
        </Card>

        {/* Review */}
        <Card>
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Wiederholung</h2>
            <Icon name="repeat" className="h-5 w-5 text-accent" />
          </div>
          <p className="mt-3 text-4xl font-semibold tabular-nums">{o.due}</p>
          <p className="text-sm text-muted">{o.due === 1 ? "Frage ist fällig" : "Fragen sind fällig"}</p>
          <ButtonLink href="/review/" variant={o.due ? "primary" : "secondary"} className="mt-4 w-full">{o.due ? "Jetzt wiederholen" : "Wiederholungszentrum"}</ButtonLink>
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Aktive Lerntage (7 Tage)" value={`${o.activeDays}/7`} hint="Pausen sind erlaubt" />
        <Stat label="Beantwortete Fragen" value={o.answered} hint={o.accuracy === null ? "–" : `${Math.round(o.accuracy * 100)} % richtig`} />
        <Stat label="Gespräche geübt" value={o.simulations + aiCount} hint={`${aiCount} mit KI · ${o.simulations} offline${lastSim ? "" : ""}`} />
        <Stat label={`Level ${o.level.level}`} value={`${o.xp} XP`} hint="misst Aktivität, nicht Kompetenz" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-semibold">Lernaktivität</h2>
            <span className="text-xs text-faint">beantwortete Fragen · 14 Tage</span>
          </div>
          <ActivityChart days={days} />
        </Card>
        <Card>
          <div className="mb-2 flex items-center justify-between"><h2 className="font-semibold">Wochen-Challenge</h2><span className="text-xs text-faint">{wc.week}</span></div>
          <ul className="grid gap-3">
            {wc.items.map((c) => (
              <li key={c.id} className="grid gap-1 text-sm">
                <div className="flex justify-between gap-2"><span className="text-muted">{c.title}</span><span className="tabular-nums">{c.value}/{c.target}</span></div>
                <ProgressBar value={c.value / c.target} label={c.title} />
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[11px] text-faint">Freiwillig. Wer eine Woche aussetzt, verliert nichts.</p>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card>
          <h2 className="mb-2 font-semibold">Empfohlen für dich</h2>
          {recs.length === 0 ? <p className="text-sm text-muted">Mach im Plan weiter – sobald du übst, kommen gezielte Vorschläge.</p> : (
            <ul className="grid gap-2">{recs.map((r) => <li key={r.href}><Link href={r.href} className="block rounded-[var(--radius-sm)] border border-line p-3 text-sm hover:border-line-strong"><span className="font-medium">{r.title}</span><span className="block text-xs text-faint">{r.reason}</span></Link></li>)}</ul>
          )}
          <Link href="/mistakes/" className="mt-3 inline-block text-sm text-accent hover:underline">Fehlergedächtnis öffnen</Link>
        </Card>
        <Card className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Kompetenzstand</h2>
            <Link href="/stats/" className="text-sm text-accent hover:underline">Details</Link>
          </div>
          <p className="mb-4 text-xs text-faint">Balken = gemessene Leistung (letzte Versuche). Etikett = vorsichtige Einschätzung; „gesichert“ erst nach richtigem Abruf mit Abstand. Kalendertage und XP zählen hier nicht.</p>
          <ul className="grid gap-3 sm:grid-cols-2">
            {objectives.map((ob) => (
              <li key={ob.objectiveId} className="grid gap-1.5">
                <div className="flex items-start justify-between gap-3 text-sm">
                  <span className="line-clamp-2 text-muted">{ob.text}</span>
                  <Badge tone={ob.mastery === "gesichert" ? "success" : ob.mastery === "gefestigt" ? "accent" : "neutral"} className="shrink-0">{MASTERY_LABEL[ob.mastery]}</Badge>
                </div>
                <ProgressBar value={(ob.measuredPerformance ?? 0) / 100} label={`Leistung ${ob.text}`} />
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-1 font-semibold">Kompetenz-Abzeichen</h2>
          <p className="mb-3 text-xs text-faint">Nur durch geprüfte Leistung – nicht durch Klicken.</p>
          <ul className="grid gap-2">
            {badges.map((b) => (
              <li key={b.id} className={b.earned ? "flex items-start gap-3" : "flex items-start gap-3 opacity-55"}>
                <span aria-hidden className={b.earned ? "grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-success/15 text-success" : "grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-line text-faint"}>{b.earned ? "✓" : "○"}</span>
                <span className="text-sm"><span className="font-medium">{b.title}</span><span className="block text-xs text-faint">{b.criterion}</span></span>
                <span className="sr-only">{b.earned ? "erreicht" : "noch nicht erreicht"}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <h2 className="mb-1 font-semibold">Praxis-Missionen</h2>
          <p className="mb-3 text-xs text-faint">Im Prüfungsmodus des KI-Gesprächs zu bestehen.</p>
          <ul className="grid gap-2">
            {MISSIONS.map((m) => {
              const done = m.done(s);
              return (
                <li key={m.id}>
                  <Link href={m.href} className="flex items-start gap-3 rounded-[var(--radius-sm)] border border-line p-3 text-sm hover:border-line-strong">
                    <span aria-hidden className={done ? "text-success" : "text-faint"}>{done ? "✓" : "○"}</span>
                    <span><span className="font-medium">{m.title}</span><span className="block text-xs text-faint">{m.how}</span></span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </Card>
      </div>

      <Card className="mt-4">
        <h2 className="mb-3 font-semibold">Erfolge</h2>
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {ACHIEVEMENTS.map((a) => {
            const got = s.achievements[a.id];
            return (
              <li key={a.id} className={got ? "flex items-center gap-3" : "flex items-center gap-3 opacity-45"}>
                <span aria-hidden className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-line bg-surface text-accent">{a.icon}</span>
                <span className="text-sm"><span className="font-medium">{a.title}</span><span className="block text-xs text-faint">{a.description}</span></span>
                <span className="sr-only">{got ? "freigeschaltet" : "noch nicht freigeschaltet"}</span>
              </li>
            );
          })}
        </ul>
      </Card>
    </div>
  );
}

function TodayCard() {
  const s = useAcademy();
  const now = Date.now();
  const prog = programProgress(s, program);
  if (!s.program.startedAt) {
    return (
      <div className="flex items-start gap-4">
        <Ring value={0} label="90-Tage-Plan">0%</Ring>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-accent">90-Tage-Ausbildungsplan</p>
          <h2 className="mt-1 text-lg font-semibold">Starte mit Stufe 1: Basics (7 Tage)</h2>
          <p className="mt-1 text-sm text-muted">Jeden Tag 30–45 Minuten: Kursbuch, Skill-Karten, Übungen, Gesprächssimulationen.</p>
          <ButtonLink href="/plan/" className="mt-4">Plan ansehen und starten <Icon name="arrow" className="h-4 w-4" /></ButtonLink>
        </div>
      </div>
    );
  }
  const day = currentDay(s, program);
  const d = day ? allDays(program).find((x) => x.day === day) : undefined;
  const ds = day ? dayState(s, program, day, now) : null;
  return (
    <div className="flex items-start gap-4">
      <Ring value={prog.ratio} label="Fortschritt 90-Tage-Plan">{`${prog.completed}/${prog.totalDays}`}</Ring>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold uppercase tracking-wider text-accent">Heute · Tag {day ?? "–"} von {prog.totalDays}</p>
        <h2 className="mt-1 text-lg font-semibold">{d ? d.title : "Alle verfügbaren Tage erledigt"}</h2>
        <p className="mt-1 text-sm text-muted">
          {ds?.status === "open" ? `${ds.doneCount} von ${ds.total} Punkten erledigt` : ds?.status === "locked" ? ds.reason : "Die nächste Stufe wird gerade ausgearbeitet."}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <ButtonLink href="/plan/">{ds?.status === "open" ? "Weiterlernen" : "Zum Plan"} <Icon name="arrow" className="h-4 w-4" /></ButtonLink>
          <ButtonLink href="/review/" variant="secondary">Wiederholen</ButtonLink>
        </div>
      </div>
    </div>
  );
}
