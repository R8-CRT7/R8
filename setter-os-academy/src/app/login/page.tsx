"use client";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Logo, PrototypeBanner } from "@/components/AppShell";
import { Button, ButtonLink, Card } from "@/components/ui";
import { importJson, useAcademy, useHydrated } from "@/lib/store/storage";

export default function LoginPage() {
  const router = useRouter();
  const state = useAcademy();
  const hydrated = useHydrated();
  const file = useRef<HTMLInputElement>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function onImport(f: File) {
    try {
      importJson(await f.text());
      router.push("/dashboard/");
    } catch {
      setMsg("Die Datei konnte nicht gelesen werden. Bitte eine Sicherung aus den Einstellungen verwenden.");
    }
  }

  return (
    <div className="min-h-dvh">
      <PrototypeBanner />
      <main id="main" className="mx-auto grid max-w-md px-4 py-12">
        <div className="mb-6 flex items-center gap-2"><Logo /><span className="text-sm font-semibold tracking-[0.18em]">SETTER OS</span></div>
        <Card>
          <h1 className="text-2xl font-semibold">Anmelden</h1>
          <p className="mt-1 text-sm text-muted">
            Der Prototyp hat noch keine Cloud-Konten. Dein Profil liegt auf diesem Gerät. Für ein anderes Gerät kannst du eine Sicherung importieren.
            Echte Anmeldung (E-Mail/Passkey via Supabase Auth) ist vorbereitet, aber erst nach Freigabe aktiv.
          </p>
          <div className="mt-6 grid gap-3">
            {hydrated && state.profile ? (
              <ButtonLink href="/dashboard/" className="min-h-12">Weiter als „{state.profile.displayName}“</ButtonLink>
            ) : (
              <ButtonLink href="/start/" className="min-h-12">Neues Profil anlegen</ButtonLink>
            )}
            <Button variant="secondary" className="min-h-12" onClick={() => file.current?.click()}>Sicherung importieren (.json)</Button>
            <input ref={file} type="file" accept="application/json" className="hidden" onChange={(e) => e.target.files?.[0] && onImport(e.target.files[0])} />
            {msg && <p role="alert" className="text-sm text-danger">{msg}</p>}
          </div>
        </Card>
      </main>
    </div>
  );
}
