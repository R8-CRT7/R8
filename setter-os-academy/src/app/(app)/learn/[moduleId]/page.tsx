import { curriculum } from "@/lib/content";
import ModuleOverview from "./ModuleOverview";

export function generateStaticParams() {
  return curriculum.map((c) => ({ moduleId: c.id }));
}

export default async function Page({ params }: { params: Promise<{ moduleId: string }> }) {
  const { moduleId } = await params;
  return <ModuleOverview moduleId={moduleId} />;
}
