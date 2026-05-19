"""Kaynak → AST: Python (`ast`) ve JavaScript/TypeScript (Tree-sitter).

Okunabilir her kaynak dosyası parse edilir. Tree-sitter başarısız olsa bile
`ParsedFile` döner; JS/TS ve Python için metin tabanlı kurallar devreye girer.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from analysis.languages import language_for_path

logger = logging.getLogger(__name__)


@dataclass
class ParsedFile:
    file_path: str
    source: str
    tree: Any
    lines: list[str]
    language: str
    parse_ok: bool = True
    parse_note: str = ""

    @property
    def is_python(self) -> bool:
        return self.language == "python"

    @property
    def has_ast(self) -> bool:
        if self.language == "python":
            return isinstance(self.tree, ast.AST)
        return self.tree is not None


class ParseError(Exception):
    pass


_TS_PARSERS: dict[str, Any] = {}
_TS_AVAILABLE: Optional[bool] = None
_TS_ERROR: str = ""


def _tree_sitter_available() -> bool:
    global _TS_AVAILABLE, _TS_ERROR
    if _TS_AVAILABLE is not None:
        return _TS_AVAILABLE
    try:
        from tree_sitter import Language, Parser  # noqa: F401

        _TS_AVAILABLE = True
    except Exception as e:
        _TS_ERROR = str(e)
        logger.warning("Tree-sitter native binding yüklenemedi: %s", e)
        _TS_AVAILABLE = False
    return _TS_AVAILABLE


def tree_sitter_status() -> dict[str, Any]:
    """Sağlık kontrolü / teşhis."""
    ok = _tree_sitter_available()
    out: dict[str, Any] = {"available": ok, "error": _TS_ERROR if not ok else ""}
    if ok:
        out["languages"] = validate_multilang_parser()
    return out


def validate_multilang_parser() -> dict[str, bool]:
    """Üç dil için gerçek parse testi — startup / health check."""
    global _TS_PARSERS
    _TS_PARSERS.clear()
    checks: dict[str, bool] = {}
    samples = [
        ("python", "x = 1\n", "probe.py"),
        ("javascript", "const x = 1;\nfetch(url);\n", "probe.js"),
        ("typescript", "const x: number = 1;\n", "probe.ts"),
    ]
    for lang, src, fname in samples:
        try:
            pf = parse_source(src, fname, language=lang)
            checks[lang] = pf.has_ast
        except Exception:
            checks[lang] = False
    return checks


def _make_language(ts_mod: Any, *, tsx: bool = False) -> Any:
    """tree-sitter 0.24 ve 0.25+ Language API uyumluluğu."""
    from tree_sitter import Language

    if tsx and hasattr(ts_mod, "language_tsx"):
        raw = ts_mod.language_tsx()
    elif hasattr(ts_mod, "language_typescript"):
        raw = ts_mod.language_typescript()
    elif hasattr(ts_mod, "language"):
        raw = ts_mod.language()
    else:
        raise ParseError("Tree-sitter dil modülünde language() bulunamadı")

    try:
        return Language(raw)
    except TypeError:
        # Eski API: Language.build_library gerekmez; doğrudan capsule
        return Language(raw)  # type: ignore[misc]


def _tree_sitter_parser(language: str, path: Path) -> Any:
    if not _tree_sitter_available():
        raise ParseError(f"Tree-sitter kullanılamıyor: {_TS_ERROR}")

    from tree_sitter import Parser

    ext = path.suffix.lower()
    cache_key = f"{language}:{ext}"
    if cache_key in _TS_PARSERS:
        return _TS_PARSERS[cache_key]

    if language == "javascript":
        import tree_sitter_javascript as ts_mod

        lang = _make_language(ts_mod)
    elif language == "typescript":
        import tree_sitter_typescript as ts_mod

        lang = _make_language(ts_mod, tsx=(ext == ".tsx"))
    else:
        raise ParseError(f"Tree-sitter desteklenmeyen dil: {language}")

    parser = Parser(lang)
    _TS_PARSERS[cache_key] = parser
    return parser


def _read_source(path: Path) -> tuple[Optional[str], str]:
    """Kaynak oku; başarısızsa (None, hata mesajı)."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        # PowerShell / Windows BOM
        if raw.startswith("\ufeff"):
            raw = raw.lstrip("\ufeff")
        return raw, ""
    except OSError as e:
        msg = f"OSError: {e}"
        logger.error("Dosya okunamadı %s: %s", path, e)
        return None, msg


def parse_source(
    source: str,
    file_path: str = "<string>",
    *,
    language: Optional[str] = None,
) -> ParsedFile:
    lang = language or language_for_path(file_path)
    lines = source.splitlines()
    tree: Any = None
    parse_ok = True
    parse_note = ""

    if lang == "python":
        try:
            tree = ast.parse(source, filename=file_path, type_comments=False)
        except SyntaxError as e:
            parse_ok = False
            parse_note = f"Python syntax: {e.msg}"
            logger.warning("Python syntax hatası %s: %s — metin kuralları devam", file_path, e.msg)
    elif lang in {"javascript", "typescript"}:
        try:
            parser = _tree_sitter_parser(lang, Path(file_path))
            parsed_tree = parser.parse(bytes(source, "utf-8"))
            if parsed_tree.root_node.has_error:
                parse_note = "Tree-sitter parse uyarısı (kısmi ağaç)"
                logger.warning("Tree-sitter uyarı %s: root has_error", file_path)
            tree = parsed_tree
        except Exception as e:
            parse_ok = False
            parse_note = f"Tree-sitter: {e}"
            logger.warning("JS/TS AST yok, metin kuralları kullanılacak %s: %s", file_path, e)
    else:
        raise ParseError(f"Desteklenmeyen dil: {lang}")

    return ParsedFile(
        file_path=file_path,
        source=source,
        tree=tree,
        lines=lines,
        language=lang,
        parse_ok=parse_ok,
        parse_note=parse_note,
    )


def parse_file(
    path: Path | str,
    *,
    language: Optional[str] = None,
) -> Optional[ParsedFile]:
    """Dosyayı oku ve parse et.

    Diskten okuma başarılıysa **her zaman** `ParsedFile` döner.
    Yalnızca dosya okunamazsa `None`.
    """
    p = Path(path).resolve()
    lang = language or language_for_path(p)
    source, err = _read_source(p)
    if source is None:
        return None

    rel_hint = str(p)
    try:
        return parse_source(source, rel_hint, language=lang)
    except ParseError as e:
        logger.error("ParseError %s: %s — kaynak metin korunuyor", p, e)
        return ParsedFile(
            file_path=rel_hint,
            source=source,
            tree=None,
            lines=source.splitlines(),
            language=lang,
            parse_ok=False,
            parse_note=str(e),
        )


def snippet_for(parsed: ParsedFile, line_start: int, line_end: int, context: int = 0) -> str:
    if not parsed.lines:
        return ""
    lo = max(1, line_start - context)
    hi = min(len(parsed.lines), line_end + context)
    return "\n".join(parsed.lines[lo - 1 : hi])
