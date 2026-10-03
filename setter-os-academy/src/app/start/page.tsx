"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Logo, PrototypeBanner } from "@/components/AppShell";
import { Button, Card } from "@/components/ui";
import { newProfile } from "@/lib/store/state";
import { update, useAcademy, useHydrated } from "@/lib/store/storage";

export default function StartPage() {
  const router = useRouter();
  const state = useAcademy();
  const hydrated = useHydrated();
  const [name, setName] = useState("");
  const [ok, setOk] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setError("Bitte gib einen Anzeigenamen ein (Spitzname reicht).");
    if (!ok) return setError("Bitte bestätige den Datenschutzhinweis.");
    update((s) => ({ ...s, profile: newProfile(name, Date.now()) }));
    router.push("/dashboard/");
  }

  return (
    <div className="min-h-dvh">
      <PrototypeBanner />
      <main id="main" className="mx-auto grid max-w-md px-4 py-12">
        <div className="mb-6 flex items-center gap-2"><Logo /><span className="text-sm font-semibold tracking-[0.18em]">SETTER OS</span></div>
        <Card>
          <h1 className="text-2xl font-semibold">Profil anlegen</h1>
          <p className="mt-1 text-sm text-muted">Registrierung im Prototyp: ein lokales Profil auf diesem Gerät – ohne E-Mail, ohne Passwort, ohne Server.</p>
          {hydrated && state.profile && (
            <p className="mt-4 rounded-[var(--radius-sm)] border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
              Auf diesem Gerät gibt es bereits ein Profil („{state.profile.displayName}“). Ein neues Profil ersetzt nur den Namen; der Fortschritt bleibt.
            </p>
          )}
          <form onSubmit={submit} className="mt-6 grid gap-4" noValidate>
            <div>
              <label htmlFor="name" className="mb-1.5 block text-sm font-medium">Anzeigename</label>
              <input
                id="name"
                autoComplete="nickname"
                maxLength={40}
                value={name}
                onChange={(e) => { setName(e.target.value); setError(null); }}
                className="min-h-12 w-full rounded-[var(--radius-sm)] border border-line bg-surface px-3 text-base outline-none focus:border-accent"
                placeholder="z. B. Emi"
                aria-describedby="name-hint"
              />
              <p id="name-hint" className="mt-1 text-xs text-faint">Bitte keinen vollständigen echten Namen nötig.</p>
            </div>
            <label className="flex items-start gap-3 text-sm text-muted">
              <input type="checkbox" checked={ok} onChange={(e) => { setOk(e.target.checked); setError(null); }} className="mt-1 h-5 w-5 accent-[var(--accent)]" />
              <span>
                Ich habe den Datenschutzhinweis gelesen: Lernfortschritt wird nur im Speicher dieses Browsers abgelegt, nicht übertragen und kann in den Einstellungen jederzeit exportiert oder gelöscht werden. In Übungen gebe ich keine echten Kundendaten ein. (Entwurf, Version 2026-10)
              </span>
            </label>
            {error && <p role="alert" className="text-sm text-danger">{error}</p>}
            <Button type="submit" className="min-h-12">Los geht&apos;s</Button>
          </form>
        </Card>
      </main>
    </div>
  );
}
