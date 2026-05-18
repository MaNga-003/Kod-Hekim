"""MUTABLE_DEFAULT_ARG — `def f(x=[])` / `def f(x={})` / `def f(x=set())` tespiti."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule


_MUTABLE_CALL_NAMES = {"list", "dict", "set"}


def _is_mutable_default(node: ast.expr) -> bool:
    if isinstance(node, (ast.List, ast.Dict, ast.Set)):
        return True
    # list(), dict(), set() çağrıları
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id in _MUTABLE_CALL_NAMES
    return False


class MutableDefaultArgRule(StaticRule):
    code = "MUTABLE_DEFAULT_ARG"
    category = "reliability"
    severity = "medium"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []
        for node in ast.walk(parsed.tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args
            # positional defaults
            for default in list(args.defaults) + list(args.kw_defaults):
                if default is None:
                    continue
                if _is_mutable_default(default):
                    issues.append(
                        self.make_issue(
                            file=parsed.file_path,
                            line_start=default.lineno,
                            line_end=default.end_lineno or default.lineno,
                            snippet=snippet_for(parsed, node.lineno, node.lineno),
                            explanation=(
                                f"`{node.name}` fonksiyonunun parametresi mutable default "
                                "ile tanımlanmış. Aynı obje çağrılar arasında paylaşılır → "
                                "sürpriz state ve bellek sızıntısı."
                            ),
                            static_confidence=0.95,
                        )
                    )
                    break  # her fonksiyon için tek bulgu yeter
        return issues
