"""Anthropic Claude provider (official `anthropic` SDK, structured outputs)."""

from __future__ import annotations

import base64
import time
from typing import Any

from smart360.ai.base import SYSTEM_PROMPT, AIProvider, ProviderError, ProviderInfo, build_user_text
from smart360.ai.schema import SOLVE_JSON_SCHEMA, SchemaViolation, SolveRequest, SolveResult, parse_solve_response

_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider(AIProvider):
    info = ProviderInfo(
        id="anthropic",
        display_name="Anthropic Claude",
        default_model="claude-opus-5-5",
        models=("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"),
        key_name="ANTHROPIC_API_KEY",
        pricing={
            "claude-opus-5-5": (4.0, 20.0),
            "claude-sonnet-5-5": (2.0, 10.0),
            "claude-haiku-4-5": (1.0, 5.0),
        },
    )

    def __init__(self, api_key: str | None, model: str | None = None, timeout_s: float = 30.0,
                 effort: str = "low", client: Any = None):
        super().__init__(api_key, model, timeout_s)
        self.effort = effort
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            # SDK retries disabled: our ResilientSolver owns retry/backoff/circuit breaking
            self._client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout_s, max_retries=0)
        return self._client

    def _content(self, req: SolveRequest) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        for png in (req.image_png, req.question_png, req.answers_png):
            if png:
                blocks.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png",
                               "data": base64.standard_b64encode(png).decode("ascii")},
                })
        blocks.append({"type": "text", "text": build_user_text(req)})
        return blocks

    def _request_kwargs(self, req: SolveRequest) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4000,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": self._content(req)}],
            "output_config": {"format": {"type": "json_schema", "schema": SOLVE_JSON_SCHEMA}},
        }
        if self.model != "claude-haiku-4-5":
            # effort is not supported on Haiku 4.5
            kwargs["output_config"]["effort"] = self.effort
        if self.model in ("claude-opus-5-5", "claude-sonnet-5-5"):
            # server-side refusal fallback (Anthropic's recommended default routing)
            kwargs["betas"] = [_FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        return kwargs

    def solve_question(self, req: SolveRequest) -> SolveResult:
        if not self.api_key:
            raise ProviderError("Anthropic API key missing", retryable=False, kind="config")
        import anthropic

        client = self._get_client()
        t0 = time.perf_counter()
        try:
            kwargs = self._request_kwargs(req)
            if "betas" in kwargs:
                resp = client.beta.messages.create(**kwargs)
            else:
                resp = client.messages.create(**kwargs)
        except anthropic.AuthenticationError as e:
            raise ProviderError("Invalid Anthropic API key", retryable=False, kind="auth") from e
        except anthropic.PermissionDeniedError as e:
            raise ProviderError("API key lacks permission", retryable=False, kind="auth") from e
        except anthropic.NotFoundError as e:
            raise ProviderError(f"Unknown model {self.model}", retryable=False, kind="config") from e
        except anthropic.RateLimitError as e:
            ra = e.response.headers.get("retry-after") if e.response is not None else None
            raise ProviderError("Rate limited", retryable=True, kind="rate_limit",
                                retry_after=float(ra) if ra else None) from e
        except anthropic.BadRequestError as e:
            raise ProviderError(f"Bad request: {e.message}", retryable=False, kind="invalid") from e
        except anthropic.APITimeoutError as e:
            raise ProviderError("Request timed out", retryable=True, kind="timeout") from e
        except anthropic.APIConnectionError as e:
            raise ProviderError("Network error", retryable=True, kind="network") from e
        except anthropic.APIStatusError as e:
            raise ProviderError(f"Server error {e.status_code}", retryable=e.status_code >= 500,
                                kind="server") from e
        latency = (time.perf_counter() - t0) * 1000

        if getattr(resp, "stop_reason", None) == "refusal":
            raise ProviderError("Model declined the request", retryable=False, kind="refusal")
        if getattr(resp, "stop_reason", None) == "max_tokens":
            raise ProviderError("Response truncated", retryable=True, kind="invalid")
        text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), None)
        if text is None:
            raise ProviderError("No text block in response", retryable=True, kind="invalid")
        try:
            parsed = parse_solve_response(text, len(req.answers), req.number_question)
        except SchemaViolation as e:
            raise ProviderError(str(e), retryable=True, kind="invalid") from e
        usage = getattr(resp, "usage", None)
        return SolveResult(
            response=parsed,
            model=getattr(resp, "model", self.model),
            provider=self.info.id,
            latency_ms=latency,
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        )
