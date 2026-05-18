"""INEFFICIENT_STRING_CONCAT — döngü içinde `s += ...` tespiti."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule, build_parent_map, is_in_loop


class InefficientStringConcatRule(StaticRule):
    code = "INEFFICIENT_STRING_CONCAT"
    category = "quality"
    severity = "low"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []
        parents = build_parent_map(parsed.tree)

        for node in ast.walk(parsed.tree):
            if not isinstance(node, ast.AugAssign):
                continue
            if not isinstance(node.op, ast.Add):
                continue
            if not isinstance(node.target, ast.Name):
                continue
            if not is_in_loop(node, parents):
                continue
            # Sağ taraf string literali veya Name ise → muhtemelen string concat.
            # Tip çıkarımı yapamıyoruz ama `+= "..."` çoğunlukla string concat.
            rhs_is_strlike = (
                isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
            ) or isinstance(node.value, ast.Name) or isinstance(node.value, ast.JoinedStr)
            if not rhs_is_strlike:
                continue

            issues.append(
                self.make_issue(
                    file=parsed.file_path,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    snippet=snippet_for(parsed, node.lineno, node.end_lineno or node.lineno, context=1),
                    explanation=(
                        f"`{node.target.id}` döngü içinde `+=` ile birleştiriliyor. "
                        "Python string'leri immutable; her iterasyon yeni alloc → O(n²). "
                        "Liste biriktir, sonra `''.join(...)` kullan."
                    ),
                    static_confidence=0.65,
                )
            )
        return issues
