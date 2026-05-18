"""LOAD_FULL_FILE — `f.read()` / `f.readlines()` yerine streaming kullanılmalı."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule


_FULL_READ_METHODS = {"read", "readlines"}


class LoadFullFileRule(StaticRule):
    code = "LOAD_FULL_FILE"
    category = "memory"
    severity = "low"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []
        for node in ast.walk(parsed.tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in _FULL_READ_METHODS:
                continue
            # .read(N) bir chunk size verirse atla (kullanıcı streaming yapıyor)
            if node.func.attr == "read" and node.args:
                continue
            issues.append(
                self.make_issue(
                    file=parsed.file_path,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    snippet=snippet_for(parsed, node.lineno, node.lineno),
                    explanation=(
                        f"`.{node.func.attr}()` dosyanın tamamını RAM'e yükler. "
                        "Büyük dosyalarda peak RAM patlar; `for line in f:` ile satır satır oku."
                    ),
                    static_confidence=0.6,
                    extra={"method": node.func.attr},
                )
            )
        return issues
