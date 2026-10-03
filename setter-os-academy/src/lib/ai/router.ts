// Configurable model router with cost estimation and a hard default lock on paid calls.
import { artifactClaudeProvider, proxyProvider } from "./providers";
import { AiError, type AiProvider, type AiRole, type CompletionRequest, type CompletionResult, type ModelTier } from "./types";

/** Anthropic API list prices (USD per 1M tokens), as documented for 2026-09-25. Re-check before enabling paid calls. */
export const PRICE_TABLE: Record<string, { inputPerMTok: number; outputPerMTok: number }> = {
  "claude-opus-5-5": { inputPerMTok: 4, outputPerMTok: 20 },
  "claude-sonnet-5-5": { inputPerMTok: 2, outputPerMTok: 10 },
  "claude-haiku-4-5": { inputPerMTok: 1, outputPerMTok: 5 },
};
export const USD_TO_EUR = 0.92; // assumption for display only

export interface RouterConfig {
  /** Provider order per role; first available provider wins. */
  routes: Record<AiRole, { providers: string[]; tier: ModelTier }>;
  /** Paid calls are locked unless explicitly enabled AND a budget > 0 is set. */
  paidCallsEnabled: boolean;
  monthlyBudgetEur: number;
  proxyModel: string;
}

export const DEFAULT_ROUTER: RouterConfig = {
  routes: {
    customer: { providers: ["claude-artifact", "proxy"], tier: "quick" },
    coach: { providers: ["claude-artifact", "proxy"], tier: "default" },
    hint: { providers: ["claude-artifact", "proxy"], tier: "quick" },
  },
  paidCallsEnabled: false,
  monthlyBudgetEur: 0,
  proxyModel: "claude-opus-5-5",
};

/** German text ≈ 3.5 characters per token (rough estimate for budgeting, not billing). */
export function estimateTokens(chars: number): number {
  return Math.ceil(chars / 3.5);
}

export function estimateCostEur(provider: AiProvider, inputChars: number, outputChars: number): number {
  if (provider.cost.kind !== "per-token") return 0;
  const usd = (estimateTokens(inputChars) * provider.cost.inputPerMTok + estimateTokens(outputChars) * provider.cost.outputPerMTok) / 1_000_000;
  return Math.round(usd * USD_TO_EUR * 10000) / 10000;
}

export interface SpendLog {
  at: number;
  providerId: string;
  role: AiRole;
  inputChars: number;
  outputChars: number;
  costEur: number;
}

export function monthSpend(log: SpendLog[], now: number): number {
  const d = new Date(now);
  return log.filter((l) => {
    const x = new Date(l.at);
    return x.getFullYear() === d.getFullYear() && x.getMonth() === d.getMonth();
  }).reduce((a, l) => a + l.costEur, 0);
}

export function createRouter(opts: {
  config: RouterConfig;
  providers?: AiProvider[];
  spendLog: () => SpendLog[];
  onSpend: (entry: SpendLog) => void;
  now?: () => number;
}) {
  const proxyUrl = typeof process !== "undefined" ? process.env.NEXT_PUBLIC_AI_PROXY_URL : undefined;
  const providers = opts.providers ?? [
    artifactClaudeProvider,
    proxyProvider(proxyUrl, PRICE_TABLE[opts.config.proxyModel] ?? PRICE_TABLE["claude-opus-5-5"]!, opts.config.proxyModel),
  ];
  const byId = new Map(providers.map((p) => [p.id, p]));
  const now = opts.now ?? (() => Date.now());

  function paidAllowed(p: AiProvider, estInputChars: number): boolean {
    if (p.cost.kind !== "per-token") return true;
    if (!opts.config.paidCallsEnabled || opts.config.monthlyBudgetEur <= 0) return false;
    const projected = monthSpend(opts.spendLog(), now()) + estimateCostEur(p, estInputChars, 2000);
    return projected <= opts.config.monthlyBudgetEur;
  }

  async function pick(role: AiRole, estInputChars: number): Promise<{ provider: AiProvider | null; blockedPaid: boolean }> {
    let blockedPaid = false;
    for (const id of opts.config.routes[role].providers) {
      const p = byId.get(id);
      if (!p || !(await p.available())) continue;
      if (!paidAllowed(p, estInputChars)) {
        blockedPaid = true;
        continue;
      }
      return { provider: p, blockedPaid };
    }
    return { provider: null, blockedPaid };
  }

  return {
    async status(role: AiRole) {
      const { provider, blockedPaid } = await pick(role, 4000);
      return { provider: provider ? { id: provider.id, label: provider.label, cost: provider.cost } : null, blockedPaid };
    },
    async complete(req: Omit<CompletionRequest, "tier"> & { tier?: ModelTier }): Promise<CompletionResult & { costEur: number }> {
      const { provider, blockedPaid } = await pick(req.role, req.prompt.length);
      if (!provider)
        throw blockedPaid
          ? new AiError("budget_blocked", "Kostenpflichtige KI-Aufrufe sind gesperrt (Standard). Freigabe und Budget in den Einstellungen nötig.")
          : new AiError("unavailable", "Keine KI verfügbar. Öffne die Akademie über deinen claude.ai-Link oder nutze den Offline-Modus.");
      const res = await provider.complete({ ...req, tier: req.tier ?? opts.config.routes[req.role].tier });
      const costEur = estimateCostEur(provider, res.inputChars, res.outputChars);
      opts.onSpend({ at: now(), providerId: provider.id, role: req.role, inputChars: res.inputChars, outputChars: res.outputChars, costEur });
      return { ...res, costEur };
    },
  };
}
export type AiRouter = ReturnType<typeof createRouter>;
