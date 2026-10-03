"use client";
import { Badge, Card, PageHeader, ProgressBar, Stat } from "@/components/ui";
import { competencyAverages, ERROR_LABEL, errorAnalysis, objectiveSummaries, overview } from "@/lib/derived";
import { useAcademy } from "@/lib/store/storage";

const M = { nicht_geprueft: "nicht geprüft", im_aufbau: "im Aufbau", gefestigt: "gefestigt", gesichert: "gesichert" } as const;

export default function Stats() {
  const s = useAcademy();
  const o = overview(s, Date.now());
  const objs = objectiveSummaries(s);
  const errs = errorAnalysis(s);
  const comps = competencyAverages(s);
  const maxErr = errs[0]?.[1] ?? 1;
  return (
    <div className="fade-in">
      <PageHeader eyebrow="Lernstatistiken & Fehleranalyse" title="Was du kannst – und was noch nicht">
        Gemessene Leistung (Antworten, Simulationen) wird getrennt von der geschätzten Kompetenz angezeigt. XP und Logins fließen nicht in die Kompetenz ein.
      </PageHeader>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Antworten" value={o.answered} />
        <Stat label="Trefferquote" value={o.accuracy === null ? "–" : `${Math.round(o.accuracy * 100)} %`} />
        <Stat label="Simulationen" value={o.simulations} />
        <Stat label="Aktive Tage (7)" value={o.activeDays} />
      </div>

      <Card className="mt-4">
        <h2 className="mb-3 font-semibold">Lernziele</h2>
        <div className="-mx-2 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="text-xs text-faint">
              <tr><th className="p-2 font-medium">Lernziel</th><th className="p-2 font-medium">Versuche</th><th className="p-2 font-medium">Richtig/Falsch</th><th className="p-2 font-medium">Leistung (gemessen)</th><th className="p-2 font-medium">Ø Zeit</th><th className="p-2 font-medium">Sicherheit</th><th className="p-2 font-medium">Einschätzung</th></tr>
            </thead>
            <tbody>
              {objs.map((x) => (
                <tr key={x.objectiveId} className="border-t border-line align-top">
                  <td className="p-2 text-muted">{x.text}</td>
                  <td className="p-2 tabular-nums">{x.attempts}</td>
                  <td className="p-2 tabular-nums">{x.correct}/{x.wrong}</td>
                  <td className="p-2 tabular-nums">{x.measuredPerformance === null ? "–" : `${x.measuredPerformance} %`}</td>
                  <td className="p-2 tabular-nums">{x.avgDurationMs === null ? "–" : `${Math.round(x.avgDurationMs / 1000)} s`}</td>
                  <td className="p-2 text-xs">{x.calibrationGap === null ? "–" : x.calibrationGap > 0.2 ? <span className="text-warning">eher überschätzt</span> : x.calibrationGap < -0.2 ? <span className="text-accent">eher unterschätzt</span> : <span className="text-success">gut kalibriert</span>}</td>
                  <td className="p-2"><Badge tone={x.mastery === "gesichert" ? "success" : x.mastery === "gefestigt" ? "accent" : "neutral"}>{M[x.mastery]}</Badge><p className="mt-1 max-w-[200px] text-[11px] text-faint">{x.masteryReason}</p></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 font-semibold">Fehleranalyse</h2>
          {errs.length === 0 ? <p className="text-sm text-muted">Noch keine Fehler erfasst.</p> : (
            <ul className="grid gap-3">
              {errs.map(([c, n]) => (
                <li key={c} className="grid gap-1 text-sm">
                  <div className="flex justify-between"><span className="text-muted">{ERROR_LABEL[c]}</span><span className="tabular-nums">{n}</span></div>
                  <ProgressBar value={n / maxErr} label={ERROR_LABEL[c]} />
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <h2 className="mb-3 font-semibold">Simulationskompetenzen (Ø)</h2>
          {s.simulations.length === 0 ? <p className="text-sm text-muted">Noch keine Simulation abgeschlossen.</p> : (
            <ul className="grid gap-3">
              {comps.map((c) => (
                <li key={c.id} className="grid gap-1 text-sm">
                  <div className="flex justify-between"><span className="text-muted">{c.label}</span><span className="tabular-nums">{c.avg === null ? "nicht geprüft" : `${c.avg} (n=${c.n})`}</span></div>
                  {c.avg !== null && <ProgressBar value={c.avg / 100} label={c.label} />}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
