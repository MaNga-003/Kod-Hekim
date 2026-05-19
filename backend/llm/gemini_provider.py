"""Google Gemini REST API üzerinden LLM sağlayıcısı (grpc SDK yok — Windows uyumlu)."""

from __future__ import annotations

import os
import time
from typing import Any, Optional

import httpx

from llm.base import (
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponse,
    LLMResponseError,
)
from llm.gemini_schema import sanitize_json_schema_for_gemini
from llm.safe_json import safe_json_parse
from llm.timeout import run_with_timeout


AVAILABLE_MODELS: list[str] = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _normalize_model(model: str) -> str:
    return model if model.startswith("models/") else f"models/{model}"


def _is_rate_limit(status: int, msg: str) -> bool:
    if status == 429:
        return True
    low = msg.lower()
    return "rate" in low or "quota" in low or "resource exhausted" in low


def _extract_text(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        block = (data.get("promptFeedback") or {}).get("blockReason")
        if block:
            raise LLMResponseError(f"Gemini istek engellendi: {block}")
        raise LLMResponseError("Gemini boş yanıt döndürdü.")

    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
    text = "".join(texts).strip()
    if not text:
        finish = candidates[0].get("finishReason")
        raise LLMResponseError(f"Gemini yanıt metni yok (finishReason={finish}).")
    return text


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: Optional[str] = None) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise LLMError("GEMINI_API_KEY .env içinde tanımlı değil.")
        self._api_key = key
        try:
            timeout = float(os.getenv("LLM_REQUEST_TIMEOUT_SEC", "90"))
        except ValueError:
            timeout = 90.0
        self._timeout = timeout

    def list_models(self) -> list[str]:
        return list(AVAILABLE_MODELS)

    def _request(
        self,
        model: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{_API_BASE}/{_normalize_model(model)}:generateContent"
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(url, params={"key": self._api_key}, json=body)
        if resp.status_code >= 400:
            detail = resp.text[:500]
            try:
                detail = resp.json().get("error", {}).get("message", detail)
            except Exception:
                pass
            if _is_rate_limit(resp.status_code, str(detail)):
                raise LLMRateLimitError(f"Gemini rate limit: {detail}")
            raise LLMError(f"Gemini HTTP {resp.status_code}: {detail}")
        return resp.json()

    def _build_body(
        self,
        prompt: str,
        *,
        temperature: float,
        max_tokens: int,
        json_schema: Optional[dict],
        system: Optional[str],
        use_schema: bool,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_schema:
            body["generationConfig"]["responseMimeType"] = "application/json"
            if use_schema:
                body["generationConfig"]["responseSchema"] = sanitize_json_schema_for_gemini(
                    json_schema
                )
        return body

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
        delays = [0.5, 1.5, 4.0]
        last_exc: Optional[Exception] = None

        for attempt in range(len(delays) + 1):
            for use_schema in (True, False) if json_schema else (False,):
                try:
                    body = self._build_body(
                        prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        json_schema=json_schema,
                        system=system,
                        use_schema=use_schema,
                    )
                    start = time.monotonic()
                    data = self._request(model, body)
                    latency_ms = int((time.monotonic() - start) * 1000)
                    text = _extract_text(data)
                    tokens = int((data.get("usageMetadata") or {}).get("totalTokenCount") or 0)
                    parsed_json = safe_json_parse(text) if json_schema else None
                    return LLMResponse(
                        text=text,
                        json=parsed_json,
                        tokens_used=tokens,
                        model=model,
                        latency_ms=latency_ms,
                    )
                except LLMRateLimitError:
                    raise
                except LLMError as e:
                    last_exc = e
                    # Schema reddedildiyse schema'sız JSON modunda tekrar dene
                    if use_schema and json_schema and "schema" in str(e).lower():
                        continue
                    if attempt < len(delays) and _is_rate_limit(0, str(e)):
                        time.sleep(delays[attempt])
                        break
                    raise
                except LLMResponseError:
                    raise
                except Exception as e:
                    raise LLMError(f"Gemini complete failed: {e}") from e

        raise LLMRateLimitError(f"Gemini rate limit, 3 retry sonrası: {last_exc}")
