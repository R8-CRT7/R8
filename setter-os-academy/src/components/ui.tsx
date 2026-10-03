// Component library (DESIGN_SYSTEM.md §Komponenten). Small, accessible, token-based.
import Link from "next/link";
import { useId, type ComponentProps, type ReactNode } from "react";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

type Variant = "primary" | "secondary" | "ghost" | "danger";
const btn: Record<Variant, string> = {
  primary: "bg-accent-solid text-accent-ink font-semibold hover:brightness-110 active:brightness-95",
  secondary: "border border-line bg-surface text-fg hover:border-line-strong",
  ghost: "text-muted hover:text-fg hover:bg-surface-strong",
  danger: "border border-danger/50 text-danger hover:bg-danger/10",
};
const base =
  "inline-flex items-center justify-center gap-2 rounded-[var(--radius-sm)] px-4 min-h-11 text-sm transition-[filter,background,border-color,color] duration-[var(--dur)] disabled:opacity-45 disabled:pointer-events-none select-none";

export function Button({ variant = "primary", className, ...p }: ComponentProps<"button"> & { variant?: Variant }) {
  return <button {...p} className={cx(base, btn[variant], className)} />;
}

export function ButtonLink({ variant = "primary", className, ...p }: ComponentProps<typeof Link> & { variant?: Variant }) {
  return <Link {...p} className={cx(base, btn[variant], className)} />;
}

export function Card({ className, children, ...p }: ComponentProps<"section">) {
  return (
    <section {...p} className={cx("glass rounded-[var(--radius)] p-5", className)}>
      {children}
    </section>
  );
}

export function Badge({ tone = "neutral", children, className }: { tone?: "neutral" | "accent" | "success" | "warning" | "danger"; children: ReactNode; className?: string }) {
  const t = {
    neutral: "text-muted border-line",
    accent: "text-accent border-accent/40 bg-accent/10",
    success: "text-success border-success/40 bg-success/10",
    warning: "text-warning border-warning/40 bg-warning/10",
    danger: "text-danger border-danger/40 bg-danger/10",
  }[tone];
  return <span className={cx("inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium", t, className)}>{children}</span>;
}

export function ProgressBar({ value, label, className }: { value: number; label: string; className?: string }) {
  const v = Math.max(0, Math.min(1, value));
  return (
    <div className={className}>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(v * 100)}
        className="h-2 w-full overflow-hidden rounded-full bg-surface-strong"
      >
        <div className="h-full rounded-full bg-accent transition-[width] duration-500" style={{ width: `${v * 100}%` }} />
      </div>
    </div>
  );
}

export function Ring({ value, size = 76, label, children }: { value: number; size?: number; label: string; children?: ReactNode }) {
  const r = (size - 10) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(1, value));
  const gid = `ring-${useId().replace(/:/g, "")}`;
  return (
    <div className="relative inline-grid place-items-center" style={{ width: size, height: size }} role="img" aria-label={`${label}: ${Math.round(v * 100)} %`}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <defs>
          <linearGradient id={gid} x1="0" x2="1">
            <stop offset="0" stopColor="var(--accent)" />
            <stop offset="1" stopColor="var(--accent)" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-strong)" strokeWidth="8" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={`url(#${gid})`} strokeWidth="8" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - v)} className="transition-[stroke-dashoffset] duration-700" />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-sm font-semibold">{children}</div>
    </div>
  );
}

export function PageHeader({ eyebrow, title, children, actions }: { eyebrow?: string; title: string; children?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-accent">{eyebrow}</p>}
        <h1 className="font-[family-name:var(--font-display)] text-[1.7rem] font-semibold leading-tight tracking-[-0.02em] sm:text-[2.1rem]">{title}</h1>
        {children && <div className="mt-2 max-w-2xl text-sm text-muted sm:text-base">{children}</div>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </header>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-[var(--radius-sm)] border border-line bg-surface p-3">
      <div className="text-xs text-faint">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-faint">{hint}</div>}
    </div>
  );
}

export function Callout({ tone, title, children }: { tone: "info" | "warn" | "legal" | "ethics"; title: string; children: ReactNode }) {
  const map = {
    info: ["border-accent/40", "text-accent", "ℹ"],
    warn: ["border-warning/40", "text-warning", "!"],
    legal: ["border-accent-2/40", "text-accent-2", "§"],
    ethics: ["border-success/40", "text-success", "◇"],
  } as const;
  const [b, t, i] = map[tone];
  return (
    <aside className={cx("rounded-[var(--radius)] border bg-surface p-4", b)}>
      <p className={cx("mb-1 flex items-center gap-2 text-sm font-semibold", t)}>
        <span aria-hidden className="grid h-5 w-5 place-items-center rounded-full border border-current text-[11px]">{i}</span>
        {title}
      </p>
      <div className="prose-lesson text-sm text-muted">{children}</div>
    </aside>
  );
}

export function Icon({ name, className = "h-5 w-5" }: { name: IconName; className?: string }) {
  const d = ICONS[name];
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      {d}
    </svg>
  );
}
export type IconName = keyof typeof ICONS;
const ICONS = {
  home: <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />,
  path: (<><circle cx="6" cy="18" r="2.5" /><circle cx="18" cy="6" r="2.5" /><path d="M8.5 18H15a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h6.5" /></>),
  chat: <path d="M4 5h16v11H8l-4 4z" />,
  repeat: (<><path d="M4 12a8 8 0 0 1 13.7-5.7L20 8.5" /><path d="M20 4v4.5h-4.5" /><path d="M20 12a8 8 0 0 1-13.7 5.7L4 15.5" /><path d="M4 20v-4.5h4.5" /></>),
  chart: (<><path d="M4 20V10" /><path d="M10 20V4" /><path d="M16 20v-7" /><path d="M22 20H2" /></>),
  tree: (<><circle cx="12" cy="5" r="2" /><circle cx="6" cy="19" r="2" /><circle cx="18" cy="19" r="2" /><path d="M12 7v5m0 0-6 5m6-5 6 5" /></>),
  book: <path d="M4 4h6a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4zM20 4h-6a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h6z" />,
  user: (<><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>),
  gear: (<><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1A2 2 0 1 1 4.3 17l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1A2 2 0 1 1 7 4.3l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1A2 2 0 1 1 19.7 7l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></>),
  shield: <path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z" />,
  trophy: (<><path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0z" /><path d="M17 5h3a3 3 0 0 1-3 4M7 5H4a3 3 0 0 0 3 4" /></>),
  check: <path d="m5 12 4.5 4.5L19 7" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
  back: <path d="M19 12H5m6 6-6-6 6-6" />,
  lock: (<><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>),
  spark: <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6" />,
  send: <path d="M4 12 20 4l-6 16-3-7z" />,
  alert: (<><path d="M12 3 2 20h20z" /><path d="M12 10v4M12 17h.01" /></>),
  layers: (<><path d="m12 3 9 5-9 5-9-5z" /><path d="m3 13 9 5 9-5" /></>),
};
