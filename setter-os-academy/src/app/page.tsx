import Link from "next/link";
import { Logo, PrototypeBanner } from "@/components/AppShell";
import { ButtonLink, Icon } from "@/components/ui";
import { curriculum, questions, scenarios } from "@/lib/content";

export default function Landing() {
  const features = [
    { icon: "chat" as const, title: "Gesprächssimulator", text: "Realistische Interessenten mit verborgenen Informationen. Du musst die richtigen Fragen stellen." },
    { icon: "spark" as const, title: "Nachvollziehbares Coaching", text: "Gewichtete Kriterien, harte Grenzen für Druck und falsche Versprechen, konkrete Beispielantworten." },
    { icon: "repeat" as const, title: "Wiederholung mit System", text: "Abrufübungen, verteilte und vermischte Wiederholung – transparent erklärt." },
    { icon: "shield" as const, title: "Seriös statt manipulativ", text: "Ein Nein ist ein Nein. Rechtliche Grenzen von UWG und DSGVO sind Teil jeder Lektion." },
  ];
  return (
    <div className="min-h-dvh">
      <PrototypeBanner />
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
        <div className="flex items-center gap-2.5">
          <Logo size={30} />
          <span className="text-sm font-semibold tracking-[0.2em]">SETTER OS ACADEMY</span>
        </div>
        <Link href="/login/" className="min-tap grid place-items-center text-sm text-muted hover:text-fg">Anmelden</Link>
      </header>

      <main id="main" className="mx-auto max-w-6xl px-4 sm:px-6">
        <section className="py-14 sm:py-24">
          <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs text-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" /> Deine persönliche Ausbildung · kostenlos · Modul 1 verfügbar
          </p>
          <h1 className="max-w-3xl font-[family-name:var(--font-display)] text-4xl font-semibold leading-[1.08] tracking-tight sm:text-6xl">
            <span className="gradient-text">Learn the skill.</span>
            <br />
            Master the conversation.
          </h1>
          <p className="mt-6 max-w-2xl text-base text-muted sm:text-lg">
            Eine interaktive Ausbildungsplattform für Appointment Setting, Chat Setting und Inbound Sales – mit
            Lektionen, Abrufübungen und einem Kundensimulator, der ehrliche, gute Gesprächsführung belohnt.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <ButtonLink href="/start/" className="px-6">
              Prototyp ausprobieren <Icon name="arrow" className="h-4 w-4" />
            </ButtonLink>
            <ButtonLink href="/login/" variant="secondary">Ich habe schon ein Profil</ButtonLink>
          </div>
          <dl className="mt-12 grid max-w-xl grid-cols-3 gap-3">
            {[
              [curriculum.length, "Module geplant"],
              [questions.length, "geprüfte Fragen"],
              [scenarios.length, "Simulationen"],
            ].map(([n, l]) => (
              <div key={l as string} className="glass rounded-[var(--radius)] p-4">
                <dt className="text-xs text-faint">{l}</dt>
                <dd className="text-2xl font-semibold tabular-nums">{n}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="grid gap-4 pb-16 sm:grid-cols-2 lg:grid-cols-4" aria-label="Funktionen">
          {features.map((f) => (
            <article key={f.title} className="glass rounded-[var(--radius)] p-5">
              <div className="mb-3 grid h-10 w-10 place-items-center rounded-xl bg-accent/10 text-accent"><Icon name={f.icon} /></div>
              <h2 className="font-semibold">{f.title}</h2>
              <p className="mt-1 text-sm text-muted">{f.text}</p>
            </article>
          ))}
        </section>

        <section className="glass mb-16 rounded-[var(--radius-lg)] p-6 sm:p-8">
          <h2 className="text-lg font-semibold">Ehrlich gesagt</h2>
          <ul className="mt-3 grid gap-2 text-sm text-muted sm:grid-cols-2">
            <li>• Dies ist ein privater, nichtkommerzieller Prototyp. Es gibt keine Bezahlung und keine Anmeldung bei einem Server.</li>
            <li>• Keine Einkommens- oder Erfolgsversprechen. Keine erfundenen Bewertungen.</li>
            <li>• Ein internes Abschlusszertifikat wäre keine staatlich anerkannte Qualifikation.</li>
            <li>• Rechtliche Inhalte sind Lernmaterial, keine Rechtsberatung. Stand: Oktober 2026.</li>
          </ul>
        </section>
      </main>
      <footer className="border-t border-line py-6 text-center text-xs text-faint">
        SETTER OS ACADEMY (Arbeitstitel) · Prototyp · Impressum und Datenschutzerklärung liegen als Entwurf vor und werden vor einer Veröffentlichung geprüft.
      </footer>
    </div>
  );
}
