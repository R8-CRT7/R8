import { allQuizIds } from "@/lib/content";
import QuizRunner from "./QuizRunner";

export function generateStaticParams() {
  return allQuizIds().map((id) => ({ moduleId: id }));
}

export default async function Page({ params }: { params: Promise<{ moduleId: string }> }) {
  const { moduleId } = await params;
  return <QuizRunner moduleId={moduleId} />;
}
