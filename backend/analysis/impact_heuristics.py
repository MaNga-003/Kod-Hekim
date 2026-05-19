"""Örüntü kodu → sayısal etki metrikleri.

Heuristic registry: kod (`"N1_QUERY"`) → metrik dict.
Sonuçlar hem statik modda (Türkçe sabit template'a girer) hem Hibrit'te (LLM'e
context olarak verilir) kullanılır.

NOT: Tüm sayılar kasıtlı olarak **tahmin** — runtime profiling yok. Doküman
kararı: somut teknik bulgu, ama her zaman "tahmin" etiketiyle.
"""

from __future__ import annotations

from typing import Callable

from agents.issue import Issue


# Geri dönüş: (impact_score 0-100, dimensions dict, remediation_hours)
HeuristicFn = Callable[[Issue], tuple[int, dict, float]]


# Severity → base impact_score
_SEV_BASE = {"high": 80, "medium": 55, "low": 30}

# Category → multiplier (security ağır)
_CAT_MULT = {
    "security": 1.15,
    "performance": 1.10,
    "memory": 1.05,
    "reliability": 1.0,
    "quality": 0.90,
}


def _base_score(issue: Issue) -> int:
    base = _SEV_BASE.get(issue.severity, 40)
    mult = _CAT_MULT.get(issue.category, 1.0)
    return min(100, int(base * mult))


# ---------------------------------------------------------------------------
# Örüntü-spesifik heuristics
# ---------------------------------------------------------------------------


def _n1_query(issue: Issue) -> tuple[int, dict, float]:
    # Varsayım: ortalama 50 entity / istek
    return (
        _base_score(issue) + 5,
        {
            "db_calls_per_request_estimate": 50,
            "latency_impact": "yüksek",
            "scaling_risk": "high",
        },
        0.5,
    )


def _missing_timeout(issue: Issue) -> tuple[int, dict, float]:
    return (
        _base_score(issue),
        {"pool_exhaustion_risk": 4, "scaling_risk": "high"},
        0.1,
    )


def _sync_in_async(issue: Issue) -> tuple[int, dict, float]:
    return (
        _base_score(issue),
        {"event_loop_block": "yüksek", "concurrent_request_impact": "high"},
        0.5,
    )


def _missing_index_hint(issue: Issue) -> tuple[int, dict, float]:
    uses = issue.extra.get("usage_count", 3)
    return (
        _base_score(issue),
        {"filter_usages": uses, "full_scan_risk": "medium"},
        0.5,
    )


def _o_n_squared(issue: Issue) -> tuple[int, dict, float]:
    return (_base_score(issue), {"complexity": "O(n²)", "scaling_risk": "high"}, 1.0)


def _large_payload(issue: Issue) -> tuple[int, dict, float]:
    return (
        _base_score(issue),
        {"unbounded_rows": True, "bandwidth_risk": "medium"},
        0.5,
    )


def _repeated_compute(issue: Issue) -> tuple[int, dict, float]:
    occ = issue.extra.get("occurrences", 2)
    return (
        _base_score(issue) - 5,
        {"redundant_calls_per_iteration": occ},
        0.25,
    )


def _overfetch_columns(issue: Issue) -> tuple[int, dict, float]:
    used = issue.extra.get("used", [])
    return (
        _base_score(issue),
        {"columns_used": used, "columns_fetched_estimate": "tümü"},
        0.5,
    )


def _unbounded_cache(issue: Issue) -> tuple[int, dict, float]:
    return (
        _base_score(issue) + 5,
        {"growth_pattern": "sınırsız", "oom_risk": "high"},
        0.5,
    )


def _global_accumulator(issue: Issue) -> tuple[int, dict, float]:
    return (
        _base_score(issue) + 5,
        {"leak_pattern": "her istekte büyür", "oom_risk": "high"},
        0.5,
    )


def _list_over_generator(issue: Issue) -> tuple[int, dict, float]:
    return (
        _base_score(issue),
        {"peak_ram_multiplier": "2-10x"},
        0.1,
    )


