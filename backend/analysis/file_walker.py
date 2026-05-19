"""Repo dosyalarını yürü — Python, JavaScript, TypeScript kaynakları.

Uzantılar: .py, .pyi, .js, .jsx, .mjs, .cjs, .ts, .tsx
node_modules, .next, venv vb. hariç; kaynak kod asla uzantı nedeniyle atlanmaz.
"""

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from analysis.languages import LANGUAGE_EXTENSIONS, SUPPORTED_LANGUAGES

# Yürürken atlanan dizin isimleri (üçüncü parti / build çıktıları).
EXCLUDED_DIR_NAMES: set[str] = {
    "node_modules",
    "tmp",
    "venv",
    ".venv",
    "env",
    ".git",
    "dist",
    "build",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "coverage",
    "htmlcov",
    ".tox",
    ".idea",
    ".vscode",
    ".cache",
    "site-packages",
    "egg-info",
    ".turbo",
    ".nuxt",
    "out",
    "target",
    "vendor",
    "bower_components",
}

# Kaynak kod dizinlerine öncelik (cap uygulanırken)
PRIORITY_DIR_NAMES: set[str] = {
    "src",
    "lib",
    "app",
    "pages",
    "components",
    "api",
    "server",
    "routes",
    "handlers",
    "services",
    "models",
    "views",
    "controllers",
    "backend",
    "frontend",
    "packages",
}

# İzin verilen gizli dizinler (kaynak içerebilir)
ALLOWED_DOT_DIRS: set[str] = {".github"}

_ALL_EXTENSIONS: dict[str, str] = {}
for _lang, _exts in LANGUAGE_EXTENSIONS.items():
    for _ext in _exts:
        _ALL_EXTENSIONS[_ext] = _lang


@dataclass(frozen=True)
class FileInfo:
    abs_path: Path
    rel_path: str
    size_bytes: int
    language: str

    @property
    def size_kb(self) -> float:
        return self.size_bytes / 1024


def _max_files() -> int:
    return int(os.getenv("MAX_FILES_TO_SCAN", "200"))


def _resolve_extensions(languages: list[str]) -> dict[str, str]:
    """Her zaman tüm desteklenen uzantıları dahil et (dil listesi filtrelemez)."""
    out: dict[str, str] = {}
    for lang in languages:
        for ext in LANGUAGE_EXTENSIONS.get(lang, set()):
            out[ext] = lang
    return out


def _should_skip_dir(name: str) -> bool:
    if name in EXCLUDED_DIR_NAMES:
        return True
    if name.startswith(".") and name not in ALLOWED_DOT_DIRS:
        return True
    return False


def _should_skip_file(rel_path: str) -> bool:
    """Test fixture'ları ve gömülü kötü-kod örneklerini üretim taramasından çıkar."""
    norm = rel_path.replace("\\", "/")
    lower = norm.lower()
    # tests/fixtures/... — kasıtlı kötü kod (birim test verisi)
    if "/tests/fixtures/" in f"/{lower}/" or lower.startswith("tests/fixtures/"):
        return True
    # tests/static_rules/ — kural testlerinde gömülü örnek string'ler
    if "/tests/static_rules/" in f"/{lower}/" or lower.startswith("tests/static_rules/"):
        return True
    name = Path(norm).name.lower()
    if name.endswith(
        (".test.js", ".test.ts", ".test.tsx", ".spec.js", ".spec.ts", ".spec.tsx")
    ):
        return True
    return False


def _priority_key(rel_path: str) -> tuple:
    """Düşük skor = daha yüksek öncelik."""
    parts = rel_path.lower().replace("\\", "/").split("/")
    dir_bonus = sum(-50 for p in parts if p in PRIORITY_DIR_NAMES)
    depth = len(parts)
    name = parts[-1] if parts else rel_path
    deprioritize = 30 if name.startswith("test_") or name.endswith("_test.py") else 0
    return (dir_bonus + deprioritize, depth)


def _file_sort_key(f: FileInfo) -> tuple:
    pk = _priority_key(f.rel_path)
    return (pk[0], pk[1], f.size_bytes, f.rel_path)


