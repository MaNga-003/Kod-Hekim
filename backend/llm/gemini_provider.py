"""Google Gemini SDK üzerinden LLM sağlayıcısı (developer.md §2.3)."""

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


AVAILABLE_MODELS: list[str] = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
]


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "rate" in msg
        or "429" in msg
        or "resource" in msg and "exhausted" in msg
        or "quota" in msg
    )


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: Optional[str] = None) -> None:
        # Lazy import — test izolasyonu için
        import google.generativeai as genai  # type: ignore[import-untyped]

        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise LLMError("GEMINI_API_KEY .env içinde tanımlı değil.")
        genai.configure(api_key=key)
        self._genai = genai

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
        model_kwargs: dict = {}
        if system:
            model_kwargs["system_instruction"] = system

        m = self._genai.GenerativeModel(model, **model_kwargs)

        config: dict = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if json_schema:
            config["response_mime_type"] = "application/json"
            config["response_schema"] = json_schema

        last_exc: Optional[Exception] = None
        delays = [0.5, 1.5, 4.0]
        for attempt in range(len(delays) + 1):
            try:
                start = time.monotonic()
                resp = m.generate_content(prompt, generation_config=config)
                latency_ms = int((time.monotonic() - start) * 1000)
                break
            except Exception as e:
                last_exc = e
                if not _is_rate_limit(e):
                    raise LLMError(f"Gemini complete failed: {e}") from e
                if attempt < len(delays):
                    time.sleep(delays[attempt])
                    continue
                raise LLMRateLimitError(f"Gemini rate limit, 3 retry sonrası: {e}") from e
        else:  # pragma: no cover
            raise LLMError(f"Beklenmedik retry akışı: {last_exc}")

        try:
            text = resp.text or ""
        except (AttributeError, ValueError) as e:
            # Safety filter ile blok edilmiş yanıtlar resp.text okunamaz hale getiriyor
            raise LLMResponseError(f"Gemini yanıt metni okunamadı: {e}") from e

        try:
            tokens = int(resp.usage_metadata.total_token_count)
        except (AttributeError, TypeError):
            tokens = 0

        parsed_json = safe_json_parse(text) if json_schema else None

        return LLMResponse(
            text=text,
            json=parsed_json,
            tokens_used=tokens,
            model=model,
            latency_ms=latency_ms,
        )
