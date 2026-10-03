import { scenarios } from "@/lib/content";
import ChatSimulator from "./ChatSimulator";

export function generateStaticParams() {
  return scenarios.map((s) => ({ scenarioId: s.id }));
}

export default async function Page({ params }: { params: Promise<{ scenarioId: string }> }) {
  const { scenarioId } = await params;
  return <ChatSimulator scenarioId={scenarioId} />;
}
