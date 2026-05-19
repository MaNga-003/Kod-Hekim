"""Derin mod için repo özet AST üretici.

Tam dosya AST'leri LLM token bütçesine sığmayacak kadar büyüktür.
Bu modül her dosya için **anahatları** çıkarır: import grafı, fonksiyon imzaları,
class yapısı, decorator hint'leri, entry point işareti.

developer.md §3.3 (Derin mod) referansı.
"""

from __future__ import annotations

import ast as _ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from analysis.file_walker import walk_files
from analysis.languages import resolve_languages


# ---------------------------------------------------------------------------
# Veri tipleri
# ---------------------------------------------------------------------------


@dataclass
class FunctionInfo:
    name: str
    line_start: int
    line_end: int
    args: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    is_async: bool = False

    def to_outline(self) -> str:
        decs = "".join(f"@{d}  " for d in self.decorators)
        prefix = "async def" if self.is_async else "def"
        sig = ", ".join(self.args)
        return f"  {decs}{prefix} {self.name}({sig})  # L{self.line_start}-{self.line_end}"


@dataclass
class ClassInfo:
    name: str
    line_start: int
    line_end: int
    bases: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)

    def to_outline(self) -> str:
        base = f"({', '.join(self.bases)})" if self.bases else ""
        more = "…" if len(self.methods) > 8 else ""
        meths = ", ".join(self.methods[:8]) + more
        return f"  class {self.name}{base}  # L{self.line_start}-{self.line_end}  methods: {meths}"


@dataclass
class FileSummary:
    file: str  # repo-relative path, "/" ayraçlı
    line_count: int
    imports: list[str] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    has_main_entry: bool = False
    route_decorators: list[str] = field(default_factory=list)

    def to_outline(self) -> str:
        head = [f"== {self.file} ({self.line_count} satır) =="]
        if self.imports:
            head.append(f"imports: {', '.join(self.imports[:20])}")
        for c in self.classes:
            head.append(c.to_outline())
        for fn in self.functions:
            head.append(fn.to_outline())
        if self.has_main_entry:
            head.append("  # has __main__ guard")
        if self.route_decorators:
            head.append(f"  # route decorators: {', '.join(self.route_decorators[:8])}")
        return "\n".join(head)


@dataclass
class RepoSummary:
    files: list[FileSummary] = field(default_factory=list)
    total_lines: int = 0
    detected_frameworks: list[str] = field(default_factory=list)

    def to_outline(self) -> str:
        head = f"# Repo özeti: {len(self.files)} kaynak dosyası, ~{self.total_lines} satır"
        if self.detected_frameworks:
            head += f"\n# Tespit edilen framework'ler: {', '.join(self.detected_frameworks)}"
        body = "\n\n".join(f.to_outline() for f in self.files)
        return head + "\n\n" + body if body else head


# ---------------------------------------------------------------------------
# Framework / route decorator tespiti
# ---------------------------------------------------------------------------


_FRAMEWORK_HINTS: dict[str, list[str]] = {
    "fastapi": ["fastapi"],
    "flask": ["flask"],
    "django": ["django"],
    "starlette": ["starlette"],
    "celery": ["celery"],
    "sqlalchemy": ["sqlalchemy"],
    "pydantic": ["pydantic"],
    "click": ["click"],
    "typer": ["typer"],
}


_ROUTE_DECORATOR_PATTERN = re.compile(
    r"^(?:app|router|blueprint)\.(?:get|post|put|delete|patch|route|task|websocket)\b"
)


