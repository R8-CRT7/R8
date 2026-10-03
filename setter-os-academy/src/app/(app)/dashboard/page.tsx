"use client";
import Link from "next/link";
import { Badge, ButtonLink, Card, Icon, PageHeader, ProgressBar, Ring, Stat } from "@/components/ui";
import { curriculum, modules, program, scenarios } from "@/lib/content";
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
  const lastSim = s.simulations[s.simulations.length - 1];

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
        <Stat label="Simulationen" value={o.simulations} hint={lastSim ? `zuletzt ${lastSim.total}/100` : "noch keine"} />
        <Stat label={`Level ${o.level.level}`} value={`${o.xp} XP`} hint="misst Aktivität, nicht Kompetenz" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Kompetenzstand Stufe 1</h2>
            <Link href="/stats/" className="text-sm text-accent hover:underline">Details</Link>
          </div>
          <p className="mb-4 text-xs text-faint">Gemessene Leistung (letzte Versuche, gewichtet) und vorsichtige Einschätzung. „Gesichert“ erst nach richtigem Abruf mit Abstand.</p>
          <ul className="grid gap-3">
            {objectives.map((ob) => (
              <li key={ob.objectiveId} className="grid gap-1.5">
                <div className="flex items-start justify-between gap-3 text-sm">
                  <span className="text-muted">{ob.text}</span>
                  <Badge tone={ob.mastery === "gesichert" ? "success" : ob.mastery === "gefestigt" ? "accent" : "neutral"} className="shrink-0">{MASTERY_LABEL[ob.mastery]}</Badge>
                </div>
                <ProgressBar value={(ob.measuredPerformance ?? 0) / 100} label={`Leistung ${ob.text}`} />
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <h2 className="mb-3 font-semibold">Erfolge</h2>
          <ul className="grid gap-2">
            {ACHIEVEMENTS.map((a) => {
              const got = s.achievements[a.id];
              return (
                <li key={a.id} className={got ? "flex items-center gap-3" : "flex items-center gap-3 opacity-45"}>
                  <span aria-hidden className="grid h-9 w-9 place-items-center rounded-xl border border-line bg-surface text-accent">{a.icon}</span>
                  <span className="text-sm">
                    <span className="font-medium">{a.title}</span>
                    <span className="block text-xs text-faint">{a.description}</span>
                  </span>
                  <span className="sr-only">{got ? "freigeschaltet" : "noch nicht freigeschaltet"}</span>
                </li>
              );
            })}
          </ul>
        </Card>
      </div>

      <Card className="mt-4">
        <h2 className="mb-3 font-semibold">Lernpfad</h2>
        <ol className="flex gap-2 overflow-x-auto pb-1">
          {curriculum.map((c) => (
            <li key={c.id} className="min-w-[150px] flex-1">
              <Link href={`/learn/${c.id}/`} className="block rounded-[var(--radius-sm)] border border-line bg-surface p-3 hover:border-line-strong">
                <span className="text-xs text-faint">Modul {c.number}</span>
                <span className="mt-0.5 block text-sm font-medium leading-snug">{c.title}</span>
                <span className="mt-2 block text-[11px]">{c.status === "verfuegbar" ? <span className="text-success">verfügbar</span> : <span className="text-faint">in Vorbereitung</span>}</span>
              </Link>
            </li>
          ))}
        </ol>
        <p className="mt-3 text-xs text-faint">{scenarios.length} Simulationen verfügbar · weitere Module folgen nach dem Vertical Slice.</p>
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
