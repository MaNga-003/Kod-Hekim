"""Repo dosyalarını yürü, uzantı filtreleri ve exclude listesiyle.

MVP: yalnız Python (.py). JS/TS sonraki sürüme bırakıldı (developer.md §5).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Yürürken atlanan dizin isimleri.
EXCLUDED_DIR_NAMES: set[str] = {
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
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
}

# Dil → uzantı seti eşlemesi. MVP'de yalnız python kullanılıyor.
LANGUAGE_EXTENSIONS: dict[str, set[str]] = {
    "python": {".py", ".pyi"},
    "javascript": {".js", ".jsx", ".mjs", ".cjs"},
    "typescript": {".ts", ".tsx"},
}


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
    """Verilen dillerin uzantılarını → dil adına eşle."""
    out: dict[str, str] = {}
    for lang in languages:
        for ext in LANGUAGE_EXTENSIONS.get(lang, set()):
            out[ext] = lang
    return out


def walk_files(
    repo_path: Path | str,
    languages: Optional[list[str]] = None,
    *,
    max_files: Optional[int] = None,
) -> list[FileInfo]:
    """Repo altındaki uygun dosyaları döndür.

    Sıralama: boyut (büyükten küçüğe). `max_files` aşılırsa en büyük dosyalar tutulur
    — küçük dosyalardan ziyade büyük dosyalar daha çok kaynak/karmaşıklık taşır.

    Args:
        repo_path: Clone edilmiş repo'nun kökü.
        languages: ["python"] (varsayılan). MVP'de tek dil.
        max_files: Override; verilmezse env'den `MAX_FILES_TO_SCAN`.
    """
    repo_path = Path(repo_path).resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        raise FileNotFoundError(f"Repo yolu bulunamadı: {repo_path}")

    languages = languages or ["python"]
    cap = max_files if max_files is not None else _max_files()
    ext_to_lang = _resolve_extensions(languages)

    results: list[FileInfo] = []

    for root, dirs, files in os.walk(repo_path):
        # In-place mutate to prune walk
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIR_NAMES and not d.startswith(".")]

        for fname in files:
            ext = Path(fname).suffix.lower()
            if ext not in ext_to_lang:
                continue
            abs_path = Path(root) / fname
            try:
                size = abs_path.stat().st_size
            except OSError:
                continue
            rel = abs_path.relative_to(repo_path).as_posix()
            results.append(
                FileInfo(
                    abs_path=abs_path,
                    rel_path=rel,
                    size_bytes=size,
                    language=ext_to_lang[ext],
                )
            )

    # Büyük → küçük; eşitlikte path stabil sıralama için ikincil key
    results.sort(key=lambda f: (-f.size_bytes, f.rel_path))

    if len(results) > cap:
        results = results[:cap]

    return results


def detect_languages(repo_path: Path | str) -> list[str]:
    """Repo'da hangi desteklenen dillerin bulunduğunu tespit et.

    İlk eşleşmeleri görür görmez döndürür (büyük repo'larda hızlı).
    """
    repo_path = Path(repo_path).resolve()
    found: set[str] = set()

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIR_NAMES and not d.startswith(".")]
        for fname in files:
            ext = Path(fname).suffix.lower()
            for lang, exts in LANGUAGE_EXTENSIONS.items():
                if ext in exts:
                    found.add(lang)
        if len(found) >= len(LANGUAGE_EXTENSIONS):
            break

    return sorted(found)


# ---------------------------------------------------------------------------
# CLI (debug için)
# ---------------------------------------------------------------------------


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="analysis.file_walker")
    parser.add_argument("path", help="Repo yolu")
    parser.add_argument(
        "--lang",
        action="append",
        default=None,
        help="Dil (tekrarlanabilir). Varsayılan: python",
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
