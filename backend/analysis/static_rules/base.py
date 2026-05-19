"""Statik kural arayüzü + IssueCandidate dataclass'ı.

Her örüntü kendi dosyasında bir `StaticRule` alt sınıfı tanımlar ve `register(...)`
fonksiyonuyla `ALL_RULES`'a eklenir (bkz. `static_rules/__init__.py`).
"""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal, Optional

# Kategori ve severity tipleri (developer.md §4.1)
Category = Literal["performance", "memory", "reliability", "security", "quality"]
Severity = Literal["high", "medium", "low"]


SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


def _cap_severity(sev: Severity, cap: Optional[Severity]) -> Severity:
    """Bir kuralın severity'sini cap ile sınırla (ör. RACE_CONDITION → max medium)."""
    if cap is None:
        return sev
    if SEVERITY_ORDER[sev] > SEVERITY_ORDER[cap]:
        return cap
    return sev


@dataclass
class IssueCandidate:
    """Statik motorun ürettiği aday sorun. LLM confirm öncesi `static_confidence` taşır."""

    code: str
    category: Category
    severity: Severity
    file: str
    line_start: int
    line_end: int
    snippet: str
    explanation: str
    static_confidence: float = 0.7
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "file": self.file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "snippet": self.snippet,
            "explanation": self.explanation,
            "static_confidence": round(self.static_confidence, 2),
            "extra": self.extra,
        }


class _RuleBase:
    """`StaticRule` ve `ProjectStaticRule` için ortak yardımcılar."""

    code: str
    category: Category
    severity: Severity
    severity_cap: Optional[Severity] = None
    languages: list[str] = ["python"]

    def make_issue(
        self,
        *,
        file: str,
        line_start: int,
        line_end: int,
        snippet: str,
        explanation: str,
        static_confidence: float = 0.7,
        severity_override: Optional[Severity] = None,
        extra: Optional[dict] = None,
    ) -> IssueCandidate:
        sev = severity_override or self.severity
        sev = _cap_severity(sev, self.severity_cap)
        return IssueCandidate(
            code=self.code,
            category=self.category,
            severity=sev,
            file=file,
            line_start=line_start,
            line_end=line_end,
            snippet=snippet,
            explanation=explanation,
            static_confidence=static_confidence,
            extra=extra or {},
        )


class StaticRule(_RuleBase, ABC):
    """Tek-dosya seviyesinde çalışan kural.

    Sınıf attribute'ları:
        code: stable upper-case ID, ör. "N1_QUERY".
        category: kategori string'i.
        severity: varsayılan severity.
        severity_cap: severity tavanı (varsa). developer.md §5.3 RACE_CONDITION için "medium".
        languages: desteklenen diller (ör. ["python"], ["javascript", "typescript"], üçü birden).
    """

    @abstractmethod
    def scan(self, parsed) -> list[IssueCandidate]:  # type: ignore[no-untyped-def]
        """ParsedFile → bulgular. Detaylar `analysis.ast_parser.ParsedFile`."""


class ProjectStaticRule(_RuleBase, ABC):
    """Proje (çoklu dosya) seviyesinde çalışan kural — örn. CIRCULAR_IMPORT, DEAD_CODE."""

    @abstractmethod
    def scan_project(self, parsed_files: list) -> list[IssueCandidate]:  # type: ignore[no-untyped-def]
        """ParsedFile listesi → bulgular."""


# ---------------------------------------------------------------------------
# AST yardımcıları (rule'lar tarafından sık kullanılır)
# ---------------------------------------------------------------------------


def get_attr_chain(node: ast.AST) -> Optional[str]:
    """`requests.get` veya `db.session.query` gibi attribute zincirlerini string'e çevir."""
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    else:
        return None
    return ".".join(reversed(parts))


def call_func_name(node: ast.Call) -> Optional[str]:
    """`requests.get(...)` çağrısı için `requests.get` döndürür; bilinmiyorsa None."""
    return get_attr_chain(node.func)


def is_in_loop(node: ast.AST, parents_map: dict[ast.AST, ast.AST]) -> bool:
    """Verilen node, herhangi bir for/while döngüsü içinde mi?"""
    cur = parents_map.get(node)
    while cur is not None:
        if isinstance(cur, (ast.For, ast.AsyncFor, ast.While)):
            return True
        cur = parents_map.get(cur)
    return False


def build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    """ast.walk parent ilişkisi vermez — kuralların ihtiyaç duyduğu eşlemeyi üret."""
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def get_enclosing(
    node: ast.AST,
    parents_map: dict[ast.AST, ast.AST],
    types: tuple[type, ...],
) -> Optional[ast.AST]:
    """node'u kapsayan ilk verilen tipten ata node'u (yoksa None)."""
    cur = parents_map.get(node)
    while cur is not None:
        if isinstance(cur, types):
            return cur
        cur = parents_map.get(cur)
    return None
