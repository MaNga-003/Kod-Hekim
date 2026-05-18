"""Shallow git clone of a public GitHub repo, with size limit and error mapping.

CLI:
    python -m analysis.repo_cloner <url>           # backend/ içinden
"""

from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from git import GitCommandError, Repo


# ---------------------------------------------------------------------------
# Hatalar
# ---------------------------------------------------------------------------


class RepoCloneError(Exception):
    """Base hata."""


class RepoNotFoundError(RepoCloneError):
    """404 / repo bulunamadı."""


class RepoPrivateError(RepoCloneError):
    """Auth gerektiren / private repo."""


class RepoTooLargeError(RepoCloneError):
    """Clone sonrası boyut MAX_REPO_SIZE_MB'yi aştı."""


class InvalidRepoUrlError(RepoCloneError):
    """URL biçimi geçersiz."""


# ---------------------------------------------------------------------------
# Sonuç tipi
# ---------------------------------------------------------------------------


@dataclass
class CloneResult:
    repo_path: Path
    repo_url: str
    size_mb: float
    commit_sha: str
    job_id: str


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


def _max_size_mb() -> int:
    return int(os.getenv("MAX_REPO_SIZE_MB", "100"))


def _tmp_dir() -> Path:
    return Path(os.getenv("TMP_DIR", "./tmp/kodhekim"))


def _dir_size_mb(path: Path) -> float:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total / (1024 * 1024)


def _validate_url(url: str) -> None:
    if not isinstance(url, str) or not url.strip():
        raise InvalidRepoUrlError("URL boş olamaz.")
    u = url.strip()
    if not (u.startswith("https://") or u.startswith("http://") or u.startswith("git@")):
        raise InvalidRepoUrlError(
            "Yalnızca https://, http:// veya git@ ile başlayan URL'ler kabul edilir."
        )
    # MVP: yalnızca GitHub kabul ediyoruz; doc finans/güvenlik tonuna sadık kalmak için.
    lowered = u.lower()
    if "github.com" not in lowered:
        raise InvalidRepoUrlError(
            "Şu an yalnızca GitHub repo'ları destekleniyor (github.com içermeli)."
        )


def _map_git_error(exc: GitCommandError) -> RepoCloneError:
    msg = (exc.stderr or "") + (exc.stdout or "") + str(exc)
    low = msg.lower()
    if "not found" in low or "could not find" in low or "404" in low:
        return RepoNotFoundError("Repo bulunamadı (404). URL'yi kontrol et.")
    if (
        "authentication" in low
        or "could not read username" in low
        or "permission denied" in low
        or "terminal prompts disabled" in low
        or "fatal: repository" in low
        and "not found" in low
    ):
        return RepoPrivateError(
            "Repo private görünüyor. KodHekim yalnızca public repo'ları analiz eder."
        )
    return RepoCloneError(f"Clone başarısız: {msg.strip()[:300]}")


# ---------------------------------------------------------------------------
# Ana API
# ---------------------------------------------------------------------------


def clone_repo(
    url: str,
    job_id: Optional[str] = None,
    *,
    max_size_mb: Optional[int] = None,
    tmp_dir: Optional[Path] = None,
) -> CloneResult:
    """Public GitHub repo'sunu shallow (depth=1) klonla.

    Args:
        url: Repo URL'si. HTTPS önerilir.
        job_id: İstenirse dış kaynak; verilmezse UUID üretilir.
        max_size_mb: Override; verilmezse env'den `MAX_REPO_SIZE_MB`.
        tmp_dir: Override; verilmezse env'den `TMP_DIR`.

    Raises:
        InvalidRepoUrlError, RepoNotFoundError, RepoPrivateError,
        RepoTooLargeError, RepoCloneError
    """
    _validate_url(url)

    job_id = job_id or uuid.uuid4().hex[:12]
    base = tmp_dir if tmp_dir is not None else _tmp_dir()
    target = base / job_id
    target.mkdir(parents=True, exist_ok=True)

    # `GIT_TERMINAL_PROMPT=0` — private repo'da kullanıcı adı/şifre sormaması için.
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    try:
        repo = Repo.clone_from(
            url,
            target,
            depth=1,
            single_branch=True,
            env=env,
        )
    except GitCommandError as e:
        shutil.rmtree(target, ignore_errors=True)
        raise _map_git_error(e) from e

    size_mb = _dir_size_mb(target)
    cap = max_size_mb if max_size_mb is not None else _max_size_mb()
    if size_mb > cap:
        shutil.rmtree(target, ignore_errors=True)
        raise RepoTooLargeError(
            f"Repo boyutu {size_mb:.1f} MB; sınır {cap} MB. Daha küçük bir repo dene."
        )

    try:
        commit_sha = repo.head.commit.hexsha[:7]
    except Exception:
        commit_sha = "unknown"

    return CloneResult(
        repo_path=target,
        repo_url=url,
        size_mb=round(size_mb, 2),
        commit_sha=commit_sha,
        job_id=job_id,
    )


def cleanup(path: Path) -> None:
    """Clone edilmiş repo'yu temizle (Windows'ta read-only handler dahil)."""
    if not Path(path).exists():
        return

    def _on_rm_error(func, p, exc_info):  # type: ignore[no-untyped-def]
        # .git altındaki bazı dosyalar Windows'ta read-only — chmod sonrası yeniden dene.
        try:
            os.chmod(p, 0o700)
            func(p)
        except Exception:
            pass

    shutil.rmtree(path, onerror=_on_rm_error)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="analysis.repo_cloner")
    parser.add_argument("url", help="GitHub repo URL'si (public)")
    parser.add_argument("--keep", action="store_true", help="Clone sonrası dizini silme")
    args = parser.parse_args()

    try:
        result = clone_repo(args.url)
    except RepoCloneError as e:
        print(f"[HATA] {type(e).__name__}: {e}")
        return 1

    print(f"[OK] Clone başarılı")
    print(f"  Yol     : {result.repo_path}")
    print(f"  Boyut   : {result.size_mb} MB")
    print(f"  Commit  : {result.commit_sha}")
    print(f"  Job ID  : {result.job_id}")

    if not args.keep:
        cleanup(result.repo_path)
        print(f"  (Temizlendi)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
