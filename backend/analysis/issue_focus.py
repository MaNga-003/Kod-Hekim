"""Bulgu önceliklendirme — skor ve rapor gürültüsünü azaltır.

KodHekim odağı (developer-v4 §4.4 ruhu):
  - Kritik: high/medium güvenlik, performans, bellek, güvenilirlik
  - RAM/operasyonel şişme: sınırsız cache, global birikim, listener sızıntısı vb.
  - Kalite gürültüsü (DEAD_CODE satır satır, shadow variable): raporda sınırlı, skora girmez
"""

from __future__ import annotations

from typing import Protocol, TypeVar

# Bellek / kaynak şişmesi — düşük severity olsa bile raporda tutulur
MEMORY_BLOAT_CODES: frozenset[str] = frozenset({
    "UNBOUNDED_CACHE",
    "GLOBAL_ACCUMULATOR",
    "MEMORY_LEAK_LISTENER",
    "MEMORY_LEAK",
    "LOAD_FULL_FILE",
    "UNCLOSED_RESOURCE",
})

# Skora ve öncelikli rapora girmeyen düşük öncelikli kalite bulguları
QUALITY_NOISE_CODES: frozenset[str] = frozenset({
    "DEAD_CODE",
    "SHADOW_VARIABLE",
    "INEFFICIENT_STRING_CONCAT",
    "LIST_OVER_GENERATOR",
    "DEEP_RECURSION",
    "CIRCULAR_IMPORT",
})

_SEV_RANK = {"high": 0, "medium": 1, "low": 2}
_FOCUS_CATEGORIES = frozenset({"performance", "memory", "security", "reliability"})

MAX_SCORING_ISSUES = 12
MAX_REPORT_ISSUES = 45
MAX_DEAD_CODE_IN_REPORT = 3
MAX_LOW_QUALITY_IN_REPORT = 6

T = TypeVar("T", bound="IssueLike")


class IssueLike(Protocol):
    code: str
    category: str
    severity: str
    file: str
    static_confidence: float


def is_memory_or_critical(issue: IssueLike) -> bool:
    if issue.code in MEMORY_BLOAT_CODES:
        return True
    if issue.category in _FOCUS_CATEGORIES and issue.severity in ("high", "medium"):
        return True
    if issue.category == "memory":
        return True
    return False


def is_scoring_issue(issue: IssueLike) -> bool:
    """Sağlık skoruna dahil edilecek bulgular."""
    if issue.code in QUALITY_NOISE_CODES:
        return False
    if issue.severity == "low":
        if issue.code in MEMORY_BLOAT_CODES:
            return True
        if issue.category in ("performance", "memory"):
            return True
        return False
    return is_memory_or_critical(issue) or (
        issue.severity in ("high", "medium") and issue.category == "quality"
    )


def _sort_key(issue: IssueLike) -> tuple:
    return (
        _SEV_RANK.get(issue.severity, 9),
        -issue.static_confidence,
        issue.file,
        issue.code,
    )


def _dedupe_file_code(issues: list[T]) -> list[T]:
    seen: set[tuple[str, str]] = set()
    out: list[T] = []
    for issue in issues:
        key = (issue.file, issue.code)
        if key in seen:
            continue
        seen.add(key)
        out.append(issue)
    return out


def issues_for_scoring(issues: list[T]) -> list[T]:
    """Skor formülüne giren en önemli bulgular (dedupe + üst sınır)."""
    pool = _dedupe_file_code([i for i in issues if is_scoring_issue(i)])
    pool.sort(key=_sort_key)
    return pool[:MAX_SCORING_ISSUES]


def issues_for_report(issues: list[T]) -> list[T]:
    """Kullanıcı raporu — kritik tam liste, kalite gürültüsü kısıtlı."""
    critical = [i for i in issues if is_scoring_issue(i) or i.code in MEMORY_BLOAT_CODES]
    critical_keys = {(i.file, i.code, i.severity) for i in critical}
    noise = [
        i for i in issues
        if (i.file, i.code, i.severity) not in critical_keys
    ]
    noise.sort(key=_sort_key)

    dead = [i for i in noise if i.code == "DEAD_CODE"][:MAX_DEAD_CODE_IN_REPORT]
    other_low = [i for i in noise if i.code != "DEAD_CODE"][:MAX_LOW_QUALITY_IN_REPORT]

    combined = _dedupe_file_code(critical + dead + other_low)
    combined.sort(key=_sort_key)
    return combined[:MAX_REPORT_ISSUES]
