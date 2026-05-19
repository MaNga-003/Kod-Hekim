"""Çoklu dil (Python + JS + TS) statik tarama testleri."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.file_walker import walk_files
from analysis.languages import resolve_languages
from analysis.scan import scan_repo


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_walk_includes_js_when_present() -> None:
    repo = FIXTURES / "javascript_express_bad"
    files = walk_files(repo, languages=["javascript"])
    rels = {f.rel_path for f in files}
    assert "server.js" in rels
    assert all(f.language == "javascript" for f in files)


def test_scan_js_fixture_finds_issues() -> None:
    repo = FIXTURES / "javascript_express_bad"
    report = scan_repo(repo, languages=["javascript"])
    assert report.files_scanned >= 1
    codes = {i.code for i in report.issues}
    assert "MISSING_TIMEOUT" in codes or "UNBOUNDED_CACHE" in codes


def test_tree_sitter_parses_all_three_languages() -> None:
    from analysis.ast_parser import validate_multilang_parser

    checks = validate_multilang_parser()
    assert checks["python"] is True
    assert checks["javascript"] is True, "JS Tree-sitter parse başarısız — sürüm uyumsuzluğu?"
    assert checks["typescript"] is True, "TS Tree-sitter parse başarısız — sürüm uyumsuzluğu?"


def test_resolve_languages_always_includes_all_three(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    langs = resolve_languages(tmp_path)
    assert langs == ["python", "javascript", "typescript"]
