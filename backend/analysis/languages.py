"""Desteklenen analiz dilleri ve repo dil çözümlemesi."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

SUPPORTED_LANGUAGES: list[str] = ["python", "javascript", "typescript"]

LANGUAGE_EXTENSIONS: dict[str, set[str]] = {
    "python": {".py", ".pyi"},
    "javascript": {".js", ".jsx", ".mjs", ".cjs"},
    "typescript": {".ts", ".tsx"},
}


def language_for_extension(ext: str) -> Optional[str]:
    ext = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
    for lang, exts in LANGUAGE_EXTENSIONS.items():
        if ext in exts:
            return lang
    return None


def language_for_path(path: Path | str) -> str:
    lang = language_for_extension(Path(path).suffix)
    return lang or "python"


def resolve_languages(
    repo_path: Path | str,
    explicit: Optional[list[str]] = None,
) -> list[str]:
    """Analizde kullanılacak dil listesi.

    Varsayılan: Python + JavaScript + TypeScript — hepsi her zaman taranır.
    `file_walker` uzantıya göre filtreler; repoda olmayan diller boş döner.
    """
    if explicit:
        return [lang for lang in explicit if lang in SUPPORTED_LANGUAGES]
    return list(SUPPORTED_LANGUAGES)
