"""O_N_SQUARED — iç içe iki for loop, aynı koleksiyona referans."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule


def _iter_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        # range(len(items)) gibi — items'ı yakala
        if isinstance(node.func, ast.Name) and node.func.id == "range" and node.args:
            inner = node.args[0]
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and inner.func.id == "len":
                if inner.args and isinstance(inner.args[0], ast.Name):
                    return inner.args[0].id
        if isinstance(node.func, ast.Name) and node.func.id == "enumerate" and node.args:
            inner = node.args[0]
            if isinstance(inner, ast.Name):
                return inner.id
    return None


class ONSquaredRule(StaticRule):
    code = "O_N_SQUARED"
    category = "performance"
    severity = "medium"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []
        seen_outer: set[int] = set()

        for outer in ast.walk(parsed.tree):
            if not isinstance(outer, ast.For):
                continue
            outer_iter = _iter_name(outer.iter)
            if outer_iter is None:
                continue
            for inner in ast.walk(outer):
                if inner is outer or not isinstance(inner, ast.For):
                    continue
                inner_iter = _iter_name(inner.iter)
                if inner_iter is None or inner_iter != outer_iter:
                    continue
                if outer.lineno in seen_outer:
                    continue
                seen_outer.add(outer.lineno)
                issues.append(
                    self.make_issue(
                        file=parsed.file_path,
                        line_start=outer.lineno,
                        line_end=inner.lineno,
                        snippet=snippet_for(parsed, outer.lineno, inner.lineno),
                        explanation=(
                            f"İç içe iki döngü aynı koleksiyonu (`{outer_iter}`) dolaşıyor — "
                            "O(n²). Büyük n'de pratik olarak askıda kalır. "
                            "Set/dict ile lookup veya algoritmayı yeniden düşün."
                        ),
                        static_confidence=0.75,
                        extra={"collection": outer_iter},
                    )
                )
                break
        return issues
