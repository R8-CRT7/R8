"""Provider registry / factory."""

from __future__ import annotations

from smart360.ai.anthropic_provider import AnthropicProvider
from smart360.ai.base import AIProvider, ProviderInfo
from smart360.ai.gemini_provider import GeminiProvider
from smart360.ai.mock_provider import MockProvider
from smart360.ai.openai_provider import OpenAIProvider

PROVIDERS: dict[str, type[AIProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "mock": MockProvider,
}


def provider_infos() -> list[ProviderInfo]:
    return [cls.info for cls in PROVIDERS.values()]


def create_provider(provider_id: str, api_key: str | None, model: str | None, timeout_s: float) -> AIProvider:
    cls = PROVIDERS.get(provider_id)
    if cls is None:
        raise KeyError(f"unknown provider {provider_id}")
    if cls is MockProvider:
        return MockProvider()
    return cls(api_key, model, timeout_s)
