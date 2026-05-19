"""Mod karşılaştırma tahmini (developer.md §16.3).

Gerçek olarak çalıştırılan mod için ölçülen metrikleri kullanır; diğer iki
mod için sabit çarpan tabanlı tahmin yapar. Kullanıcı "Statik / Hibrit / Derin"
karelerini yan yana görür.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Iterable, Literal, Optional

from agents.orchestrator import Event


Mode = Literal["static", "hybrid", "deep"]


@dataclass
class ModeMetrics:
    mode: Mode
    estimated_seconds: float
    estimated_tokens: int
    estimated_issues: int
    is_actual: bool  # True = ölçülen, False = tahmin

    def to_dict(self) -> dict:
        return asdict(self)


# Dosya başına tahmin çarpanları — kabaca kalibre (developer.md §16.3 notu:
# MVP sonrası 5 örnek repo üzerinde refine edilir).
_TIME_PER_FILE_SEC: dict[str, float] = {
    "static": 0.05,
    "hybrid": 1.2,
    "deep": 6.0,
}

_TOKENS_PER_FILE: dict[str, int] = {
    "static": 0,
    "hybrid": 2_000,
    "deep": 15_000,
}

# Statik motor tüm aday'ları döndürür; LLM confirm bir kısmını eler;
# Derin LLM bazı bilinmedik bulgular katar, bazı bilinen pattern'leri kaçırır.
_ISSUE_MULTIPLIER: dict[str, float] = {
    "static": 1.0,
    "hybrid": 0.70,
    "deep": 0.90,
}


def _parse_ts(ts: str) -> datetime:
    """ISO-Z formatlı string'i datetime'a çevir."""
    s = ts.rstrip("Z")
    if "+" not in s and "-" not in s[10:]:
        s = s + "+00:00"
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def compute_actual_metrics(events: Iterable[Event]) -> dict:
    """Pipeline event listesinden gerçek metrikleri çıkar.

    Token sayısı şu an event'lerde yok (LLM provider tarafından döndürülen
    `tokens_used` toplanmıyor) — şimdilik 0 kabul; gelecek sürümde event
    payload'ına eklenebilir.
    """
    events = list(events)
    if not events:
        return {"seconds": 0.0, "tokens": 0, "issues": 0}
    try:
        start = _parse_ts(events[0].timestamp)
        end = _parse_ts(events[-1].timestamp)
        seconds = max(0.0, (end - start).total_seconds())
    except Exception:  # noqa: BLE001
        seconds = 0.0
    issues = sum(1 for e in events if e.type == "issue_found")
    return {"seconds": seconds, "tokens": 0, "issues": issues}


def estimate_modes(
    file_count: int,
    actual_mode: Mode,
    actual_seconds: float,
    actual_tokens: int,
    actual_issues: int,
) -> list[ModeMetrics]:
    """3 mod için ModeMetrics listesi döndür.

    `actual_mode` için ölçülen değerleri olduğu gibi kullanır; diğerleri için
    sabit çarpanlarla tahmin yapar.
    """
    if file_count <= 0:
        file_count = 1
    actual_mult = _ISSUE_MULTIPLIER[actual_mode]

    out: list[ModeMetrics] = []
    for mode in ("static", "hybrid", "deep"):
        if mode == actual_mode:
            out.append(
                ModeMetrics(
                    mode=mode,  # type: ignore[arg-type]
                    estimated_seconds=actual_seconds,
                    estimated_tokens=actual_tokens,
                    estimated_issues=actual_issues,
                    is_actual=True,
                )
            )
        else:
            normalized_issues = (
                actual_issues / actual_mult if actual_mult > 0 else actual_issues
            )
            out.append(
                ModeMetrics(
                    mode=mode,  # type: ignore[arg-type]
                    estimated_seconds=round(file_count * _TIME_PER_FILE_SEC[mode], 2),
                    estimated_tokens=file_count * _TOKENS_PER_FILE[mode],
                    estimated_issues=int(round(normalized_issues * _ISSUE_MULTIPLIER[mode])),
                    is_actual=False,
                )
            )
    return out
