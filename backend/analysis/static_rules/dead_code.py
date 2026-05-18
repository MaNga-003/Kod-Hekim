"""DEAD_CODE — tanımlı ama hiç çağrılmayan/referans verilmeyen fonksiyon veya sınıf (proje seviyesi)."""

from __future__ import annotations

import ast
from pathlib import Path

from analysis.ast_parser import ParsedFile
from analysis.static_rules.base import IssueCandidate, ProjectStaticRule


def _is_test_file(path: str) -> bool:
    p = Path(path)
    name = p.name
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or "tests" in p.parts
        or "test" in p.parts
    )


def _is_init(path: str) -> bool:
    return Path(path).name == "__init__.py"


class DeadCodeRule(ProjectStaticRule):
    code = "DEAD_CODE"
    category = "quality"
    severity = "low"

    def scan_project(self, parsed_files: list[ParsedFile]) -> list[IssueCandidate]:
        if not parsed_files:
            return []

        # Definitions: (name → list of (file, lineno))
        definitions: dict[str, list[tuple[str, int]]] = {}
        # Toplam referans sayısı (tanım hariç)
        references: dict[str, int] = {}

        for pf in parsed_files:
            if _is_test_file(pf.file_path) or _is_init(pf.file_path):
                continue
            for node in ast.walk(pf.tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = node.name
                    if name.startswith("_"):
                        continue  # private + dunder; flag etme
                    # Method değil, modül-level tanımı al — sade için: hepsini kaydet
                    definitions.setdefault(name, []).append((pf.file_path, node.lineno))

        # Tüm dosyalardaki Name/Attribute kullanımları → referans sayımı
        all_names_in_use: dict[str, int] = {}
        for pf in parsed_files:
            for node in ast.walk(pf.tree):
                if isinstance(node, ast.Name):
                    all_names_in_use[node.id] = all_names_in_use.get(node.id, 0) + 1
                elif isinstance(node, ast.Attribute):
                    all_names_in_use[node.attr] = all_names_in_use.get(node.attr, 0) + 1
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        nm = alias.asname or alias.name
                        all_names_in_use[nm] = all_names_in_use.get(nm, 0) + 1

        # `def foo(): ...` FunctionDef node'u Name yaratmaz — sadece çağrı/referans Name üretir.
        # Yani all_names_in_use'taki sayı zaten "dış kullanım" sayısıdır.
        issues: list[IssueCandidate] = []
        for name, defs in definitions.items():
            if all_names_in_use.get(name, 0) > 0:
                continue
            for file_path, lineno in defs:
                issues.append(
                    self.make_issue(
                        file=file_path,
                        line_start=lineno,
                        line_end=lineno,
                        snippet=f"def/class {name}",
                        explanation=(
                            f"`{name}` tanımlı ama proje içinde (test/__init__ hariç) "
                            "hiçbir yerden referans alınmıyor. Ölü kod gibi görünüyor — "
                            "kullanılıyorsa export et, kullanılmıyorsa sil."
                        ),
                        static_confidence=0.55,
                        extra={"symbol": name},
                    )
                )

        return issues
