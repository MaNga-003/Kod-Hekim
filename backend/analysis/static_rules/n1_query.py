"""N1_QUERY — döngü içinde ORM/DB sorgusu."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import (
    IssueCandidate,
    StaticRule,
    build_parent_map,
    get_attr_chain,
    is_in_loop,
)


# Doğrudan sorgu nesnesi üzerinde — tek başına yeterince güvenilir
_DIRECT_ORM_METHODS = frozenset({
    "query",
    "filter",
    "filter_by",
    "where",
    "execute",
    "objects",
})

# Yalnızca ORM bağlamında (`.query.get`, `.objects.get`, `session.get`) sayılır
_CONTEXT_ORM_METHODS = frozenset({
    "get",
    "first",
    "one",
    "one_or_none",
    "find",
    "find_one",
})

_ORM_RECEIVER_HINTS = frozenset({
    "query",
    "objects",
    "session",
    "db",
})


def _chain_looks_like_orm(chain: str) -> bool:
    parts = chain.split(".")
    if len(parts) < 2:
        return False
    receiver = parts[-2].lower()
    if receiver in _ORM_RECEIVER_HINTS:
        return True
    if receiver.endswith("session"):
        return True
    # Model.query.filter — en az üç parça
    return len(parts) >= 3 and parts[-3].lower() not in {"self", "cls"}


def _is_db_call(call: ast.Call) -> str | None:
    """Çağrı muhtemelen DB/ORM call mı? dict.get / client.get gibi FP'leri ele."""
    if not isinstance(call.func, ast.Attribute):
        return None
    method = call.func.attr
    if method in _DIRECT_ORM_METHODS:
        return method
    if method in _CONTEXT_ORM_METHODS:
        chain = get_attr_chain(call.func)
        if chain and _chain_looks_like_orm(chain):
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
