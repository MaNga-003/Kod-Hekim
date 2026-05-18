"""Sağlayıcı seçici + ajan→model default eşlemesi."""

from __future__ import annotations

import os
from typing import Literal, Optional

from llm.base import LLMError, LLMProvider


ProviderName = Literal["cerebras", "gemini"]
AgentRole = Literal["profiler", "impact", "surgeon", "chief", "deep_mode"]


# .env'deki defaults eşlemesi (developer.md §10)
_ENV_KEYS: dict[ProviderName, dict[AgentRole, str]] = {
    "cerebras": {
        "profiler": "CEREBRAS_DEFAULT_PROFILER",
        "impact": "CEREBRAS_DEFAULT_IMPACT",
        "surgeon": "CEREBRAS_DEFAULT_SURGEON",
        "chief": "CEREBRAS_DEFAULT_CHIEF",
        "deep_mode": "CEREBRAS_DEFAULT_DEEP",
    },
    "gemini": {
        "profiler": "GEMINI_DEFAULT_PROFILER",
        "impact": "GEMINI_DEFAULT_IMPACT",
        "surgeon": "GEMINI_DEFAULT_SURGEON",
        "chief": "GEMINI_DEFAULT_CHIEF",
        "deep_mode": "GEMINI_DEFAULT_DEEP",
    },
}

# Hard fallback'ler — .env eksikse de çalışsın
_HARD_DEFAULTS: dict[ProviderName, dict[AgentRole, str]] = {
    "cerebras": {
        "profiler": "gpt-oss-120b",
        "impact": "gpt-oss-120b",
        "surgeon": "zai-glm-4.7",
        "chief": "qwen-3-235b-a22b-instruct-2507",
        "deep_mode": "qwen-3-235b-a22b-instruct-2507",
    },
    "gemini": {
        "profiler": "gemini-2.5-flash",
        "impact": "gemini-2.5-flash",
        "surgeon": "gemini-2.5-pro",
        "chief": "gemini-2.5-pro",
        "deep_mode": "gemini-2.5-pro",
    },
}


def get_provider(name: ProviderName, *, api_key: Optional[str] = None) -> LLMProvider:
    """`"cerebras"` veya `"gemini"` string'inden provider örneği üret."""
    if name == "cerebras":
        from llm.cerebras_provider import CerebrasProvider

        return CerebrasProvider(api_key=api_key)
    if name == "gemini":
        from llm.gemini_provider import GeminiProvider

        return GeminiProvider(api_key=api_key)
    raise LLMError(f"Bilinmeyen provider: {name}")


def default_model(provider: ProviderName, role: AgentRole) -> str:
    """Bir ajan rolü için varsayılan model. Önce env, sonra hard fallback."""
    env_key = _ENV_KEYS[provider][role]
    return os.getenv(env_key) or _HARD_DEFAULTS[provider][role]


def resolve_model(
    provider: ProviderName,
    role: AgentRole,
    *,
    override: Optional[str] = None,
) -> str:
    """UI'dan gelen override > env default > hard default sırasıyla."""
    return override or default_model(provider, role)


def list_supported() -> dict[str, list[str]]:
    """`/api/models` endpoint'inin döndüreceği yapı (provider → model listesi)."""
    from llm.cerebras_provider import AVAILABLE_MODELS as CEREBRAS_MODELS
    from llm.gemini_provider import AVAILABLE_MODELS as GEMINI_MODELS

    return {
        "cerebras": list(CEREBRAS_MODELS),
        "gemini": list(GEMINI_MODELS),
    }
