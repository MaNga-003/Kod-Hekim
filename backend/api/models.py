"""GET /api/models — sağlayıcı ve model listesi (UI seçici için)."""

from __future__ import annotations

import os

from fastapi import APIRouter

from agents.orchestrator import _DEFAULTS_CEREBRAS, _DEFAULTS_GEMINI
from llm.cerebras_provider import AVAILABLE_MODELS as CEREBRAS_MODELS
from llm.gemini_provider import AVAILABLE_MODELS as GEMINI_MODELS


router = APIRouter(prefix="/api", tags=["models"])


@router.get("/models")
async def list_models() -> dict:
    """Frontend mod/model seçici için sağlayıcı + model listesi.

    Response şeması:
        {
          "providers": {
            "cerebras": {
              "available": bool,
              "models": ["gpt-oss-120b", ...],
              "defaults": {"profiler": "...", ...}
            },
            "gemini": { ... }
          }
        }
    """
    return {
        "providers": {
            "cerebras": {
                "available": bool(os.getenv("CEREBRAS_API_KEY")),
                "models": list(CEREBRAS_MODELS),
                "defaults": dict(_DEFAULTS_CEREBRAS),
            },
            "gemini": {
                "available": bool(os.getenv("GEMINI_API_KEY")),
                "models": list(GEMINI_MODELS),
                "defaults": dict(_DEFAULTS_GEMINI),
            },
        }
    }
