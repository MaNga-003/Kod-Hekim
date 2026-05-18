"""CIRCULAR_IMPORT — modüller arası A → B → A import zinciri (proje seviyesi)."""

from __future__ import annotations

import ast
from pathlib import Path

from analysis.ast_parser import ParsedFile
from analysis.static_rules.base import IssueCandidate, ProjectStaticRule


def _file_to_module(file_path: str, root: Path | None) -> str:
    """`./pkg/sub/mod.py` → `pkg.sub.mod` (ya da kaba bir tahmin)."""
    p = Path(file_path)
    if root is not None:
        try:
            rel = p.relative_to(root)
        except ValueError:
            rel = p
    else:
        rel = p
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _module_imports(tree: ast.AST) -> list[str]:
    out: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                out.append(node.module)
    return out


def _find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Tarjan/Kosaraju yerine basit DFS — küçük grafiklerde yeterli."""
    cycles: list[list[str]] = []
    visited: dict[str, int] = {}  # 0=beyaz, 1=gri, 2=siyah
    stack: list[str] = []
    seen_cycles: set[tuple[str, ...]] = set()

    def dfs(node: str) -> None:
        visited[node] = 1
        stack.append(node)
        for nb in graph.get(node, []):
            color = visited.get(nb, 0)
            if color == 1:
                idx = stack.index(nb)
                cyc = stack[idx:] + [nb]
                key = tuple(sorted(cyc[:-1]))
                if key not in seen_cycles:
                    seen_cycles.add(key)
                    cycles.append(cyc)
            elif color == 0:
                dfs(nb)
        stack.pop()
        visited[node] = 2

    for n in list(graph.keys()):
        if visited.get(n, 0) == 0:
            dfs(n)
    return cycles


class CircularImportRule(ProjectStaticRule):
    code = "CIRCULAR_IMPORT"
    category = "quality"
    severity = "low"

    def scan_project(self, parsed_files: list[ParsedFile]) -> list[IssueCandidate]:
        if not parsed_files:
            return []

        # Repo kökünü en kısa ortak path olarak bul (cross-platform)
        paths = [Path(p.file_path).resolve() for p in parsed_files]
        try:
            from os.path import commonpath

            root = Path(commonpath([str(p) for p in paths]))
        except (ValueError, OSError):
            root = paths[0].parent

        # Modül adı → ParsedFile eşlemesi
        module_to_pf: dict[str, ParsedFile] = {}
        graph: dict[str, list[str]] = {}
        for pf in parsed_files:
            mod = _file_to_module(pf.file_path, root)
            module_to_pf[mod] = pf
            imports = _module_imports(pf.tree)
            # Yalnız repo içindeki modüllere bağ kur
            graph[mod] = []
        for mod, pf in module_to_pf.items():
            for imp in _module_imports(pf.tree):
                # imp tam isim, prefix ya da suffix olarak eşleşmeli
                # (relative-ish: "from b import x" → "pkg.b" ile eşle)
                for cand in module_to_pf:
                    if (
                        cand == imp
                        or cand.startswith(imp + ".")
                        or cand.endswith("." + imp)
                        or cand.rsplit(".", 1)[-1] == imp
                    ):
                        if cand != mod:
                            graph[mod].append(cand)
                        break

        cycles = _find_cycles(graph)

        issues: list[IssueCandidate] = []
        for cyc in cycles:
            # Döngüdeki ilk modülün dosyasında raporla
            first_mod = cyc[0]
            pf = module_to_pf.get(first_mod)
            if pf is None:
                continue
            chain = " → ".join(cyc)
            issues.append(
                self.make_issue(
                    file=pf.file_path,
                    line_start=1,
                    line_end=1,
                    snippet=chain,
                    explanation=(
                        f"Döngüsel import zinciri: {chain}. "
                        "Modüller startup'ta birbirine bağlı yüklenir → kafa karıştırıcı hata mesajları "
                        "ve startup zamanı artışı. Ortak parçaları üçüncü bir modüle taşı."
                    ),
                    static_confidence=0.9,
                    extra={"cycle": cyc},
                )
            )
        return issues
