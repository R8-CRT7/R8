"""OpenAI provider (optional dependency: `pip install smart360[openai]`).

Implemented against the official `openai` SDK Chat Completions API with strict
json_schema response_format. Unit tested with a fake client; not live-tested
(no key available during development) - see docs/FINAL_STATUS.md.
"""

from __future__ import annotations

import base64
import time
from typing import Any

from smart360.ai.base import SYSTEM_PROMPT, AIProvider, ProviderError, ProviderInfo, build_user_text
from smart360.ai.schema import (
    SOLVE_JSON_SCHEMA,
    SchemaViolation,
    SolveRequest,
    SolveResult,
    parse_solve_response,
)


class OpenAIProvider(AIProvider):
    info = ProviderInfo(
        id="openai",
        display_name="OpenAI",
        default_model="gpt-6-luna",
        models=("gpt-6-luna", "gpt-6.1-sol", "gpt-6-astra"),
        key_name="OPENAI_API_KEY",
        pricing={},  # not verified - cost tracking shows tokens only
    )

    def __init__(
        self, api_key: str | None, model: str | None = None, timeout_s: float = 30.0, client: Any = None
    ):
        super().__init__(api_key, model, timeout_s)
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import openai
            except ImportError as e:
                raise ProviderError("OpenAI SDK not installed (pip install openai)", False, "config") from e
            self._client = openai.OpenAI(api_key=self.api_key, timeout=self.timeout_s, max_retries=0)
        return self._client

    def solve_question(self, req: SolveRequest) -> SolveResult:
        if not self.api_key:
            raise ProviderError("OpenAI API key missing", retryable=False, kind="config")
        client = self._get_client()
        content: list[dict[str, Any]] = [{"type": "text", "text": build_user_text(req)}]
        for png in (req.image_png, req.question_png, req.answers_png):
            if png:
                url = "data:image/png;base64," + base64.standard_b64encode(png).decode("ascii")
                content.append({"type": "image_url", "image_url": {"url": url}})
        t0 = time.perf_counter()
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "solve_question", "schema": SOLVE_JSON_SCHEMA, "strict": True},
                },
            )
        except Exception as e:
            raise _map_openai_error(e) from e
        latency = (time.perf_counter() - t0) * 1000
        choice = resp.choices[0]
        if getattr(choice.message, "refusal", None):
            raise ProviderError("Model declined the request", retryable=False, kind="refusal")
        try:
            parsed = parse_solve_response(choice.message.content or "", len(req.answers), req.number_question)
        except SchemaViolation as e:
            raise ProviderError(str(e), retryable=True, kind="invalid") from e
        usage = getattr(resp, "usage", None)
        return SolveResult(
            parsed,
            getattr(resp, "model", self.model),
            self.info.id,
            latency,
            int(getattr(usage, "prompt_tokens", 0) or 0),
            int(getattr(usage, "completion_tokens", 0) or 0),
        )


def _map_openai_error(e: Exception) -> ProviderError:
    try:
        import openai
    except ImportError:
        return ProviderError(str(e), True, "network")
    if isinstance(e, openai.AuthenticationError | openai.PermissionDeniedError):
        return ProviderError("Invalid OpenAI API key", False, "auth")
    if isinstance(e, openai.RateLimitError):
        return ProviderError("Rate limited", True, "rate_limit")
    if isinstance(e, openai.APITimeoutError):
        return ProviderError("Request timed out", True, "timeout")
    if isinstance(e, openai.APIConnectionError):
        return ProviderError("Network error", True, "network")
    if isinstance(e, openai.BadRequestError | openai.NotFoundError):
        return ProviderError(f"Bad request: {e}", False, "invalid")
    if isinstance(e, openai.APIStatusError):
        return ProviderError(f"Server error {e.status_code}", e.status_code >= 500, "server")
    return ProviderError(f"Unexpected error: {type(e).__name__}", True, "error")
