"""N1_QUERY — döngü içinde ORM/DB sorgusu."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule, build_parent_map, is_in_loop


# Çağrıda görünen son attribute (zincirin sonu). Geniş tutuyoruz; LLM confirm filtreler.
_ORM_METHOD_NAMES = {
    "query",
    "filter",
    "filter_by",
    "where",
    "get",
    "first",
    "one",
    "one_or_none",
    "find",
    "find_one",
    "execute",
    # Django: Model.objects.get/.filter
    "objects",
}


def _is_db_call(call: ast.Call) -> str | None:
    """Çağrı muhtemelen DB call mı? Eşleşen method adını döndür ya da None."""
    if not isinstance(call.func, ast.Attribute):
        return None
    method = call.func.attr
    if method in _ORM_METHOD_NAMES:
        return method
    return None


class N1QueryRule(StaticRule):
    code = "N1_QUERY"
    category = "performance"
    severity = "high"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []
        parents = build_parent_map(parsed.tree)
        seen_lines: set[int] = set()

        for node in ast.walk(parsed.tree):
            if not isinstance(node, ast.Call):
                continue
            method = _is_db_call(node)
            if method is None:
                continue
            if not is_in_loop(node, parents):
                continue
            if node.lineno in seen_lines:
                continue
            seen_lines.add(node.lineno)
            issues.append(
                self.make_issue(
                    file=parsed.file_path,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    snippet=snippet_for(parsed, node.lineno, node.lineno, context=2),
                    explanation=(
                        f"Döngü içinde `.{method}(...)` DB çağrısı — klasik N+1 problemi. "
                        "Her iterasyon ayrı bir sorgu açar. `select_related` / `joinedload` "
                        "veya batch fetch (`IN (...)`) ile tek sorguya indir."
                    ),
                    static_confidence=0.75,
                    extra={"method": method},
                )
            )
        return issues
