"""Shallow git clone of a public GitHub repo, with size limit and error mapping.

CLI:
    python -m analysis.repo_cloner <url>           # backend/ içinden
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from git import GitCommandError, Repo

from analysis.file_walker import count_all_source_files

logger = logging.getLogger(__name__)


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


class RepoEmptyError(RepoCloneError):
    """Klon başarılı görünse de analiz edilebilir kaynak dosya yok."""


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
    source_file_count: int = 0


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


_GITHUB_HTTPS = re.compile(
    r"^https?://github\.com/[\w.\-]+/[\w.\-]+(?:\.git)?/?$",
    re.IGNORECASE,
)


def _max_size_mb() -> int:
    return int(os.getenv("MAX_REPO_SIZE_MB", "100"))


def _tmp_dir() -> Path:
    """Klon dizini — asla backend kaynak ağacının içinde olmamalı.

    Uvicorn ``--reload`` backend/ altındaki değişiklikleri izler; klon buraya
    yazılırsa job store sıfırlanır ve SSE 404 verir.
    """
    backend_dir = Path(__file__).resolve().parent.parent
    system_base = Path(tempfile.gettempdir()) / "kodhekim"

    raw = os.getenv("TMP_DIR", "").strip()
    if raw:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (system_base / Path(raw).name).resolve()
        else:
            path = path.resolve()
        # backend/ altına düşen yolları sistem temp'e yönlendir
        try:
            path.relative_to(backend_dir)
            logger.warning(
                "TMP_DIR backend içinde (%s) — uvicorn reload riski; %s kullanılıyor",
                path,
                system_base,
            )
            path = system_base.resolve()
        except ValueError:
            pass
    else:
        path = system_base.resolve()

    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_repo_url(url: str) -> str:
    """GitHub URL'sini GitPython'ın kabul edeceği forma getir.

    - Sonundaki `/` temizlenir
    - `/tree/branch` veya `/blob/...` kırpılır (kullanıcı tarayıcı linki yapıştırsa)
    - `https://github.com/user/repo` → `.git` eklenir (zorunlu değil ama uyumluluk)
    """
    if not isinstance(url, str) or not url.strip():
        raise InvalidRepoUrlError("URL boş olamaz.")

    u = url.strip()
    if u.endswith("/"):
        u = u.rstrip("/")

    # git@github.com:owner/repo(.git)?
    if u.startswith("git@"):
        if "github.com" not in u.lower():
            raise InvalidRepoUrlError("Şu an yalnızca GitHub repo'ları destekleniyor.")
        if not u.endswith(".git"):
            u = f"{u}.git"
        return u

    if not (u.startswith("https://") or u.startswith("http://")):
        raise InvalidRepoUrlError(
            "Yalnızca https://, http:// veya git@ ile başlayan URL'ler kabul edilir."
        )

    lowered = u.lower()
    if "github.com" not in lowered:
        raise InvalidRepoUrlError(
            "Şu an yalnızca GitHub repo'ları destekleniyor (github.com içermeli)."
        )

    for marker in ("/tree/", "/blob/"):
        if marker in u:
            u = u.split(marker, 1)[0].rstrip("/")

    if u.startswith("https://github.com") or u.startswith("http://github.com"):
        if not u.endswith(".git"):
            u = f"{u}.git"

    return u


def _dir_size_mb(path: Path) -> float:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total / (1024 * 1024)


def _validate_url(url: str) -> str:
    """Normalize edilmiş URL döndür (geriye uyumluluk)."""
    return normalize_repo_url(url)


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
    ):
        return RepoPrivateError(
            "Repo private görünüyor. KodHekim yalnızca public repo'ları analiz eder."
        )
    return RepoCloneError(f"Clone başarısız: {msg.strip()[:300]}")


def _count_source_files(repo_path: Path) -> int:
    return count_all_source_files(repo_path)


def _verify_clone_complete(target: Path) -> None:
    """Klon dizininin gerçekten dolu olduğunu doğrula."""
    if not target.is_dir():
        raise RepoCloneError("Clone hedefi bir dizin değil.")
    if not any(target.iterdir()):
        raise RepoCloneError("Clone dizini boş — klonlama tamamlanmamış olabilir.")
    git_dir = target / ".git"
    if not git_dir.exists():
        raise RepoCloneError(
            "Clone dizininde .git yok — klonlama eksik veya bozuk olabilir."
        )


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

    Klonlama tamamlanmadan ve en az bir kaynak dosya doğrulanmadan dönmez.
    """
    normalized = _validate_url(url)

    job_id = job_id or uuid.uuid4().hex[:12]
    base = (tmp_dir if tmp_dir is not None else _tmp_dir()).resolve()
    base.mkdir(parents=True, exist_ok=True)
    target = (base / job_id).resolve()

    if target.exists():
        shutil.rmtree(target, ignore_errors=True)

    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    logger.info("Cloning %s -> %s", normalized, target)
    try:
        repo = Repo.clone_from(
            normalized,
            str(target),
            depth=1,
            single_branch=True,
            env=env,
        )
    except GitCommandError as e:
        shutil.rmtree(target, ignore_errors=True)
        raise _map_git_error(e) from e

    try:
        _verify_clone_complete(target)
    except RepoCloneError:
        shutil.rmtree(target, ignore_errors=True)
        raise

    size_mb = _dir_size_mb(target)
    cap = max_size_mb if max_size_mb is not None else _max_size_mb()
    if size_mb > cap:
        shutil.rmtree(target, ignore_errors=True)
        raise RepoTooLargeError(
            f"Repo boyutu {size_mb:.1f} MB; sınır {cap} MB. Daha küçük bir repo dene."
        )

    source_count = _count_source_files(target)
    if source_count == 0:
        shutil.rmtree(target, ignore_errors=True)
        raise RepoEmptyError(
            "Repo klonlandı ancak .py / .js / .ts / .jsx / .tsx kaynak dosyası bulunamadı. "
            "URL'nin repo köküne işaret ettiğinden emin ol."
        )

    try:
        commit_sha = repo.head.commit.hexsha[:7]
    except Exception:
        commit_sha = "unknown"

    logger.info(
        "Clone OK: %s files, %.1f MB, commit %s",
        source_count,
        size_mb,
        commit_sha,
    )

    return CloneResult(
        repo_path=target,
        repo_url=normalized,
        size_mb=round(size_mb, 2),
        commit_sha=commit_sha,
        job_id=job_id,
        source_file_count=source_count,
    )


def cleanup(path: Path) -> None:
    """Clone edilmiş repo'yu temizle (Windows'ta read-only handler dahil)."""
    if not Path(path).exists():
        return

    def _on_rm_error(func, p, exc_info):  # type: ignore[no-untyped-def]
        try:
            os.chmod(p, 0o700)
            func(p)
        except Exception:
            pass

    shutil.rmtree(path, onerror=_on_rm_error)


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

    print("[OK] Clone başarılı")
    print(f"  Yol     : {result.repo_path}")
    print(f"  Boyut   : {result.size_mb} MB")
    print(f"  Dosya   : {result.source_file_count} kaynak dosyası")
    print(f"  Commit  : {result.commit_sha}")
    print(f"  Job ID  : {result.job_id}")

    if not args.keep:
        cleanup(result.repo_path)
        print("  (Temizlendi)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
