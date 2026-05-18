"""Python source → AST. İnce bir sarıcı; rules `ast` standart kütüphanesini kullanır.

`tree_sitter` desteği §J Derin mod için ileride; MVP'de yalnız stdlib ast yeter.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ParsedFile:
    file_path: str
    source: str
    tree: ast.AST
    lines: list[str]


class ParseError(Exception):
    pass


def parse_source(source: str, file_path: str = "<string>") -> ParsedFile:
    """Verilen kaynak metnini AST'ye dönüştür.

    Raises:
        ParseError: SyntaxError yakalandığında.
    """
    try:
        tree = ast.parse(source, filename=file_path, type_comments=False)
    except SyntaxError as e:
        raise ParseError(f"{file_path}: {e.msg} (line {e.lineno})") from e
    return ParsedFile(
        file_path=file_path,
        source=source,
        tree=tree,
        lines=source.splitlines(),
    )


def parse_file(path: Path | str) -> Optional[ParsedFile]:
    """Dosyayı oku ve parse et. SyntaxError'da None döndürür (rule motoru geçer)."""
    p = Path(path)
    try:
        source = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        return parse_source(source, str(p))
    except ParseError:
        return None


def snippet_for(parsed: ParsedFile, line_start: int, line_end: int, context: int = 0) -> str:
    """Belirtilen satır aralığını (1-indexed, inclusive) +/- context satır olarak döndür."""
    if not parsed.lines:
        return ""
    lo = max(1, line_start - context)
    hi = min(len(parsed.lines), line_end + context)
    return "\n".join(parsed.lines[lo - 1 : hi])
