import { modules } from "@/lib/content";
import LessonView from "./LessonView";

export function generateStaticParams() {
  return modules.flatMap((m) => m.lessons.map((l) => ({ moduleId: m.id, lessonId: l.id })));
}

export default async function Page({ params }: { params: Promise<{ moduleId: string; lessonId: string }> }) {
  const { moduleId, lessonId } = await params;
  return <LessonView moduleId={moduleId} lessonId={lessonId} />;
}
