// AI layer types. The customer simulator and the coach are two independent roles that
// only share this transport layer – never prompts, state or outputs.

export type AiRole = "customer" | "coach" | "hint";
export type ModelTier = "quick" | "default" | "complex";

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface CompletionRequest {
  role: AiRole;
  /** Complete, self-contained prompt (providers are stateless). */
  prompt: string;
  tier: ModelTier;
  signal?: AbortSignal;
  onText?: (text: string) => void;
}

export interface CompletionResult {
  text: string;
  truncated: boolean;
  providerId: string;
  tierApplied: ModelTier;
  inputChars: number;
  outputChars: number;
}

export type AiErrorCode =
  | "unavailable" // provider cannot run in this view
  | "not_granted" // viewer declined
  | "rate_limited"
  | "budget_blocked" // paid call blocked by budget/lock
  | "cancelled"
  | "invalid_output" // model answered, but not in the required format
  | "refused"
  | "upstream_error";

export class AiError extends Error {
  constructor(
    public code: AiErrorCode,
    message: string,
    public partial?: string,
  ) {
    super(message);
  }
}

export type CostModel =
  /** Uses the viewer's own Claude plan inside the claude.ai artifact viewer – no API key, no separate bill. */
  | { kind: "claude-plan" }
  /** Pay per token via an optional self-hosted proxy. Prices in USD per 1M tokens. */
  | { kind: "per-token"; inputPerMTok: number; outputPerMTok: number }
  | { kind: "free" };

export interface AiProvider {
  id: string;
  label: string;
  cost: CostModel;
  /** Resolves false when the provider cannot run in this environment. */
  available(): Promise<boolean>;
  complete(req: CompletionRequest): Promise<CompletionResult>;
}
