"use client";
import { useState } from "react";

/** 14-day learning activity: single series bar chart (one hue, recessive grid, per-bar hover + table view). */
export function ActivityChart({ days }: { days: { date: Date; count: number }[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(4, ...days.map((d) => d.count));
  const W = 560;
  const H = 150;
  const padB = 22;
  const padT = 18;
  const bw = W / days.length;
  const y = (v: number) => H - padB - (v / max) * (H - padB - padT);
  const ticks = [0, Math.round(max / 2), max];
  const fmt = (d: Date) => d.toLocaleDateString("de-DE", { weekday: "short", day: "numeric" });
  return (
    <figure>
      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Beantwortete Fragen pro Tag, letzte 14 Tage">
          {ticks.map((t) => (
            <g key={t}>
              <line x1="0" x2={W} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeWidth="1" />
              <text x="2" y={y(t) - 3} fontSize="10" fill="var(--text-faint)">{t}</text>
            </g>
          ))}
          {days.map((d, i) => {
            const h = H - padB - y(d.count);
            const x = i * bw + bw * 0.22;
            const w = bw * 0.56;
            return (
              <g key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)} tabIndex={0} aria-label={`${fmt(d.date)}: ${d.count} Fragen`}>
                <rect x={i * bw} y={padT} width={bw} height={H - padT - padB} fill="transparent" />
                {d.count > 0 && <path d={`M${x},${H - padB} v${-(h - 4)} q0,-4 4,-4 h${w - 8} q4,0 4,4 v${h - 4} z`} fill={hover === i ? "var(--accent-2)" : "var(--accent)"} />}
                {(i % 2 === 0 || i === days.length - 1) && <text x={i * bw + bw / 2} y={H - 6} fontSize="10" textAnchor="middle" fill="var(--text-faint)">{d.date.getDate()}.</text>}
              </g>
            );
          })}
        </svg>
        {hover !== null && (
          <div className="pointer-events-none absolute -top-2 rounded-md border border-line bg-elev px-2 py-1 text-xs shadow" style={{ left: `${((hover + 0.5) / days.length) * 100}%`, transform: "translateX(-50%)" }}>
            {fmt(days[hover]!.date)}: <span className="font-semibold tabular-nums">{days[hover]!.count}</span> Fragen
          </div>
        )}
      </div>
      <figcaption className="sr-only">
        <table><thead><tr><th>Tag</th><th>Fragen</th></tr></thead><tbody>{days.map((d, i) => <tr key={i}><td>{fmt(d.date)}</td><td>{d.count}</td></tr>)}</tbody></table>
      </figcaption>
    </figure>
  );
}
