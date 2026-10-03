// Single-file entry for the private artifact build. Reuses all pages and engines of the Next.js app.
import "../app/globals.css";
import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { AppShell } from "@/components/AppShell";
import { ThemeSync, themeBootScript } from "@/components/ThemeSync";
import { getState } from "@/lib/store/storage";
import { setInitial, useLocation } from "./router";
import Landing from "../app/page";
import StartPage from "../app/start/page";
import LoginPage from "../app/login/page";
import Dashboard from "../app/(app)/dashboard/page";
import PlanPage from "../app/(app)/plan/page";
import LearningPath from "../app/(app)/learn/page";
import ModuleOverview from "../app/(app)/learn/[moduleId]/ModuleOverview";
import LessonView from "../app/(app)/learn/[moduleId]/[lessonId]/LessonView";
import QuizRunner from "../app/(app)/quiz/[moduleId]/QuizRunner";
import SimulatorList from "../app/(app)/simulator/page";
import ChatSimulator from "../app/(app)/simulator/[scenarioId]/ChatSimulator";
import ReviewCenter from "../app/(app)/review/ReviewCenter";
import Stats from "../app/(app)/stats/page";
import Skills from "../app/(app)/skills/page";
import ExamArea from "../app/(app)/exam/page";
import Sources from "../app/(app)/sources/page";
import Profile from "../app/(app)/profile/page";
import SettingsPage from "../app/(app)/settings/page";
import Admin from "../app/(app)/admin/page";
import { curriculum, modules, quizById, scenarios } from "@/lib/content";

function resolve(path: string): { node: ReactNode; shell: boolean } {
  const p = path.split("?")[0]!;
  const seg = p.split("/").filter(Boolean);
  const [a, b, c] = seg;
  if (!a) return { node: <Landing />, shell: false };
  if (a === "start") return { node: <StartPage />, shell: false };
  if (a === "login") return { node: <LoginPage />, shell: false };
  const simple: Record<string, () => ReactNode> = {
    dashboard: () => <Dashboard />,
    plan: () => <PlanPage />,
    simulator: () => <SimulatorList />,
    review: () => <ReviewCenter />,
    stats: () => <Stats />,
    skills: () => <Skills />,
    exam: () => <ExamArea />,
    sources: () => <Sources />,
    profile: () => <Profile />,
    settings: () => <SettingsPage />,
    admin: () => <Admin />,
  };
  if (a === "learn") {
    if (!b) return { node: <LearningPath />, shell: true };
    if (!curriculum.some((x) => x.id === b)) return { node: <Dashboard />, shell: true };
    if (!c) return { node: <ModuleOverview moduleId={b} />, shell: true };
    const m = modules.find((x) => x.id === b);
    if (m?.lessons.some((l) => l.id === c)) return { node: <LessonView moduleId={b} lessonId={c} />, shell: true };
    return { node: <ModuleOverview moduleId={b} />, shell: true };
  }
  if (a === "quiz" && b && quizById(b)) return { node: <QuizRunner moduleId={b} />, shell: true };
  if (a === "simulator" && b && scenarios.some((s) => s.id === b)) return { node: <ChatSimulator scenarioId={b} />, shell: true };
  return { node: (simple[a] ?? simple.dashboard!)(), shell: true };
}

function App() {
  const path = useLocation();
  const { node, shell } = resolve(path);
  const keyed = <div key={path}>{node}</div>;
  return (
    <>
      <ThemeSync />
      {shell ? <AppShell>{keyed}</AppShell> : keyed}
    </>
  );
}

// eslint-disable-next-line no-new-func
try { new Function(themeBootScript)(); } catch { /* ignore */ }
let hasProfile = false;
try { hasProfile = !!getState().profile; } catch { /* ignore */ }
setInitial(hasProfile ? "/dashboard/" : "/");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
