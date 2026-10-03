import { scenarios } from "@/lib/content";
import ScenarioEntry from "./ScenarioEntry";

export function generateStaticParams() {
  return scenarios.map((s) => ({ scenarioId: s.id }));
}

export default async function Page({ params }: { params: Promise<{ scenarioId: string }> }) {
  const { scenarioId } = await params;
  return <ScenarioEntry scenarioId={scenarioId} />;
}
