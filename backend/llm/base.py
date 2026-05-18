"""LLM Provider arayüzü.

KodHekim 2 sağlayıcı destekler: Cerebras (hızlı multi-model) ve Gemini (1M context).
Ajan kodu doğrudan provider'a karşı yazılır; sağlayıcı/model UI'dan seçilir.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, TypedDict


class LLMResponse(TypedDict):
    """LLM çağrısının dönüş şeması — tüm sağlayıcılar bunu üretir."""

    text: str
    json: Optional[dict]
    tokens_used: int
    model: str
    latency_ms: int


class LLMError(Exception):
    """LLM çağrısı başarısız oldu (auth, network, rate limit, vs.)."""


class LLMRateLimitError(LLMError):
    """Rate limit hit — exponential backoff retry sonrası hâlâ başarısız."""


class LLMResponseError(LLMError):
    """Sağlayıcı yanıt verdi ama içerik beklenenden farklı (boş, parse edilemeyen, vs.)."""


class LLMProvider(ABC):
    """Tüm sağlayıcılar bu arayüzü implemente eder.

    Concrete implementasyonlar:
        - `CerebrasProvider` (cerebras_provider.py)
        - `GeminiProvider`   (gemini_provider.py)
    """

    name: str  # ör. "cerebras", "gemini"

    @abstractmethod
    def list_models(self) -> list[str]:
        """Sağlayıcının desteklediği model ID'lerini döndür."""

    @abstractmethod
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
        """Tek-shot completion.

        Args:
            prompt: User mesajı.
            model: Sağlayıcının `list_models()` listesinden bir ID.
            temperature: Sıcaklık (0.0-2.0).
            json_schema: Verilirse structured output zorlanır; cevap `json` alanına parse edilir.
            max_tokens: Output cap.
            system: System mesajı (verilmezse atlanır).

        Raises:
            LLMError ve alt sınıfları.
        """