def _load_full_file(issue: Issue) -> tuple[int, dict, float]:
    return (
        _base_score(issue),
        {"peak_ram_equals_file_size": True},
        0.25,
    )


def _unclosed_resource(issue: Issue) -> tuple[int, dict, float]:
    return (
        _base_score(issue),
        {"handle_leak_risk": "low-to-medium"},
        0.1,
    )


def _unhandled_exception(issue: Issue) -> tuple[int, dict, float]:
    return (
        _base_score(issue),
        {"restart_loop_risk": 3, "user_impact": "5xx"},
        0.5,
    )


def _race_condition(issue: Issue) -> tuple[int, dict, float]:
    return (
        _base_score(issue),
        {"data_corruption_risk": 3, "shared_mutable": True},
        1.0,
    )


def _deep_recursion(issue: Issue) -> tuple[int, dict, float]:
    return (_base_score(issue), {"stack_overflow_risk": "low"}, 0.5)


def _mutable_default_arg(issue: Issue) -> tuple[int, dict, float]:
    return (_base_score(issue), {"leak_potential": 3}, 0.1)


def _hardcoded_secret(issue: Issue) -> tuple[int, dict, float]:
    return (
        _base_score(issue) + 10,
        {"exposure_scope": "repo kalıcı (commit'lendiyse)", "rotate_now": True},
        0.5,
    )


def _inefficient_string_concat(issue: Issue) -> tuple[int, dict, float]:
    return (_base_score(issue), {"complexity": "O(n²)"}, 0.25)


def _circular_import(issue: Issue) -> tuple[int, dict, float]:
    cyc = issue.extra.get("cycle", [])
    return (
        _base_score(issue),
        {"cycle_length": len(cyc), "startup_impact_ms": "small-to-medium"},
        0.5,
    )


def _shadow_variable(issue: Issue) -> tuple[int, dict, float]:
    return (_base_score(issue), {"bug_surface": "low"}, 0.1)


def _dead_code(issue: Issue) -> tuple[int, dict, float]:
    return (_base_score(issue), {"maintenance_burden": "low"}, 0.1)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


HEURISTICS: dict[str, HeuristicFn] = {
    "N1_QUERY": _n1_query,
    "MISSING_TIMEOUT": _missing_timeout,
    "SYNC_IN_ASYNC": _sync_in_async,
    "MISSING_INDEX_HINT": _missing_index_hint,
    "O_N_SQUARED": _o_n_squared,
    "LARGE_PAYLOAD": _large_payload,
    "REPEATED_COMPUTE": _repeated_compute,
    "OVERFETCH_COLUMNS": _overfetch_columns,
    "UNBOUNDED_CACHE": _unbounded_cache,
    "GLOBAL_ACCUMULATOR": _global_accumulator,
    "LIST_OVER_GENERATOR": _list_over_generator,
    "LOAD_FULL_FILE": _load_full_file,
    "UNCLOSED_RESOURCE": _unclosed_resource,
    "UNHANDLED_EXCEPTION": _unhandled_exception,
    "RACE_CONDITION": _race_condition,
    "DEEP_RECURSION": _deep_recursion,
    "MUTABLE_DEFAULT_ARG": _mutable_default_arg,
    "HARDCODED_SECRET": _hardcoded_secret,
    "INEFFICIENT_STRING_CONCAT": _inefficient_string_concat,
    "CIRCULAR_IMPORT": _circular_import,
    "SHADOW_VARIABLE": _shadow_variable,
    "DEAD_CODE": _dead_code,
}


def compute_impact(issue: Issue) -> tuple[int, dict, float]:
    """`(impact_score, dimensions, remediation_hours)` döndürür."""
    fn = HEURISTICS.get(issue.code)
    if fn is None:
        return (_base_score(issue), {}, 0.5)
    score, dims, hours = fn(issue)
    return (max(0, min(100, score)), dims, hours)
