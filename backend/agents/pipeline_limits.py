"""Pipeline süre sınırları — env ile yapılandırılır."""

from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


# Profiler: LLM confirm edilecek maksimum aday (geri kalanı yüksek statik güvenle geçer)
MAX_PROFILER_LLM_CANDIDATES: int = _int_env("MAX_PROFILER_LLM_CANDIDATES", 35)

# Cerrah: sözel reçete üretilecek maksimum bulgu (en yüksek etki skoruna göre)
MAX_SURGEON_FIXES: int = _int_env("MAX_SURGEON_FIXES", 8)

# Cerrah: tek LLM çağrısında kaç bulgu
SURGEON_BATCH_SIZE: int = _int_env("SURGEON_BATCH_SIZE", 4)

# LLM istek zaman aşımı (saniye) — takılmayı önler
LLM_REQUEST_TIMEOUT_SEC: float = _float_env("LLM_REQUEST_TIMEOUT_SEC", 90)
