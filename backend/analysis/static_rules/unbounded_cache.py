"""UNBOUNDED_CACHE — `@lru_cache(maxsize=None)`, `@cache`, modül-level dict cache."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule


def _decorator_name(dec: ast.expr) -> str:
    """`functools.lru_cache` veya `lru_cache` gibi adı string'e çevir."""
    if isinstance(dec, ast.Call):
        return _decorator_name(dec.func)
    if isinstance(dec, ast.Attribute):
        parts: list[str] = [dec.attr]
        cur = dec.value
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    if isinstance(dec, ast.Name):
        return dec.id
    return ""


class UnboundedCacheRule(StaticRule):
    code = "UNBOUNDED_CACHE"
    category = "memory"
    severity = "high"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []

        # 1) Decorator-based caches
        for node in ast.walk(parsed.tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                name = _decorator_name(dec)
                short = name.split(".")[-1]
                if short == "cache":
                    # functools.cache (3.9+) — kalıcı sınırsız
                    issues.append(self._mk(parsed, dec, "@cache (functools.cache) sınırsız", node.name))
                    break
                if short == "lru_cache":
                    if not isinstance(dec, ast.Call) or not dec.keywords and not dec.args:
                        # @lru_cache (parantezsiz) — Python <3.8 default unbounded, 3.8+ default 128
                        # Doc isteği üzerine yine de hatırlatma.
                        issues.append(
                            self._mk(parsed, dec, "@lru_cache parantezsiz — maxsize'ı netleştir", node.name)
                        )
                        break
                    # @lru_cache(maxsize=None)
                    if isinstance(dec, ast.Call):
                        for kw in dec.keywords:
                            if (
                                kw.arg == "maxsize"
                                and isinstance(kw.value, ast.Constant)
                                and kw.value.value is None
                            ):
                                issues.append(
                                    self._mk(
                                        parsed,
                                        dec,
                                        "@lru_cache(maxsize=None) sınırsız",
                                        node.name,
                                    )
                                )
                                break

        # 2) Modül seviyesinde `_cache = {}` veya `cache = {}` benzeri,
        #    sonra `cache[key] = value` yazımı var ama silme/eviction yok.
        module_caches: dict[str, ast.Assign] = {}
        for node in parsed.tree.body if hasattr(parsed.tree, "body") else []:
            if isinstance(node, ast.Assign):
                # Tek hedefli atama, sağ taraf {} ya da dict()
                if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                    continue
                name = node.targets[0].id
                if not ("cache" in name.lower() or "memo" in name.lower()):
                    continue
                rhs = node.value
                is_empty_dict = (
                    isinstance(rhs, ast.Dict)
                    and not rhs.keys
                    or (isinstance(rhs, ast.Call) and isinstance(rhs.func, ast.Name) and rhs.func.id == "dict")
                )
                if is_empty_dict:
                    module_caches[name] = node

        if module_caches:
            # Yazma var mı, silme var mı?
            writes = {n: False for n in module_caches}
            deletes = {n: False for n in module_caches}
            for node in ast.walk(parsed.tree):
                # cache[key] = value (Subscript yazımı)
                if isinstance(node, ast.Assign):
                    for tgt in node.targets:
                        if isinstance(tgt, ast.Subscript) and isinstance(tgt.value, ast.Name):
                            if tgt.value.id in writes:
                                writes[tgt.value.id] = True
                # del cache[k] / cache.pop / cache.clear
                if isinstance(node, ast.Delete):
                    for tgt in node.targets:
                        if isinstance(tgt, ast.Subscript) and isinstance(tgt.value, ast.Name):
                            if tgt.value.id in deletes:
                                deletes[tgt.value.id] = True
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id in deletes
                        and node.func.attr in {"pop", "clear", "popitem"}
                    ):
                        deletes[node.func.value.id] = True

            for name, assign in module_caches.items():
                if writes[name] and not deletes[name]:
                    issues.append(
                        self._mk(
                            parsed,
                            assign,
                            f"Modül-level `{name} = {{}}` sınırsız büyüyor (yazma var, "
                            "silme/eviction yok)",
                            None,
                        )
                    )

        return issues

    def _mk(self, parsed: ParsedFile, node: ast.AST, reason: str, func_name) -> IssueCandidate:
        line_start = node.lineno
        line_end = node.end_lineno or line_start
        return self.make_issue(
            file=parsed.file_path,
            line_start=line_start,
            line_end=line_end,
            snippet=snippet_for(parsed, line_start, line_end),
            explanation=(
                f"{reason}. {'`' + func_name + '` ' if func_name else ''}"
                "süreç ayakta kaldıkça RAM büyür → OOM. "
                "Sınır koy: `@lru_cache(maxsize=N)` veya `cachetools.TTLCache`."
            ),
            static_confidence=0.85,
            extra={"reason": reason},
        )
