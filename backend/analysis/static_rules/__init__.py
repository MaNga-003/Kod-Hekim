"""Tüm statik kuralların kayıt yeri.

`ALL_RULES`: tek-dosya seviyesinde çalışan `StaticRule` örnekleri.
`ALL_PROJECT_RULES`: proje (çoklu dosya) seviyesinde çalışan `ProjectStaticRule` örnekleri.

`scan_repo()` her iki listeyi de tüketir (bkz. `analysis/scan.py`).
"""

from __future__ import annotations

from analysis.static_rules.base import IssueCandidate, ProjectStaticRule, StaticRule

# --- Performans (8) ---
from analysis.static_rules.large_payload import LargePayloadRule
from analysis.static_rules.missing_index_hint import MissingIndexHintRule
from analysis.static_rules.missing_timeout import MissingTimeoutRule
from analysis.static_rules.n1_query import N1QueryRule
from analysis.static_rules.o_n_squared import ONSquaredRule
from analysis.static_rules.overfetch_columns import OverfetchColumnsRule
from analysis.static_rules.repeated_compute import RepeatedComputeRule
from analysis.static_rules.sync_in_async import SyncInAsyncRule

# --- Bellek/RAM (5) ---
from analysis.static_rules.global_accumulator import GlobalAccumulatorRule
from analysis.static_rules.list_over_generator import ListOverGeneratorRule
from analysis.static_rules.load_full_file import LoadFullFileRule
from analysis.static_rules.unbounded_cache import UnboundedCacheRule
from analysis.static_rules.unclosed_resource import UnclosedResourceRule

# --- Güvenilirlik (4) ---
from analysis.static_rules.deep_recursion import DeepRecursionRule
from analysis.static_rules.mutable_default_arg import MutableDefaultArgRule
from analysis.static_rules.race_condition import RaceConditionRule
from analysis.static_rules.unhandled_exception import UnhandledExceptionRule

# --- Güvenlik (1) ---
from analysis.static_rules.hardcoded_secret import HardcodedSecretRule

# --- Kalite (4) ---
from analysis.static_rules.circular_import import CircularImportRule
from analysis.static_rules.dead_code import DeadCodeRule
from analysis.static_rules.inefficient_string_concat import InefficientStringConcatRule
from analysis.static_rules.shadow_variable import ShadowVariableRule


ALL_RULES: list[StaticRule] = [
    # Performans (7 — proje seviyesindeki kurallar ALL_PROJECT_RULES'da)
    LargePayloadRule(),
    MissingIndexHintRule(),
    MissingTimeoutRule(),
    N1QueryRule(),
    ONSquaredRule(),
    OverfetchColumnsRule(),
    RepeatedComputeRule(),
    SyncInAsyncRule(),
    # Bellek
    GlobalAccumulatorRule(),
    ListOverGeneratorRule(),
    LoadFullFileRule(),
    UnboundedCacheRule(),
    UnclosedResourceRule(),
    # Güvenilirlik
    DeepRecursionRule(),
    MutableDefaultArgRule(),
    RaceConditionRule(),
    UnhandledExceptionRule(),
    # Güvenlik
    HardcodedSecretRule(),
    # Kalite (tek-dosya)
    InefficientStringConcatRule(),
    ShadowVariableRule(),
]

ALL_PROJECT_RULES: list[ProjectStaticRule] = [
    CircularImportRule(),
    DeadCodeRule(),
]


__all__ = [
    "ALL_RULES",
    "ALL_PROJECT_RULES",
    "IssueCandidate",
    "StaticRule",
    "ProjectStaticRule",
]
