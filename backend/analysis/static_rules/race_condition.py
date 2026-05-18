"""RACE_CONDITION — global mutable üzerine async fonksiyon içinden lock'suz mutate."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule


_LOCK_TYPES = {"Lock", "RLock", "Semaphore", "BoundedSemaphore"}


def _is_lock_acquisition_around(stmt_lineno: int, async_func: ast.AsyncFunctionDef) -> bool:
    """Async fonksiyonda `async with lock:` var mı (basit heuristic — stmt'in line'ı kapsayan)."""
    for node in ast.walk(async_func):
        if not isinstance(node, (ast.AsyncWith, ast.With)):
            continue
        for item in node.items:
            ctx = item.context_expr
            # `asyncio.Lock()`, `Lock()`, lock variable
            if isinstance(ctx, ast.Call):
                ctx = ctx.func
            if isinstance(ctx, ast.Attribute) and ctx.attr in _LOCK_TYPES:
                if node.lineno <= stmt_lineno <= (node.end_lineno or stmt_lineno):
                    return True
            if isinstance(ctx, ast.Name) and any(
                kw in ctx.id.lower() for kw in ("lock", "mutex", "semaphore")
            ):
                if node.lineno <= stmt_lineno <= (node.end_lineno or stmt_lineno):
                    return True
    return False


class RaceConditionRule(StaticRule):
    code = "RACE_CONDITION"
    category = "reliability"
    severity = "medium"
    severity_cap = "medium"  # developer.md §5.3

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []

        # Modül-level mutable isimler (list / dict / set)
        globals_mut: set[str] = set()
        for node in parsed.tree.body if hasattr(parsed.tree, "body") else []:
            if not isinstance(node, ast.Assign):
                continue
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            rhs = node.value
            if isinstance(rhs, (ast.List, ast.Dict, ast.Set)):
                globals_mut.add(node.targets[0].id)

        if not globals_mut:
            return issues

        for func in ast.walk(parsed.tree):
            if not isinstance(func, ast.AsyncFunctionDef):
                continue
            for node in ast.walk(func):
                # name.append/extend/clear/pop/...
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id in globals_mut
                        and node.func.attr in {"append", "extend", "pop", "clear", "update", "remove"}
                    ):
                        if _is_lock_acquisition_around(node.lineno, func):
                            continue
                        issues.append(self._make(parsed, node, node.func.value.id, func.name))
                # name[k] = v
                if isinstance(node, ast.Assign):
                    for tgt in node.targets:
                        if (
                            isinstance(tgt, ast.Subscript)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id in globals_mut
                        ):
                            if _is_lock_acquisition_around(node.lineno, func):
                                continue
                            issues.append(self._make(parsed, node, tgt.value.id, func.name))
                # name += / name -= üzerine (AugAssign)
                if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                    if node.target.id in globals_mut:
                        if _is_lock_acquisition_around(node.lineno, func):
                            continue
                        issues.append(self._make(parsed, node, node.target.id, func.name))

        return issues

    def _make(
        self,
        parsed: ParsedFile,
        node: ast.AST,
        var: str,
        func_name: str,
    ) -> IssueCandidate:
        ls = node.lineno
        return self.make_issue(
            file=parsed.file_path,
            line_start=ls,
            line_end=node.end_lineno or ls,
            snippet=snippet_for(parsed, ls, ls, context=1),
            explanation=(
                f"`async def {func_name}` içinde global `{var}` mutate ediliyor; lock yok. "
                "Eşzamanlı istekler birbirinin değişikliğini bozabilir. "
                "`asyncio.Lock()` ile koru veya state'i request-local yap."
            ),
            static_confidence=0.55,
            extra={"variable": var, "async_func": func_name},
        )
