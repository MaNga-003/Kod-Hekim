"""Cerebras Cloud SDK üzerinden LLM sağlayıcısı (developer.md §2.2)."""

from __future__ import annotations

import os
import time
from typing import Optional

from llm.base import (
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponse,
    LLMResponseError,
)
from llm.safe_json import safe_json_parse


# developer.md §2.2 — 27 Mayıs 2026'da deprecate olacak modeller MVP boyunca çalışır.
AVAILABLE_MODELS: list[str] = [
    "gpt-oss-120b",
    "llama3.1-8b",
    "qwen-3-235b-a22b-instruct-2507",
    "zai-glm-4.7",
]


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "rate" in msg
        or "429" in msg
        or "quota" in msg
        or "too many" in msg
    )


class CerebrasProvider(LLMProvider):
    name = "cerebras"

    def __init__(self, api_key: Optional[str] = None) -> None:
        # SDK import'u lazy — testlerde mock'lanabilir, ayrıca import-time hata
        # tüm app'i indirmesin.
        from cerebras.cloud.sdk import Cerebras  # type: ignore[import-untyped]

        key = api_key or os.getenv("CEREBRAS_API_KEY")
        if not key:
            raise LLMError("CEREBRAS_API_KEY .env içinde tanımlı değil.")
        self.client = Cerebras(api_key=key)

    def list_models(self) -> list[str]:
        return list(AVAILABLE_MODELS)

    def complete(
        self,
        prompt: str,
        model: str,
        *,
        temperature: float = 0.2,
        json_schema: Optional[dict] = None,
        max_tokens: int = 4096,
        system: Optional[str] = None,
    ) -> LLMResponse:
        if model not in AVAILABLE_MODELS:
            # Cerebras zaman zaman alias kabul ediyor; uyar ama dene.
            pass

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }
        if json_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "out", "strict": True, "schema": json_schema},
            }

        last_exc: Optional[Exception] = None
        delays = [0.5, 1.5, 4.0]  # 3 retry, exponential-ish
        for attempt in range(len(delays) + 1):
            try:
                start = time.monotonic()
                resp = self.client.chat.completions.create(**kwargs)
                latency_ms = int((time.monotonic() - start) * 1000)
                break
            except Exception as e:
                last_exc = e
                if not _is_rate_limit(e):
                    raise LLMError(f"Cerebras complete failed: {e}") from e
                if attempt < len(delays):
                    time.sleep(delays[attempt])
                    continue
                raise LLMRateLimitError(f"Cerebras rate limit, 3 retry sonrası: {e}") from e
        else:  # pragma: no cover
            raise LLMError(f"Beklenmedik retry akışı: {last_exc}")

        # Yanıt çıkarımı
        try:
            text = resp.choices[0].message.content or ""
            tokens = getattr(resp.usage, "total_tokens", 0) or 0
        except (AttributeError, IndexError) as e:
            raise LLMResponseError(f"Cerebras response şekli beklenmedik: {e}") from e

        parsed_json = safe_json_parse(text) if json_schema else None

        return LLMResponse(
            text=text,
            json=parsed_json,
            tokens_used=tokens,
            model=model,
            latency_ms=latency_ms,
        )