def _decorator_name(node: _ast.expr) -> str:
    if isinstance(node, _ast.Name):
        return node.id
    if isinstance(node, _ast.Attribute):
        parts: list[str] = []
        cur: Optional[_ast.AST] = node
        while isinstance(cur, _ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, _ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    if isinstance(node, _ast.Call):
        return _decorator_name(node.func) + "(…)"
    return "?"


def _is_main_guard(node: _ast.If) -> bool:
    """`if __name__ == "__main__":` tespiti."""
    test = node.test
    if not isinstance(test, _ast.Compare) or len(test.ops) != 1:
        return False
    if not isinstance(test.ops[0], _ast.Eq):
        return False
    left, right = test.left, test.comparators[0]
    if isinstance(left, _ast.Name) and left.id == "__name__":
        if isinstance(right, _ast.Constant) and right.value == "__main__":
            return True
    return False


# ---------------------------------------------------------------------------
# Dosya özetleme
# ---------------------------------------------------------------------------


def _function_info(node: _ast.FunctionDef | _ast.AsyncFunctionDef) -> FunctionInfo:
    args = [a.arg for a in node.args.args]
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    decorators = [_decorator_name(d) for d in node.decorator_list]
    return FunctionInfo(
        name=node.name,
        line_start=node.lineno,
        line_end=node.end_lineno or node.lineno,
        args=args,
        decorators=decorators,
        is_async=isinstance(node, _ast.AsyncFunctionDef),
    )


def _class_info(node: _ast.ClassDef) -> ClassInfo:
    methods = [
        b.name
        for b in node.body
        if isinstance(b, (_ast.FunctionDef, _ast.AsyncFunctionDef))
    ]
    bases = [_decorator_name(b) for b in node.bases]
    return ClassInfo(
        name=node.name,
        line_start=node.lineno,
        line_end=node.end_lineno or node.lineno,
        bases=bases,
        methods=methods,
    )


def summarize_file(path: Path, repo_root: Path) -> Optional[FileSummary]:
    """Tek Python dosyası için özet AST çıkar; parse hatasında `None`."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    try:
        tree = _ast.parse(source)
    except SyntaxError:
        return None

    try:
        rel = str(path.resolve().relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        rel = path.name

    summary = FileSummary(file=rel, line_count=len(source.splitlines()))

    for node in tree.body:
        if isinstance(node, _ast.Import):
            summary.imports.extend(n.name for n in node.names)
        elif isinstance(node, _ast.ImportFrom):
            module = node.module or ""
            for n in node.names:
                summary.imports.append(f"{module}.{n.name}" if module else n.name)
        elif isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            fn = _function_info(node)
            summary.functions.append(fn)
            for d in fn.decorators:
                if _ROUTE_DECORATOR_PATTERN.search(d):
                    summary.route_decorators.append(d)
        elif isinstance(node, _ast.ClassDef):
            summary.classes.append(_class_info(node))
        elif isinstance(node, _ast.If) and _is_main_guard(node):
            summary.has_main_entry = True

    return summary


# ---------------------------------------------------------------------------
# Repo özetleme
# ---------------------------------------------------------------------------


def _detect_frameworks(files: list[FileSummary]) -> list[str]:
    found: set[str] = set()
    for fs in files:
        for imp in fs.imports:
            low = imp.lower()
            for fw, hints in _FRAMEWORK_HINTS.items():
                if any(h in low for h in hints):
                    found.add(fw)
    return sorted(found)


_JS_IMPORT = re.compile(
    r"""import\s+(?:[\w*{}\s,]+\s+from\s+)?['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\)"""
)
_JS_FN = re.compile(
    r"(?:export\s+)?(?:async\s+)?function\s+(\w+)|(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\("
)
_JS_ROUTE = re.compile(r"@(?:Get|Post|Put|Delete|Patch|Controller)\b|app\.(get|post|put|delete)\s*\(")


def summarize_js_ts_file(path: Path, repo_root: Path, language: str) -> Optional[FileSummary]:
    """JS/TS dosyası için hafif özet (regex tabanlı)."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    try:
        rel = str(path.resolve().relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        rel = path.name

    summary = FileSummary(file=rel, line_count=len(source.splitlines()))
    for m in _JS_IMPORT.finditer(source):
        imp = m.group(1) or m.group(2)
        if imp:
            summary.imports.append(imp)
    for i, m in enumerate(_JS_FN.finditer(source), start=1):
        name = m.group(1) or m.group(2) or f"anon_{i}"
        line = source[: m.start()].count("\n") + 1
        summary.functions.append(
            FunctionInfo(name=name, line_start=line, line_end=line, is_async="async" in m.group(0))
        )
    for m in _JS_ROUTE.finditer(source):
        summary.route_decorators.append(m.group(0)[:40])
    return summary


def summarize_repo(repo_path: Path | str) -> RepoSummary:
    """Python, JavaScript ve TypeScript dosyaları için özet AST + framework tespiti."""
    repo_root = Path(repo_path).resolve()
    langs = resolve_languages(repo_root)
    summaries: list[FileSummary] = []
    for finfo in walk_files(repo_root, languages=langs):
        if finfo.language == "python":
            s = summarize_file(finfo.abs_path, repo_root)
        else:
            s = summarize_js_ts_file(finfo.abs_path, repo_root, finfo.language)
        if s:
            summaries.append(s)
    return RepoSummary(
        files=summaries,
        total_lines=sum(f.line_count for f in summaries),
        detected_frameworks=_detect_frameworks(summaries),
    )


# ---------------------------------------------------------------------------
# Token bütçesi (kabaca char/4)
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Çok kabaca tahmin: ~4 char ≈ 1 token (Python kodu için)."""
    return max(1, len(text) // 4)


def pick_full_inclusion_files(
    summary: RepoSummary,
    full_file_loader: Callable[[str], str],
    *,
    char_budget: int,
) -> list[tuple[str, str]]:
    """Tam kod inject edilecek dosyaları seç.

    Strateji (öncelik sırasıyla):
      1. route_decorators içeren dosyalar (entry point)
      2. has_main_entry dosyalar
      3. Diğer dosyalar (boyut sırasıyla, küçükten büyüğe — en çok dosya sığar)

    Args:
        summary: Repo özeti.
        full_file_loader: file path → kaynak string.
        char_budget: toplam karakter bütçesi.

    Returns:
        [(file_path, source), ...] — char_budget'ı aşmadan eklenmiş.
    """
    prioritized: list[FileSummary] = []
    seen: set[str] = set()

    # 1) Route decorator'lı (entry point)
    for f in summary.files:
        if f.route_decorators and f.file not in seen:
            prioritized.append(f)
            seen.add(f.file)
    # 2) __main__ guard
    for f in summary.files:
        if f.has_main_entry and f.file not in seen:
            prioritized.append(f)
            seen.add(f.file)
    # 3) Geri kalanı: küçükten büyüğe
    others = sorted(
        (f for f in summary.files if f.file not in seen),
        key=lambda f: f.line_count,
    )
    prioritized.extend(others)

    out: list[tuple[str, str]] = []
    used = 0
    for f in prioritized:
        try:
            src = full_file_loader(f.file)
        except OSError:
            continue
        cost = len(src) + len(f.file) + 32  # header/footer payı
        if used + cost > char_budget:
            continue
        out.append((f.file, src))
        used += cost

    return out
