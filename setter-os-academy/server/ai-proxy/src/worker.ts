// OPTIONAL Cloudflare-Worker-style proxy (fetch handler). NOT deployed.
// Purpose: keep the Anthropic API key server-side and enforce cost limits for a self-hosted build.
// Secrets/vars (set in the hosting dashboard, never in code): ANTHROPIC_API_KEY, ALLOWED_ORIGIN,
// DAILY_REQUEST_LIMIT (e.g. "200"), MODEL (default claude-opus-5-5).
// Daily counter uses an optional KV binding COUNTER; without it only per-request caps apply.
import Anthropic from "@anthropic-ai/sdk";

interface Env {
  ANTHROPIC_API_KEY: string;
  ALLOWED_ORIGIN: string;
  DAILY_REQUEST_LIMIT?: string;
  MODEL?: string;
  COUNTER?: { get(k: string): Promise<string | null>; put(k: string, v: string, o?: { expirationTtl?: number }): Promise<void> };
}

const MAX_TOKENS: Record<string, number> = { customer: 600, hint: 300, coach: 4000 };
const MAX_PROMPT_CHARS = 60_000;

function json(body: unknown, status: number, origin: string) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", "access-control-allow-origin": origin, "access-control-allow-headers": "content-type" } });
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const origin = env.ALLOWED_ORIGIN;
    if (req.method === "OPTIONS") return json({}, 204, origin);
    if (req.method !== "POST" || req.headers.get("origin") !== origin) return json({ error: "forbidden" }, 403, origin);
    const body = (await req.json().catch(() => null)) as { role?: string; prompt?: string } | null;
    const role = body?.role ?? "";
    if (!body?.prompt || !(role in MAX_TOKENS) || body.prompt.length > MAX_PROMPT_CHARS) return json({ error: "bad_request" }, 400, origin);

    if (env.COUNTER) {
      const key = `day:${new Date().toISOString().slice(0, 10)}`;
      const n = Number((await env.COUNTER.get(key)) ?? "0");
      if (n >= Number(env.DAILY_REQUEST_LIMIT ?? "100")) return json({ error: "budget" }, 402, origin);
      await env.COUNTER.put(key, String(n + 1), { expirationTtl: 172800 });
    }

    const client = new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });
    try {
      const msg = await client.beta.messages.create({
        model: env.MODEL ?? "claude-opus-5-5",
        max_tokens: MAX_TOKENS[role]!,
        output_config: { effort: role === "coach" ? "medium" : "low" },
        betas: ["server-side-fallback-2026-07-01"],
        fallbacks: "default",
        messages: [{ role: "user", content: body.prompt }],
      } as never);
      const m = msg as unknown as { stop_reason: string; content: { type: string; text?: string }[] };
      if (m.stop_reason === "refusal") return json({ refused: true }, 200, origin);
      const text = m.content.filter((b) => b.type === "text").map((b) => b.text ?? "").join("");
      return json({ text, truncated: m.stop_reason === "max_tokens" }, 200, origin);
    } catch (e) {
      if (e instanceof Anthropic.RateLimitError) return json({ error: "rate_limited" }, 429, origin);
      if (e instanceof Anthropic.APIError) return json({ error: "upstream" }, 502, origin);
      return json({ error: "upstream" }, 502, origin);
    }
  },
};
