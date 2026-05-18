"""DEEP_RECURSION — kendini çağıran fonksiyonlar (base case heuristic)."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule


class DeepRecursionRule(StaticRule):
    code = "DEEP_RECURSION"
    category = "reliability"
    severity = "low"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []

        for func in ast.walk(parsed.tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls_self = False
            has_base_case = False
            for node in ast.walk(func):
                # Recursive call?
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == func.name
                ):
                    calls_self = True
                # if + return → muhtemelen base case
                if isinstance(node, ast.If):
                    for stmt in node.body:
                        if isinstance(stmt, ast.Return):
                            has_base_case = True
                            break
            if calls_self and not has_base_case:
                issues.append(
                    self.make_issue(
                        file=parsed.file_path,
                        line_start=func.lineno,
                        line_end=func.lineno,
                        snippet=snippet_for(parsed, func.lineno, func.lineno),
                        explanation=(
                            f"`{func.name}` kendini çağırıyor ama açık bir base case "
                            "(if + return) görünmüyor. Stack overflow / RecursionError riski."
                        ),
                        static_confidence=0.6,
                        extra={"function": func.name},
                    )
                )
        return issues
