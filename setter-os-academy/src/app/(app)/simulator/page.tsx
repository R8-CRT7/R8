"use client";
import Link from "next/link";
import { Badge, Card, Icon, PageHeader } from "@/components/ui";
import { scenarios } from "@/lib/content";
import { useAcademy } from "@/lib/store/storage";

const CHANNEL = { chat: "Website-Chat", telefon_simuliert: "Telefon (simuliert)", instagram_dm: "Instagram-DM", whatsapp: "WhatsApp", email: "E-Mail" } as const;

export default function SimulatorList() {
  const s = useAcademy();
  return (
    <div className="fade-in">
      <PageHeader eyebrow="Chat Simulator" title="Gespräche üben – ohne Risiko">
        Jede Person hat verborgene Informationen. Du erfährst sie nur durch gute Fragen. Danach bewertet der Coach dein Gespräch nach transparenten Kriterien.
      </PageHeader>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {scenarios.map((sc) => {
          const runs = s.simulations.filter((x) => x.scenarioId === sc.id);
          const best = runs.length ? Math.max(...runs.map((r) => r.total)) : null;
          return (
            <Link key={sc.id} href={`/simulator/${sc.id}/`} className="group">
              <Card className="h-full transition-colors group-hover:border-line-strong">
                <div className="flex items-center gap-3">
                  <span aria-hidden className="grid h-11 w-11 place-items-center rounded-full text-sm font-semibold" style={{ background: `hsl(${sc.persona.avatarHue} 60% 50% / 0.18)`, color: `hsl(${sc.persona.avatarHue} 80% 72%)` }}>
                    {sc.persona.name.split(" ").map((p) => p[0]).join("")}
                  </span>
                  <div className="min-w-0">
                    <h2 className="font-semibold leading-tight">{sc.title}</h2>
                    <p className="text-xs text-faint">{sc.archetype}</p>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <Badge>{sc.market}</Badge>
                  <Badge>{sc.direction === "inbound" ? "Inbound" : "Outbound"}</Badge>
                  <Badge>{CHANNEL[sc.channel]}</Badge>
                  <Badge>Stufe {sc.difficulty}</Badge>
                </div>
                <p className="mt-3 line-clamp-3 text-sm text-muted">{sc.industry}</p>
                <div className="mt-4 flex items-center justify-between text-sm">
                  <span className="text-faint">{best === null ? "Noch nicht gespielt" : `Bestwert ${best}/100 · ${runs.length}×`}</span>
                  <Icon name="arrow" className="h-4 w-4 text-accent" />
                </div>
              </Card>
            </Link>
          );
        })}
        <Card className="border-dashed">
          <h2 className="font-semibold">Weitere Szenarien in Vorbereitung</h2>
          <p className="mt-1 text-sm text-muted">Geplant sind ≥ 20 Szenarien, u. a. preisorientierter, skeptischer und zeitknapper Kunde, Recruiting, B2B SaaS, IT-Dienstleistung (siehe SIMULATION_ENGINE.md).</p>
        </Card>
      </div>
    </div>
  );
}
