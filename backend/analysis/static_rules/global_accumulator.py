"""GLOBAL_ACCUMULATOR — modül-level liste/dict üzerine sürekli append/yazma."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule


class GlobalAccumulatorRule(StaticRule):
    code = "GLOBAL_ACCUMULATOR"
    category = "memory"
    severity = "high"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []

        # 1) Modül seviyesinde boş liste/dict atamaları → aday akümülatörler
        accumulators: dict[str, ast.Assign] = {}
        for node in parsed.tree.body if hasattr(parsed.tree, "body") else []:
            if not isinstance(node, ast.Assign):
                continue
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            name = node.targets[0].id
            # cache/memo isimleri UNBOUNDED_CACHE'in alanı; burada hariç tut
            if "cache" in name.lower() or "memo" in name.lower():
                continue
            rhs = node.value
            is_empty_list = isinstance(rhs, ast.List) and not rhs.elts
            is_empty_dict = isinstance(rhs, ast.Dict) and not rhs.keys
            if is_empty_list or is_empty_dict:
                accumulators[name] = node

        if not accumulators:
            return issues

        # 2) Fonksiyon içinde global isimlere .append() ya da subscript yazımı var mı?
        appends: dict[str, ast.AST] = {}
        removes: dict[str, bool] = {n: False for n in accumulators}

        for func in ast.walk(parsed.tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(func):
                # name.append(...)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id in accumulators
                        and node.func.attr in {"append", "extend", "add", "update"}
                    ):
                        appends.setdefault(node.func.value.id, node)
                    if (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id in accumulators
                        and node.func.attr in {"pop", "remove", "clear", "popitem"}
                    ):
                        removes[node.func.value.id] = True
                # name[k] = v
                if isinstance(node, ast.Assign):
                    for tgt in node.targets:
                        if (
                            isinstance(tgt, ast.Subscript)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id in accumulators
                        ):
                            appends.setdefault(tgt.value.id, node)
                # del name[k]
                if isinstance(node, ast.Delete):
                    for tgt in node.targets:
                        if (
                            isinstance(tgt, ast.Subscript)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id in accumulators
                        ):
                            removes[tgt.value.id] = True

        for name, ev in appends.items():
            if removes.get(name):
                continue  # eviction var → akümülatör değil
            assign = accumulators[name]
            issues.append(
                self.make_issue(
                    file=parsed.file_path,
                    line_start=assign.lineno,
                    line_end=assign.end_lineno or assign.lineno,
                    snippet=snippet_for(parsed, assign.lineno, assign.lineno),
                    explanation=(
                        f"Modül-level `{name}` koleksiyonuna handler içinde "
                        "ekleme yapılıyor ama tahliye yok. Klasik bellek sızıntısı: "
                        "sunucu zamanla şişer, sonunda OOM."
                    ),
                    static_confidence=0.85,
                    extra={"variable": name, "first_write_line": ev.lineno},
                )
            )

        return issues
