import { modules } from "@/lib/content";
import QuizRunner from "./QuizRunner";

export function generateStaticParams() {
  return modules.map((m) => ({ moduleId: m.id }));
}

export default async function Page({ params }: { params: Promise<{ moduleId: string }> }) {
  const { moduleId } = await params;
  return <QuizRunner moduleId={moduleId} />;
}