def _apply_cap_balanced(results: list[FileInfo], cap: int) -> list[FileInfo]:
    """Cap aşımında her dilden dosya koru; küçük kaynak dosyalar öncelikli."""
    if len(results) <= cap:
        return results

    by_lang: dict[str, list[FileInfo]] = defaultdict(list)
    for f in results:
        by_lang[f.language].append(f)

    langs_present = [lang for lang in SUPPORTED_LANGUAGES if by_lang.get(lang)]
    if not langs_present:
        return results[:cap]

    per_lang = max(1, cap // len(langs_present))
    picked: list[FileInfo] = []
    picked_paths: set[str] = set()

    for lang in langs_present:
        bucket = sorted(
            by_lang[lang],
            key=lambda f: (f.size_bytes > 500_000, f.size_bytes, _file_sort_key(f)),
        )
        for f in bucket[:per_lang]:
            if f.rel_path not in picked_paths:
                picked.append(f)
                picked_paths.add(f.rel_path)

    if len(picked) < cap:
        rest = sorted(
            [f for f in results if f.rel_path not in picked_paths],
            key=lambda f: (f.size_bytes > 500_000, f.size_bytes, _file_sort_key(f)),
        )
        for f in rest:
            if len(picked) >= cap:
                break
            picked.append(f)
            picked_paths.add(f.rel_path)

    picked.sort(key=_file_sort_key)
    return picked


def walk_files(
    repo_path: Path | str,
    languages: Optional[list[str]] = None,
    *,
    max_files: Optional[int] = None,
) -> list[FileInfo]:
    """Repo altındaki .py / .js / .jsx / .ts / .tsx kaynak dosyalarını döndür."""
    repo_path = Path(repo_path).resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        raise FileNotFoundError(f"Repo yolu bulunamadı: {repo_path}")

    # Varsayılan: üç dil — uzantıya göre filtrelenir, kaynak atlanmaz
    languages = languages or list(SUPPORTED_LANGUAGES)
    cap = max_files if max_files is not None else _max_files()
    ext_to_lang = _resolve_extensions(languages)

    results: list[FileInfo] = []

    for root, dirs, files in os.walk(repo_path, topdown=True, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not _should_skip_dir(d))

        for fname in sorted(files):
            if fname.startswith("."):
                continue
            ext = Path(fname).suffix.lower()
            if ext not in ext_to_lang:
                continue
            abs_path = Path(root) / fname
            if not abs_path.is_file():
                continue
            try:
                size = abs_path.stat().st_size
            except OSError:
                continue
            rel = abs_path.relative_to(repo_path).as_posix()
            if _should_skip_file(rel):
                continue
            results.append(
                FileInfo(
                    abs_path=abs_path,
                    rel_path=rel,
                    size_bytes=size,
                    language=ext_to_lang[ext],
                )
            )

    results.sort(key=_file_sort_key)
    return _apply_cap_balanced(results, cap)


def detect_languages(repo_path: Path | str) -> list[str]:
    """Repoda bulunan diller (bilgi amaçlı)."""
    repo_path = Path(repo_path).resolve()
    found: set[str] = set()

    for root, dirs, files in os.walk(repo_path, topdown=True):
        dirs[:] = [d for d in dirs if not _should_skip_dir(d)]
        for fname in files:
            ext = Path(fname).suffix.lower()
            lang = _ALL_EXTENSIONS.get(ext)
            if lang:
                found.add(lang)
        if len(found) >= len(SUPPORTED_LANGUAGES):
            break

    return sorted(found)


def count_all_source_files(repo_path: Path | str) -> int:
    """Cap uygulanmadan toplam kaynak dosya sayısı."""
    return len(walk_files(repo_path, max_files=10**9))


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="analysis.file_walker")
    parser.add_argument("path", help="Repo yolu")
    parser.add_argument(
        "--lang",
        action="append",
        default=None,
        help="Dil (tekrarlanabilir). Varsayılan: python+javascript+typescript",
    )
    parser.add_argument("--max", type=int, default=None, help="Maks dosya sayısı")
    args = parser.parse_args()

    files = walk_files(args.path, languages=args.lang, max_files=args.max)
    total_kb = sum(f.size_bytes for f in files) / 1024
    print(f"[OK] {len(files)} dosya, toplam {total_kb:.1f} KB")
    for f in files[:20]:
        print(f"  {f.size_kb:7.1f} KB  {f.language:10}  {f.rel_path}")
    if len(files) > 20:
        print(f"  ... ve {len(files) - 20} dosya daha")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
