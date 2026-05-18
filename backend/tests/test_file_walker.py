"""file_walker.py birim testleri — saf offline, tmp_path fixture'ları."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.file_walker import (
    EXCLUDED_DIR_NAMES,
    LANGUAGE_EXTENSIONS,
    detect_languages,
    walk_files,
)


# ---------------------------------------------------------------------------
# Yardımcı: tmp_path içine sahte repo yapısı kur
# ---------------------------------------------------------------------------


def _make_file(root: Path, rel: str, content: str = "x = 1\n") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Tipik bir Python projesi yapısı + dışlanması gereken klasörler."""
    _make_file(tmp_path, "app/main.py", "print('hello')\n")
    _make_file(tmp_path, "app/utils/helpers.py", "def foo(): pass\n")
    _make_file(tmp_path, "tests/test_main.py", "def test_x(): assert True\n")
    _make_file(tmp_path, "README.md", "readme")
    _make_file(tmp_path, "package.json", "{}")
    # dışlanması gereken
    _make_file(tmp_path, "node_modules/foo/index.js", "x")
    _make_file(tmp_path, ".git/HEAD", "ref")
    _make_file(tmp_path, "__pycache__/x.cpython-311.pyc", "binary")
    _make_file(tmp_path, ".venv/lib/site-packages/foo/__init__.py", "x")
    return tmp_path


# ---------------------------------------------------------------------------
# Testler
# ---------------------------------------------------------------------------


def test_walk_files_finds_only_python(fake_repo: Path) -> None:
    results = walk_files(fake_repo)
    rels = sorted(r.rel_path for r in results)
    assert rels == ["app/main.py", "app/utils/helpers.py", "tests/test_main.py"]
    assert all(r.language == "python" for r in results)


def test_walk_files_excludes_known_dirs(fake_repo: Path) -> None:
    results = walk_files(fake_repo)
    for r in results:
        for excluded in EXCLUDED_DIR_NAMES:
            assert excluded not in r.rel_path.split("/"), (
                f"Excluded dir '{excluded}' '{r.rel_path}' içinde göründü"
            )


def test_walk_files_excludes_dotdirs(tmp_path: Path) -> None:
    _make_file(tmp_path, ".hidden/secret.py", "x")
    _make_file(tmp_path, "ok.py", "x")
    results = walk_files(tmp_path)
    assert [r.rel_path for r in results] == ["ok.py"]


def test_walk_files_sorts_by_size_desc(tmp_path: Path) -> None:
    _make_file(tmp_path, "small.py", "x\n")  # 2 byte
    _make_file(tmp_path, "big.py", "x" * 5000)  # 5000 byte
    _make_file(tmp_path, "medium.py", "x" * 500)  # 500 byte
    results = walk_files(tmp_path)
    assert [r.rel_path for r in results] == ["big.py", "medium.py", "small.py"]


def test_walk_files_respects_max(tmp_path: Path) -> None:
    for i in range(10):
        _make_file(tmp_path, f"f{i}.py", "x" * (i + 1))
    results = walk_files(tmp_path, max_files=3)
    assert len(results) == 3
    # En büyükler (i=9,8,7) tutulmalı
    assert {r.rel_path for r in results} == {"f9.py", "f8.py", "f7.py"}


def test_walk_files_rejects_nonexistent_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        walk_files(tmp_path / "yok")


def test_detect_languages_finds_python(fake_repo: Path) -> None:
    langs = detect_languages(fake_repo)
    assert "python" in langs


def test_detect_languages_empty_repo(tmp_path: Path) -> None:
    assert detect_languages(tmp_path) == []


def test_language_extensions_registry_has_python() -> None:
    assert ".py" in LANGUAGE_EXTENSIONS["python"]
