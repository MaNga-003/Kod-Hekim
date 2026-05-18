"""UNHANDLED_EXCEPTION — route handler içinde risky call var ama try/except yok."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule, call_func_name
from analysis.static_rules.large_payload import _is_route_handler


_RISKY_CALL_NAMES = {
    "json.loads",
    "json.load",
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.delete",
    "requests.patch",
    "requests.request",
    "httpx.get",
    "httpx.post",
    "open",
    "int",
    "float",
}

# Sondaki method ismiyle eşleşen DB call hint'leri
_RISKY_METHOD_NAMES = {"execute", "first", "one"}


def _has_outer_try(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Fonksiyon body'sinde top-level bir Try bloğu var mı?"""
    return any(isinstance(stmt, ast.Try) for stmt in func.body)


def _risky_calls_in(func: ast.AST) -> list[ast.Call]:
    out: list[ast.Call] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        name = call_func_name(node)
        if name in _RISKY_CALL_NAMES:
            out.append(node)
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in _RISKY_METHOD_NAMES:
            out.append(node)
    return out


class UnhandledExceptionRule(StaticRule):
    code = "UNHANDLED_EXCEPTION"
    category = "reliability"
    severity = "medium"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []
        for func in ast.walk(parsed.tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _is_route_handler(func):
                continue
            if _has_outer_try(func):
                continue
            risky = _risky_calls_in(func)
            if not risky:
                continue
            first = risky[0]
            issues.append(
                self.make_issue(
                    file=parsed.file_path,
                    line_start=func.lineno,
                    line_end=func.lineno,
                    snippet=snippet_for(parsed, func.lineno, func.lineno),
                    explanation=(
                        f"Route `{func.name}` içinde {len(risky)} adet hata fırlatabilecek "
                        f"çağrı var (ör. `{call_func_name(first) or 'attr-call'}`) ama "
                        "try/except yok. Tek bir bozuk istek 500 patlatır, kötü senaryoda "
                        "worker restart döngüsü."
                    ),
                    static_confidence=0.6,
                    extra={"handler": func.name, "risky_count": len(risky)},
                )
            )
        return issues
