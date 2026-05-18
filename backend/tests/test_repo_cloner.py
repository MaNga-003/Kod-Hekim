"""repo_cloner.py birim testleri.

Ağa giden testler (`@pytest.mark.network`) varsayılan olarak çalışır — küçük public
repo'yu klonlar. Çevrimdışıysan: `pytest -m 'not network'`.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from git import GitCommandError

from analysis.repo_cloner import (
    CloneResult,
    InvalidRepoUrlError,
    RepoCloneError,
    RepoNotFoundError,
    RepoPrivateError,
    RepoTooLargeError,
    _map_git_error,
    cleanup,
    clone_repo,
)


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "   ",
        "not-a-url",
        "ftp://github.com/foo/bar.git",
        "https://gitlab.com/foo/bar.git",  # MVP: yalnız GitHub
    ],
)
def test_clone_rejects_invalid_urls(bad_url: str) -> None:
    with pytest.raises(InvalidRepoUrlError):
        clone_repo(bad_url)


# ---------------------------------------------------------------------------
# Hata eşleme
# ---------------------------------------------------------------------------


def _gce(stderr: str) -> GitCommandError:
    e = GitCommandError(["git", "clone"], 128)
    e.stderr = stderr
    e.stdout = ""
    return e


def test_map_404_to_not_found() -> None:
    e = _gce("remote: Repository not found.\nfatal: repository ... not found")
    assert isinstance(_map_git_error(e), RepoNotFoundError)


def test_map_auth_to_private() -> None:
    e = _gce("fatal: Authentication failed for 'https://github.com/...'")
    assert isinstance(_map_git_error(e), RepoPrivateError)


def test_map_other_to_generic() -> None:
    e = _gce("fatal: unable to access 'https://...': Could not resolve host")
    mapped = _map_git_error(e)
    assert isinstance(mapped, RepoCloneError)
    # Spesifik alt sınıf olmamalı
    assert not isinstance(mapped, (RepoNotFoundError, RepoPrivateError, RepoTooLargeError))


# ---------------------------------------------------------------------------
# Boyut sınırı (mocked clone)
# ---------------------------------------------------------------------------


def test_clone_raises_when_size_exceeds_limit(tmp_path: Path) -> None:
    """Repo.clone_from'u mockla, sonra büyük bir dosya yarat → TooLarge fırlatmalı."""

    fake_repo_path: Path = tmp_path / "fake"

    def fake_clone(url, target, **kwargs):  # type: ignore[no-untyped-def]
        Path(target).mkdir(parents=True, exist_ok=True)
        big = Path(target) / "big.bin"
        big.write_bytes(b"x" * (2 * 1024 * 1024))  # 2 MB

        class _FakeRepo:
            class head:
                class commit:
                    hexsha = "abc1234deadbeef"

        return _FakeRepo()

    with patch("analysis.repo_cloner.Repo.clone_from", side_effect=fake_clone):
        with pytest.raises(RepoTooLargeError):
            clone_repo(
                "https://github.com/example/repo",
                tmp_dir=tmp_path,
                max_size_mb=1,
            )

    # Hata sonrası dizin silinmiş olmalı
    job_dirs = list(tmp_path.iterdir())
    assert job_dirs == [], f"Beklenen: temizlenmiş, bulunan: {job_dirs}"


def test_clone_success_returns_result(tmp_path: Path) -> None:
    def fake_clone(url, target, **kwargs):  # type: ignore[no-untyped-def]
        Path(target).mkdir(parents=True, exist_ok=True)
        (Path(target) / "main.py").write_text("print('ok')\n")

        class _FakeRepo:
            class head:
                class commit:
                    hexsha = "1234567abcdef"

        return _FakeRepo()

    with patch("analysis.repo_cloner.Repo.clone_from", side_effect=fake_clone):
        result = clone_repo(
            "https://github.com/example/repo",
            tmp_dir=tmp_path,
            max_size_mb=100,
        )

    assert isinstance(result, CloneResult)
    assert result.repo_path.exists()
    assert result.commit_sha == "1234567"
    assert result.size_mb >= 0
    assert result.job_id


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def test_cleanup_removes_directory(tmp_path: Path) -> None:
    d = tmp_path / "to-remove"
    d.mkdir()
    (d / "file.txt").write_text("x")
    cleanup(d)
    assert not d.exists()


def test_cleanup_silent_on_missing(tmp_path: Path) -> None:
    cleanup(tmp_path / "yok")  # raise etmemeli


# ---------------------------------------------------------------------------
# Gerçek ağ testi (opt-in) — küçük public repo
# ---------------------------------------------------------------------------


@pytest.mark.network
def test_real_clone_octocat(tmp_path: Path) -> None:
    """Klasik küçücük public repo: github.com/octocat/Hello-World (<1 KB)."""
    result = clone_repo(
        "https://github.com/octocat/Hello-World",
        tmp_dir=tmp_path,
    )
    try:
        assert result.repo_path.exists()
        assert result.commit_sha != "unknown"
        assert result.size_mb < 5
    finally:
        cleanup(result.repo_path)
