"""Google Gemini provider (optional dependency: `pip install smart360[gemini]`).

Uses google-genai `models.generate_content` with a JSON response schema. Unit tested
with a fake client; not live-tested (no key during development).
"""

from __future__ import annotations

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


class GeminiProvider(AIProvider):
    info = ProviderInfo(
        id="gemini",
        display_name="Google Gemini",
        default_model="gemini-3.8-flash",
        models=("gemini-3.8-flash", "gemini-3.1-flash-lite"),
        key_name="GEMINI_API_KEY",
        pricing={},
    )

    def __init__(
        self, api_key: str | None, model: str | None = None, timeout_s: float = 30.0, client: Any = None
    ):
        super().__init__(api_key, model, timeout_s)
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google import genai
                from google.genai import types
            except ImportError as e:
                raise ProviderError("google-genai SDK not installed", False, "config") from e
            self._client = genai.Client(
                api_key=self.api_key, http_options=types.HttpOptions(timeout=int(self.timeout_s * 1000))
            )
        return self._client

    def solve_question(self, req: SolveRequest) -> SolveResult:
        if not self.api_key:
            raise ProviderError("Gemini API key missing", retryable=False, kind="config")
        client = self._get_client()
        from google.genai import errors, types

        parts: list[Any] = [
            types.Part.from_bytes(data=png, mime_type="image/png")
            for png in (req.image_png, req.question_png, req.answers_png)
            if png
        ]
        parts.append(build_user_text(req))
        t0 = time.perf_counter()
        try:
            resp = client.models.generate_content(
                model=self.model,
                contents=parts,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_json_schema=SOLVE_JSON_SCHEMA,
                ),
            )
        except errors.ClientError as e:
            code = getattr(e, "code", 400)
            if code in (401, 403):
                raise ProviderError("Invalid Gemini API key", False, "auth") from e
            if code == 429:
                raise ProviderError("Rate limited", True, "rate_limit") from e
            raise ProviderError(f"Bad request ({code})", False, "invalid") from e
        except errors.ServerError as e:
            raise ProviderError("Gemini server error", True, "server") from e
        except (TimeoutError, ConnectionError, OSError) as e:
            raise ProviderError("Network error", True, "network") from e
        latency = (time.perf_counter() - t0) * 1000
        try:
            parsed = parse_solve_response(resp.text or "", len(req.answers), req.number_question)
        except SchemaViolation as e:
            raise ProviderError(str(e), retryable=True, kind="invalid") from e
        um = getattr(resp, "usage_metadata", None)
        return SolveResult(
            parsed,
            self.model,
            self.info.id,
            latency,
            int(getattr(um, "prompt_token_count", 0) or 0),
            int(getattr(um, "candidates_token_count", 0) or 0),
        )
