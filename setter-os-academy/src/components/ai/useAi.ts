"use client";
import { useEffect, useMemo, useState } from "react";
import { createRouter, DEFAULT_ROUTER, type AiRouter } from "@/lib/ai/router";
import { addSpend } from "@/lib/store/state";
import { getState, update, useAcademy } from "@/lib/store/storage";

/** Router bound to the learner's settings; spend is logged locally. */
export function useAiRouter(): { router: AiRouter; status: "checking" | "ready" | "unavailable" | "blocked"; providerLabel: string | null; costKind: string | null } {
  const s = useAcademy();
  const router = useMemo(
    () =>
      createRouter({
        config: { ...DEFAULT_ROUTER, paidCallsEnabled: s.ai.paidCallsEnabled, monthlyBudgetEur: s.ai.monthlyBudgetEur },
        spendLog: () => getState().ai.spendLog,
        onSpend: (e) => update((st) => addSpend(st, e)),
      }),
    [s.ai.paidCallsEnabled, s.ai.monthlyBudgetEur],
  );
  const [status, setStatus] = useState<"checking" | "ready" | "unavailable" | "blocked">("checking");
  const [label, setLabel] = useState<string | null>(null);
  const [costKind, setCostKind] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    router.status("customer").then((st) => {
      if (!alive) return;
      setLabel(st.provider?.label ?? null);
      setCostKind(st.provider?.cost.kind ?? null);
      setStatus(st.provider ? "ready" : st.blockedPaid ? "blocked" : "unavailable");
    });
    return () => {
      alive = false;
    };
  }, [router]);
  return { router, status, providerLabel: label, costKind };
}

/** Height of the visible viewport (shrinks when the iOS keyboard opens). */
export function useVisualViewportHeight(): { height: number; offsetTop: number } | null {
  const [h, setH] = useState<{ height: number; offsetTop: number } | null>(null);
  useEffect(() => {
    const vv = window.visualViewport;
    const read = () => setH({ height: vv ? vv.height : window.innerHeight, offsetTop: vv ? vv.offsetTop : 0 });
    read();
    vv?.addEventListener("resize", read);
    vv?.addEventListener("scroll", read);
    window.addEventListener("resize", read);
    return () => {
      vv?.removeEventListener("resize", read);
      vv?.removeEventListener("scroll", read);
      window.removeEventListener("resize", read);
    };
  }, []);
  return h;
}
