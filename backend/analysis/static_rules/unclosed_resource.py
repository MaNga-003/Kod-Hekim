"""UNCLOSED_RESOURCE — `open()` / `socket.socket()` çağrısı `with` bloğu dışında."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import (
    IssueCandidate,
    StaticRule,
    build_parent_map,
    call_func_name,
    get_enclosing,
)


_RESOURCE_FUNCS = {"open", "socket.socket"}


def _is_inside_with(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """`with open(...) as f:` veya `with open(...):` formunda çağrılmış mı?"""
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, ast.withitem):
            return cur.context_expr is node
        if isinstance(cur, (ast.With, ast.AsyncWith)):
            for item in cur.items:
                if item.context_expr is node:
                    return True
        cur = parents.get(cur)
    return False


class UnclosedResourceRule(StaticRule):
    code = "UNCLOSED_RESOURCE"
    category = "memory"
    severity = "low"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []
        parents = build_parent_map(parsed.tree)

        for node in ast.walk(parsed.tree):
            if not isinstance(node, ast.Call):
                continue
            fname = call_func_name(node)
            if fname not in _RESOURCE_FUNCS:
                continue
            if _is_inside_with(node, parents):
                continue
            # Module-level `f = open(...)` veya fonksiyon içinde fakat with'siz
            issues.append(
                self.make_issue(
                    file=parsed.file_path,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    snippet=snippet_for(parsed, node.lineno, node.lineno),
                    explanation=(
                        f"`{fname}(...)` çağrısı `with` bloğu dışında. "
                        "İstisna durumunda dosya handle'ı açık kalır; "
                        "context manager kullan: `with {fname}(...) as f:`"
                    ),
                    static_confidence=0.7,
                    extra={"function": fname},
                )
            )
        return issues
