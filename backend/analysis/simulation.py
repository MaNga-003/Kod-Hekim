"""Önce/Sonra sağlık skoru simülatörü (developer.md §16.1).

Kullanıcı raporda fix'leri tick'lediğinde sağlık skorunun nereye çıkacağını
hesaplar. Saf Python; LLM çağrısı yok.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from agents.chief_heuristic import health_score
from agents.issue import Issue
from agents.types import HealthScore


def simulate_post_fix_score(
    all_issues: Iterable[Issue],
    accepted_fix_ids: set[str],
) -> HealthScore:
    """Kabul edilen fix'leri uygulanmış sayıp yeni sağlık skorunu döndür.

    Args:
        all_issues: Raporun tüm `Issue`'ları.
        accepted_fix_ids: Kabul edilen issue id'leri.

    Returns:
        Bu fix'ler uygulansa elde edilecek `HealthScore`.
    """
    remaining = [i for i in all_issues if i.id not in accepted_fix_ids]
    return health_score(remaining)


def score_delta(current: HealthScore, simulated: HealthScore) -> HealthScore:
    """İki skor arasındaki farkı `HealthScore` formatında döndür (signed)."""
    return HealthScore(
        overall=simulated.overall - current.overall,
        performance=simulated.performance - current.performance,
        security=simulated.security - current.security,
        quality=simulated.quality - current.quality,
    )


def to_payload(
    current: HealthScore, simulated: HealthScore, delta: HealthScore
) -> dict:
    return {
        "current_score": asdict(current),
        "simulated_score": asdict(simulated),
        "delta": asdict(delta),
    }
