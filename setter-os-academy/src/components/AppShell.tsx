"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useId, type ReactNode } from "react";
import { Icon, cx, type IconName } from "./ui";
import { useAcademy, useHydrated } from "@/lib/store/storage";
import { levelFor } from "@/lib/engine/gamification";
import { totalXp } from "@/lib/store/state";
import { ButtonLink } from "./ui";

const PRIMARY: { href: string; label: string; icon: IconName }[] = [
  { href: "/dashboard/", label: "Start", icon: "home" },
  { href: "/plan/", label: "Plan", icon: "path" },
  { href: "/simulator/", label: "Simulator", icon: "chat" },
  { href: "/review/", label: "Wiederholen", icon: "repeat" },
  { href: "/stats/", label: "Statistik", icon: "chart" },
];
const SECONDARY: { href: string; label: string; icon: IconName }[] = [
  { href: "/learn/", label: "Module", icon: "book" },
  { href: "/skills/", label: "Skill Tree", icon: "tree" },
  { href: "/exam/", label: "Prüfungen", icon: "trophy" },
  { href: "/sources/", label: "Quellen", icon: "book" },
  { href: "/profile/", label: "Profil", icon: "user" },
  { href: "/settings/", label: "Einstellungen", icon: "gear" },
  { href: "/admin/", label: "Admin", icon: "shield" },
];

export function PrototypeBanner() {
  return (
    <div role="note" className="border-b border-warning/30 bg-warning/10 px-4 py-1.5 text-center text-[12px] text-warning">
      Nichtkommerzieller Prototyp · privater Test · keine Rechts- oder Steuerberatung · Daten bleiben auf diesem Gerät
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname() ?? "/";
  const state = useAcademy();
  const hydrated = useHydrated();
  const xp = totalXp(state);
  const lvl = levelFor(xp);
  const active = (href: string) => path === href || path.startsWith(href);

  return (
    <div className="min-h-dvh">
      <PrototypeBanner />
      <div className="mx-auto flex max-w-[1400px]">
        {/* Desktop sidebar */}
        <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col border-r border-line px-4 py-6 lg:flex" aria-label="Hauptnavigation">
          <Link href="/dashboard/" className="mb-8 flex items-center gap-2.5 px-2">
            <Logo />
            <span className="text-sm font-semibold tracking-[0.18em]">SETTER OS</span>
          </Link>
          <nav className="flex flex-col gap-1">
            {[...PRIMARY, ...SECONDARY].map((i, idx) => (
              <div key={i.href}>
                {idx === PRIMARY.length && <div className="my-3 h-px bg-line" />}
                <Link
                  href={i.href}
                  aria-current={active(i.href) ? "page" : undefined}
                  className={cx(
                    "flex min-h-10 items-center gap-3 rounded-[var(--radius-sm)] px-3 text-sm transition-colors",
                    active(i.href) ? "bg-surface-strong text-fg shadow-[inset_2px_0_0_var(--accent)]" : "text-muted hover:bg-surface hover:text-fg",
                  )}
                >
                  <Icon name={i.icon} className="h-[18px] w-[18px]" />
                  {i.label}
                </Link>
              </div>
            ))}
          </nav>
          {hydrated && state.profile && (
            <div className="mt-auto rounded-[var(--radius)] border border-line bg-surface p-3">
              <div className="text-xs text-faint">Level {lvl.level}</div>
              <div className="text-sm font-medium">{lvl.title}</div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-strong">
                <div className="h-full bg-[linear-gradient(90deg,var(--accent),var(--accent-2))]" style={{ width: `${lvl.progress * 100}%` }} />
              </div>
              <div className="mt-1 text-[11px] text-faint">{xp} XP · Level misst Aktivität, nicht Kompetenz</div>
            </div>
          )}
        </aside>

        <div className="min-w-0 flex-1">
          {/* Mobile top bar */}
          <header className="sticky top-[env(safe-area-inset-top,0px)] z-20 flex items-center justify-between border-b border-line bg-[color-mix(in_srgb,var(--bg)_82%,transparent)] px-4 py-3 backdrop-blur-xl lg:hidden">
            <Link href="/dashboard/" className="flex items-center gap-2">
              <Logo />
              <span className="text-xs font-semibold tracking-[0.18em]">SETTER OS</span>
            </Link>
            <details className="relative">
              <summary className="min-tap grid cursor-pointer list-none place-items-center rounded-full text-muted hover:text-fg" aria-label="Weitere Bereiche">
                <Icon name="layers" />
              </summary>
              <nav className="glass absolute right-0 z-30 mt-2 w-56 rounded-[var(--radius)] p-2" aria-label="Weitere Bereiche">
                {SECONDARY.map((i) => (
                  <Link key={i.href} href={i.href} className="flex min-h-11 items-center gap-3 rounded-[var(--radius-sm)] px-3 text-sm text-muted hover:bg-surface-strong hover:text-fg">
                    <Icon name={i.icon} className="h-[18px] w-[18px]" />
                    {i.label}
                  </Link>
                ))}
              </nav>
            </details>
          </header>

          <main id="main" className="px-4 pb-28 pt-6 sm:px-6 lg:px-10 lg:pb-12 lg:pt-10">
            {!hydrated ? (
              <div className="h-40 animate-pulse rounded-[var(--radius)] bg-surface" aria-busy="true" aria-label="Lädt" />
            ) : state.profile ? (
              children
            ) : (
              <NoProfile />
            )}
          </main>
        </div>
      </div>

      {/* Mobile bottom tab bar – 44px+ targets, safe area aware */}
      <nav className="pb-safe fixed inset-x-0 bottom-0 z-30 border-t border-line bg-[color-mix(in_srgb,var(--bg)_88%,transparent)] px-2 pt-1.5 backdrop-blur-xl lg:hidden" aria-label="Hauptnavigation mobil">
        <ul className="grid grid-cols-5">
          {PRIMARY.map((i) => (
            <li key={i.href}>
              <Link
                href={i.href}
                aria-current={active(i.href) ? "page" : undefined}
                className={cx("flex min-h-12 flex-col items-center justify-center gap-0.5 rounded-xl text-[11px]", active(i.href) ? "text-accent" : "text-faint")}
              >
                <Icon name={i.icon} className="h-[22px] w-[22px]" />
                {i.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}

function NoProfile() {
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <h1 className="text-2xl font-semibold">Noch kein Lernprofil</h1>
      <p className="mt-2 text-muted">Lege ein lokales Profil an, um deinen Fortschritt zu speichern. Es bleibt auf diesem Gerät.</p>
      <div className="mt-6 flex justify-center gap-2">
        <ButtonLink href="/start/">Profil anlegen</ButtonLink>
        <ButtonLink href="/login/" variant="secondary">Anmelden</ButtonLink>
      </div>
    </div>
  );
}

export function Logo({ size = 26 }: { size?: number }) {
  // Unique gradient id per instance: a hidden (display:none) duplicate must not swallow the gradient.
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--accent)" />
          <stop offset="1" stopColor="var(--accent-2)" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="30" height="30" rx="9" fill={`url(#${id})`} opacity="0.18" />
      <rect x="1" y="1" width="30" height="30" rx="9" fill="none" stroke={`url(#${id})`} strokeWidth="1.5" />
      <path d="M9 19.5c0 2 2 3.5 5 3.5h4a4 4 0 0 0 0-8h-4a4 4 0 0 1 0-8h4c3 0 5 1.5 5 3.5" fill="none" stroke={`url(#${id})`} strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}
