"""LARGE_PAYLOAD — route handler içinde pagination'sız `.all()`."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule


_ROUTE_DECORATORS = {
    # FastAPI / Starlette
    "get",
    "post",
    "put",
    "delete",
    "patch",
    "head",
    "options",
    # Flask
    "route",
    # Django REST
    "api_view",
}


def _is_route_handler(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in func.decorator_list:
        if isinstance(dec, ast.Call):
            dec = dec.func
        if isinstance(dec, ast.Attribute) and dec.attr in _ROUTE_DECORATORS:
            return True
        if isinstance(dec, ast.Name) and dec.id in _ROUTE_DECORATORS:
            return True
    return False


def _has_pagination(call: ast.Call) -> bool:
    """`.all()` öncesi/sonrası limit/offset/slice var mı?"""
    if not isinstance(call.func, ast.Attribute):
        return False
    # call.func.value zincirde `.limit(...).offset(...)` var mı kontrol et
    cur: ast.AST | None = call.func.value
    while isinstance(cur, ast.Call):
        if isinstance(cur.func, ast.Attribute) and cur.func.attr in {"limit", "offset", "slice", "paginate"}:
            return True
        cur = cur.func.value if isinstance(cur.func, ast.Attribute) else None
    return False


class LargePayloadRule(StaticRule):
    code = "LARGE_PAYLOAD"
    category = "performance"
    severity = "medium"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []
        for func in ast.walk(parsed.tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _is_route_handler(func):
                continue
            for node in ast.walk(func):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Attribute) or node.func.attr != "all":
                    continue
                if _has_pagination(node):
                    continue
                issues.append(
                    self.make_issue(
                        file=parsed.file_path,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        snippet=snippet_for(parsed, node.lineno, node.lineno),
                        explanation=(
                            f"Route `{func.name}` içinde `.all()` çağrısı; limit/offset yok. "
                            "Tablo büyüdükçe yanıt boyutu ve latency çığ gibi büyür. "
                            "Pagination ekle (`limit(...).offset(...)` veya FastAPI Pagination)."
                        ),
                        static_confidence=0.7,
                        extra={"handler": func.name},
                    )
                )
        return issues
