"""SHADOW_VARIABLE — built-in ya da dış scope adıyla çakışan değişken."""

from __future__ import annotations

import ast
import builtins

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule


_BUILTINS = set(dir(builtins))
# Sıkça çakışan ama "kabul edilebilir" — flag etmiyoruz (gürültü azaltma)
_SAFE_NAMES = {"_", "self", "cls"}


class ShadowVariableRule(StaticRule):
    code = "SHADOW_VARIABLE"
    category = "quality"
    severity = "low"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []
        seen_lines: set[int] = set()

        for func in ast.walk(parsed.tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Fonksiyon parametreleri ve fonksiyon içinde atanan isimler
            param_names = {a.arg for a in func.args.args}
            param_names |= {a.arg for a in func.args.kwonlyargs}

            for node in ast.walk(func):
                names_here: list[tuple[str, int, int]] = []
                if isinstance(node, ast.Assign):
                    for tgt in node.targets:
                        if isinstance(tgt, ast.Name):
                            names_here.append((tgt.id, tgt.lineno, tgt.end_lineno or tgt.lineno))
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    names_here.append(
                        (node.target.id, node.target.lineno, node.target.end_lineno or node.target.lineno)
                    )

                for name, ls, le in names_here:
                    if name in _SAFE_NAMES:
                        continue
                    if name in _BUILTINS:
                        if ls in seen_lines:
                            continue
                        seen_lines.add(ls)
                        issues.append(
                            self.make_issue(
                                file=parsed.file_path,
                                line_start=ls,
                                line_end=le,
                                snippet=snippet_for(parsed, ls, ls),
                                explanation=(
                                    f"`{name}` Python built-in ismini gölgeliyor. "
                                    "Aynı scope'ta built-in artık erişilemez → kafa karıştırıcı bug yüzeyi."
                                ),
                                static_confidence=0.85,
                                extra={"shadowed": name, "kind": "builtin"},
                            )
                        )

        return issues
