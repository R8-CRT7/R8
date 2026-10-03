"use client";
import { useState } from "react";
import { FreeChat } from "@/components/ai/FreeChat";
import { useAiRouter } from "@/components/ai/useAi";
import { Badge, Card, Icon } from "@/components/ui";
import { scenarioById } from "@/lib/content";
import ChatSimulator from "./ChatSimulator";

/** Entry point for a scenario: free-text AI conversation or the offline choice-based training. */
export default function ScenarioEntry({ scenarioId }: { scenarioId: string }) {
  const sc = scenarioById(scenarioId)!;
  const [choice, setChoice] = useState<"free" | "offline" | null>(null);
  const ai = useAiRouter();
  if (choice === "free" && sc.ai) return <FreeChat sc={sc} onExit={() => setChoice(null)} />;
  if (choice === "offline") return <ChatSimulator scenarioId={scenarioId} />;
  return (
    <div className="fade-in mx-auto max-w-2xl">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">Gesprächstraining</p>
      <h1 className="mt-1 mb-4 font-[family-name:var(--font-display)] text-2xl font-semibold">{sc.title}</h1>
      <div className="grid gap-3">
        <button disabled={!sc.ai} onClick={() => setChoice("free")} className="text-left disabled:opacity-50">
          <Card className="transition-colors hover:border-accent/60">
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-semibold">KI-Gespräch mit freier Eingabe</h2>
              {ai.status === "ready" ? <Badge tone="success">verfügbar</Badge> : ai.status === "checking" ? <Badge>prüfe …</Badge> : <Badge tone="warning">nur im claude.ai-Viewer</Badge>}
            </div>
            <p className="mt-1 text-sm text-muted">Du schreibst deine Nachrichten selbst. Ein KI-Kunde reagiert auf den echten Verlauf, ein getrennter KI-Coach wertet aus. Lern-, Praxis- oder Prüfungsmodus.</p>
          </Card>
        </button>
        <button onClick={() => setChoice("offline")} className="text-left">
          <Card className="transition-colors hover:border-line-strong">
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-semibold">Offline-Training mit Antwortauswahl</h2>
              <Badge>immer verfügbar</Badge>
            </div>
            <p className="mt-1 text-sm text-muted">Regelbasiert, ohne KI und ohne Internet. Du wählst aus vorgegebenen Nachrichten; die Bewertung folgt festen Regeln.</p>
          </Card>
        </button>
      </div>
      <p className="mt-4 flex items-start gap-2 text-xs text-faint"><Icon name="shield" className="h-4 w-4 shrink-0" /> Nur erfundene Personen. Gespräche bleiben auf diesem Gerät und lassen sich in den Einstellungen löschen.</p>
    </div>
  );
}
