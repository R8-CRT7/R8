// Provider adapters. No API key ever lives in the client bundle.
import { AiError, type AiProvider, type CompletionRequest, type CompletionResult, type ModelTier } from "./types";

type SampleFn = ((input: string, opts?: Record<string, unknown>) => Promise<{ text: string; truncated: boolean; modelTierApplied?: ModelTier }>) & Record<string, unknown>;
interface ClaudeRuntime {
  use(name: string): Promise<unknown>;
}

function claudeRuntime(): ClaudeRuntime | null {
  if (typeof window === "undefined") return null;
  const c = (window as unknown as { claude?: ClaudeRuntime }).claude;
  return c && typeof c.use === "function" ? c : null;
}

let samplePromise: Promise<SampleFn | null> | null = null;
function getSample(): Promise<SampleFn | null> {
  if (!samplePromise) {
    const rt = claudeRuntime();
    samplePromise = rt ? (rt.use("sample") as Promise<SampleFn | null>).catch(() => null) : Promise.resolve(null);
  }
  return samplePromise;
}
/** test hook */
export function resetProviderCache() {
  samplePromise = null;
}

const SAMPLE_ERROR_MAP: Record<string, AiError["code"]> = {
  not_granted: "not_granted",
  sampling_disabled: "unavailable",
  not_declared: "unavailable",
  capability_disabled: "unavailable",
  capability_removed: "unavailable",
  rate_limited: "rate_limited",
  cancelled: "cancelled",
  refused: "refused",
  empty_completion: "invalid_output",
  session_expired: "unavailable",
};

/**
 * Claude via the claude.ai artifact runtime (`sample` capability). Runs on the viewer's own Claude
 * account: no API key, no server, no separate bill. Only available when the page is opened inside
 * the claude.ai viewer and the viewer allows it (consent prompt on first call).
 */
export const artifactClaudeProvider: AiProvider = {
  id: "claude-artifact",
  label: "Claude (über dein Claude-Konto, im claude.ai-Viewer)",
  cost: { kind: "claude-plan" },
  async available() {
    return (await getSample()) !== null;
  },
  async complete(req: CompletionRequest): Promise<CompletionResult> {
    const sample = await getSample();
    if (!sample) throw new AiError("unavailable", "Claude ist in dieser Ansicht nicht verfügbar.");
    try {
      const r = await sample(req.prompt, {
        modelTier: req.tier,
        cache: false, // every chat turn must be a fresh answer
        signal: req.signal,
        onText: req.onText ? ({ text }: { text: string }) => req.onText!(text) : undefined,
      });
      return {
        text: r.text,
        truncated: !!r.truncated,
        providerId: this.id,
        tierApplied: r.modelTierApplied ?? req.tier,
        inputChars: req.prompt.length,
        outputChars: r.text.length,
      };
    } catch (e) {
      const err = e as { code?: string; message?: string; text?: string };
      throw new AiError(SAMPLE_ERROR_MAP[err.code ?? ""] ?? "upstream_error", err.message ?? "Unbekannter Fehler", err.text);
    }
  },
};

/**
 * Optional self-hosted proxy (see server/ai-proxy). Disabled unless NEXT_PUBLIC_AI_PROXY_URL is set
 * at build time AND the learner enabled paid calls with a budget > 0. The proxy holds the API key.
 * Note: the claude.ai artifact viewer blocks requests to other hosts, so this only works in a
 * self-hosted build of the app.
 */
export function proxyProvider(url: string | undefined, prices: { inputPerMTok: number; outputPerMTok: number }, model: string): AiProvider {
  return {
    id: "proxy",
    label: `Eigener Proxy (${model}, kostenpflichtig)`,
    cost: { kind: "per-token", ...prices },
    async available() {
      return !!url;
    },
    async complete(req) {
      if (!url) throw new AiError("unavailable", "Kein Proxy konfiguriert.");
      let res: Response;
      try {
        res = await fetch(url, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ role: req.role, tier: req.tier, prompt: req.prompt }),
          signal: req.signal,
        });
      } catch (e) {
        if ((e as Error).name === "AbortError") throw new AiError("cancelled", "Abgebrochen");
        throw new AiError("upstream_error", "Proxy nicht erreichbar.");
      }
      if (res.status === 429) throw new AiError("rate_limited", "Proxy-Limit erreicht.");
      if (res.status === 402) throw new AiError("budget_blocked", "Tagesbudget des Proxys erreicht.");
      if (!res.ok) throw new AiError("upstream_error", `Proxy-Fehler ${res.status}`);
      const data = (await res.json()) as { text?: string; truncated?: boolean; refused?: boolean };
      if (data.refused) throw new AiError("refused", "Anfrage abgelehnt.");
      if (!data.text) throw new AiError("invalid_output", "Leere Antwort.");
      req.onText?.(data.text);
      return { text: data.text, truncated: !!data.truncated, providerId: "proxy", tierApplied: req.tier, inputChars: req.prompt.length, outputChars: data.text.length };
    },
  };
}
