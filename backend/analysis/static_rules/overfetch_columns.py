"""OVERFETCH_COLUMNS — `.all()` sonra sadece 1-2 alan kullanılıyor (heuristic)."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule


class OverfetchColumnsRule(StaticRule):
    code = "OVERFETCH_COLUMNS"
    category = "performance"
    severity = "medium"

    # Eğer kullanılan attribute sayısı bu eşikten azsa overfetch sayılır.
    MIN_USED_ATTRS_FOR_OK = 3

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []

        # `items = ....all()` formundaki atamaları bul
        for stmt in ast.walk(parsed.tree):
            if not isinstance(stmt, ast.Assign):
                continue
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                continue
            rhs = stmt.value
            if not (isinstance(rhs, ast.Call) and isinstance(rhs.func, ast.Attribute) and rhs.func.attr == "all"):
                continue

            items_name = stmt.targets[0].id

            # Bir sonraki for döngüsünü ara ki üzerinde iterate ediyor olsun:
            # for x in items: ... attribute(x.email) ...
            used_attrs: set[str] = set()
            iter_found = False
            for outer in ast.walk(parsed.tree):
                if not isinstance(outer, ast.For):
                    continue
                if not (isinstance(outer.iter, ast.Name) and outer.iter.id == items_name):
                    continue
                iter_found = True
                if not isinstance(outer.target, ast.Name):
                    continue
                iter_var = outer.target.id
                for node in ast.walk(outer):
                    if (
                        isinstance(node, ast.Attribute)
                        and isinstance(node.value, ast.Name)
                        and node.value.id == iter_var
                    ):
                        used_attrs.add(node.attr)

            if not iter_found:
                continue
            if not used_attrs:
                continue
            if len(used_attrs) >= self.MIN_USED_ATTRS_FOR_OK:
                continue

            issues.append(
                self.make_issue(
                    file=parsed.file_path,
                    line_start=rhs.lineno,
                    line_end=rhs.end_lineno or rhs.lineno,
                    snippet=snippet_for(parsed, rhs.lineno, rhs.lineno, context=2),
                    explanation=(
                        f"`{items_name} = ....all()` ile tüm kolonlar çekiliyor ama döngüde "
                        f"sadece {sorted(used_attrs)} kullanılıyor. "
                        "`.with_entities(...)` / `values(...)` ile yalnız gereken kolonları çek."
                    ),
                    static_confidence=0.6,
                    extra={"used": sorted(used_attrs)},
                )
            )

        return issues
