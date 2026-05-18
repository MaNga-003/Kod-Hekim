"""MISSING_TIMEOUT — timeout kwarg'ı olmayan dış HTTP çağrısı."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule, call_func_name


_BLOCKING_HTTP_CALLS = {
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.delete",
    "requests.patch",
    "requests.head",
    "requests.options",
    "requests.request",
    "httpx.get",
    "httpx.post",
    "httpx.put",
    "httpx.delete",
    "httpx.patch",
    "httpx.head",
    "httpx.options",
    "httpx.request",
    "urllib.request.urlopen",
}


def _has_kwarg(call: ast.Call, name: str) -> bool:
    return any(k.arg == name for k in call.keywords)


class MissingTimeoutRule(StaticRule):
    code = "MISSING_TIMEOUT"
    category = "performance"
    severity = "high"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []
        for node in ast.walk(parsed.tree):
            if not isinstance(node, ast.Call):
                continue
            fname = call_func_name(node)
            if fname not in _BLOCKING_HTTP_CALLS:
                continue
            if _has_kwarg(node, "timeout"):
                continue
            issues.append(
                self.make_issue(
                    file=parsed.file_path,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    snippet=snippet_for(parsed, node.lineno, node.end_lineno or node.lineno),
                    explanation=(
                        f"`{fname}(...)` çağrısı timeout olmadan yapılıyor. "
                        "Yavaş veya askıda kalan upstream connection pool'u tüketebilir; "
                        "tüm worker'lar bloklanır."
                    ),
                    static_confidence=0.9,
                    extra={"function": fname},
                )
            )
        return issues
