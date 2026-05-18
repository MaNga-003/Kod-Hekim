"""REPEATED_COMPUTE — döngü içinde aynı sabit-argüman fonksiyon çağrısının tekrarı."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule, build_parent_map


def _call_signature(call: ast.Call) -> str | None:
    """Çağrıyı 'name(args)' biçiminde signature string'ine çevir — yalnız sabit/Name argümanlar."""
    try:
        func = ast.unparse(call.func)
        # Tüm argümanların literal Constant ya da Name olması gerekir;
        # döngü değişkenini içeren çağrıları flag etmek istemiyoruz.
        args = []
        for a in call.args:
            if isinstance(a, ast.Constant):
                args.append(repr(a.value))
            elif isinstance(a, ast.Name):
                args.append(a.id)
            else:
                return None
        for kw in call.keywords:
            if kw.arg is None:  # **kwargs
                return None
            if isinstance(kw.value, ast.Constant):
                args.append(f"{kw.arg}={kw.value.value!r}")
            elif isinstance(kw.value, ast.Name):
                args.append(f"{kw.arg}={kw.value.id}")
            else:
                return None
        return f"{func}({', '.join(args)})"
    except Exception:
        return None


def _names_used(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


class RepeatedComputeRule(StaticRule):
    code = "REPEATED_COMPUTE"
    category = "performance"
    severity = "low"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []
        parents = build_parent_map(parsed.tree)

        for loop in ast.walk(parsed.tree):
            if not isinstance(loop, (ast.For, ast.AsyncFor, ast.While)):
                continue

            # Döngü değişkenleri (bunlardan birini kullanan çağrı invariant değil)
            loop_vars: set[str] = set()
            if isinstance(loop, (ast.For, ast.AsyncFor)):
                if isinstance(loop.target, ast.Name):
                    loop_vars.add(loop.target.id)
                elif isinstance(loop.target, (ast.Tuple, ast.List)):
                    for elt in loop.target.elts:
                        if isinstance(elt, ast.Name):
                            loop_vars.add(elt.id)

            # Aynı imzalı çağrıyı en az 2 kez gör → flag
            seen: dict[str, list[ast.Call]] = {}
            for node in ast.walk(loop):
                if not isinstance(node, ast.Call):
                    continue
                # Yalnız direkt body'de değil; iç içe ama yine bu loop kapsayıcı olmalı.
                sig = _call_signature(node)
                if not sig:
                    continue
                if _names_used(node) & loop_vars:
                    continue  # döngü değişkeni → invariant değil
                seen.setdefault(sig, []).append(node)

            for sig, calls in seen.items():
                if len(calls) < 2:
                    continue
                first = calls[0]
                issues.append(
                    self.make_issue(
                        file=parsed.file_path,
                        line_start=first.lineno,
                        line_end=first.end_lineno or first.lineno,
                        snippet=snippet_for(parsed, first.lineno, first.lineno, context=1),
                        explanation=(
                            f"`{sig}` döngü içinde {len(calls)} kez ve aynı argümanlarla "
                            "çağrılıyor (loop-invariant). Döngü dışına çıkar veya cache et."
                        ),
                        static_confidence=0.75,
                        extra={"signature": sig, "occurrences": len(calls)},
                    )
                )
        return issues
