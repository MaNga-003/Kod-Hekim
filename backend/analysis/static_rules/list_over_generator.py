"""LIST_OVER_GENERATOR — `for x in [c for c in big]` veya `sum([...])` gibi.

ListComp sonucu sadece iter edilecekse generator expression yeterli ve RAM dostu.
"""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule


# ListComp tamamen tüketilirse list'e dönüştürmek anlamsız.
_ITERATING_CONSUMERS = {
    "sum",
    "any",
    "all",
    "max",
    "min",
    "set",
    "frozenset",
    "tuple",
    "dict",
    "join",  # ''.join([...])
}


class ListOverGeneratorRule(StaticRule):
    code = "LIST_OVER_GENERATOR"
    category = "memory"
    severity = "low"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []

        # Case 1: `for x in [c for c in y]` — direkt yararsız
        for node in ast.walk(parsed.tree):
            if isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.iter, ast.ListComp):
                issues.append(self._make(parsed, node.iter, "for"))

        # Case 2: `sum([...])`, `any([...])`, `''.join([...])` vb.
        for node in ast.walk(parsed.tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            first = node.args[0]
            if not isinstance(first, ast.ListComp):
                continue
            fname = None
            if isinstance(node.func, ast.Name):
                fname = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fname = node.func.attr
            if fname in _ITERATING_CONSUMERS:
                issues.append(self._make(parsed, first, f"{fname}()"))

        return issues

    def _make(self, parsed: ParsedFile, node: ast.ListComp, ctx: str) -> IssueCandidate:
        return self.make_issue(
            file=parsed.file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            snippet=snippet_for(parsed, node.lineno, node.end_lineno or node.lineno),
            explanation=(
                f"`{ctx}` içinde list comprehension'a sarılı bir iterable var; "
                "sonuç sadece iter ediliyor. Köşeli parantezi kaldır → generator "
                "expression peak RAM'i 2-10x düşürür."
            ),
            static_confidence=0.8,
            extra={"context": ctx},
        )
