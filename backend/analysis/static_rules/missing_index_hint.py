"""MISSING_INDEX_HINT — aynı alanda 3+ filtre ama index ipucu yok (heuristic)."""

from __future__ import annotations

import ast
from collections import Counter

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule


def _is_orm_filter_call(call: ast.Call) -> ast.Attribute | None:
    """`.filter(...)`, `.filter_by(...)`, `.where(...)` çağrısı mı?"""
    if not isinstance(call.func, ast.Attribute):
        return None
    if call.func.attr in {"filter", "filter_by", "where"}:
        return call.func
    return None


def _extract_field_names(call: ast.Call) -> list[str]:
    """Filter çağrısından alan ismi çıkar: filter_by(email=...) ve filter(Model.email==...)"""
    names: list[str] = []
    for kw in call.keywords:
        if kw.arg:
            names.append(kw.arg)
    for arg in call.args:
        # Model.field == X → BoolOp/Compare
        if isinstance(arg, ast.Compare) and isinstance(arg.left, ast.Attribute):
            names.append(arg.left.attr)
        elif isinstance(arg, ast.Compare) and isinstance(arg.left, ast.Name):
            names.append(arg.left.id)
    return names


class MissingIndexHintRule(StaticRule):
    code = "MISSING_INDEX_HINT"
    category = "performance"
    severity = "medium"

    THRESHOLD = 3

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []

        field_uses: Counter[str] = Counter()
        first_line: dict[str, int] = {}

        for node in ast.walk(parsed.tree):
            if not isinstance(node, ast.Call):
                continue
            if not _is_orm_filter_call(node):
                continue
            for fname in _extract_field_names(node):
                if fname.startswith("_") or fname in {"id", "pk"}:
                    continue  # primary key zaten indexli
                field_uses[fname] += 1
                first_line.setdefault(fname, node.lineno)

        for fname, count in field_uses.items():
            if count < self.THRESHOLD:
                continue
            ln = first_line[fname]
            issues.append(
                self.make_issue(
                    file=parsed.file_path,
                    line_start=ln,
                    line_end=ln,
                    snippet=snippet_for(parsed, ln, ln),
                    explanation=(
                        f"`{fname}` alanı bu dosyada {count} farklı sorguda filtreleme için "
                        "kullanılıyor. Index yoksa her sorgu tablo taraması yapar; "
                        "model tanımına `index=True` ekle (veya migration ile)."
                    ),
                    static_confidence=0.55,
                    extra={"field": fname, "usage_count": count},
                )
            )
        return issues
