"""In-memory job store + arka plan pipeline runner."""

from __future__ import annotations

import asyncio
import logging
import os
import queue as _q
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, Optional

from agents.orchestrator import AnalysisState, Event, Mode, run_pipeline
from analysis.repo_cloner import (
    CloneResult,
    InvalidRepoUrlError,
    RepoCloneError,
    RepoEmptyError,
    RepoNotFoundError,
    RepoPrivateError,
    RepoTooLargeError,
    cleanup,
    clone_repo,
    normalize_repo_url,
)

logger = logging.getLogger(__name__)


JobStatus = Literal["queued", "cloning", "running", "done", "error"]


@dataclass
class JobRecord:
    job_id: str
    repo_url: str
    mode: Mode
    provider: str
    status: JobStatus = "queued"
    error: Optional[str] = None
    error_code: Optional[str] = None
    state: Optional[AnalysisState] = None
    queue: "_q.Queue[Optional[Event]]" = field(default_factory=_q.Queue)
    clone_path: Optional[Path] = None


JOB_STORE: dict[str, JobRecord] = {}
_STORE_LOCK = threading.Lock()


def get_job(job_id: str) -> Optional[JobRecord]:
    with _STORE_LOCK:
        return JOB_STORE.get(job_id)


def _put(job_id: str, record: JobRecord) -> None:
    with _STORE_LOCK:
        JOB_STORE[job_id] = record


def start_job_with_clone(
    *,
    clone: CloneResult,
    repo_url: str,
    mode: Mode,
    provider_name: str,
    model_overrides: Optional[dict[str, str]] = None,
) -> JobRecord:
    """Önceden tamamlanmış klon ile pipeline başlat (analyze.py kullanır)."""
    record = JobRecord(
        job_id=clone.job_id,
        repo_url=repo_url,
        mode=mode,
        provider=provider_name,
        status="running",
        clone_path=clone.repo_path.resolve(),
    )
    _put(clone.job_id, record)

    def _push(ev: Optional[Event]) -> None:
        try:
            record.queue.put(ev)
        except Exception:
            pass

    _push(Event(
        type="clone_done",
        data={
            "size_mb": clone.size_mb,
            "commit_sha": clone.commit_sha,
            "source_files": clone.source_file_count,
            "repo_path": str(clone.repo_path),
        },
    ))

    _maybe_warn_file_cap(clone.repo_path, _push)
    _start_pipeline_thread(record, clone.repo_path, mode, provider_name, model_overrides, _push)
    return record


def start_job(
    *,
    repo_url: str,
    mode: Mode,
    provider_name: str,
    model_overrides: Optional[dict[str, str]] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> JobRecord:
    """Geriye uyumluluk: klon + pipeline tek thread'de (testler)."""
    del loop
    job_id = uuid.uuid4().hex[:12]
    record = JobRecord(
        job_id=job_id,
        repo_url=repo_url,
        mode=mode,
        provider=provider_name,
    )
    _put(job_id, record)

    def _push(ev: Optional[Event]) -> None:
        try:
            record.queue.put(ev)
        except Exception:
            pass

    def _worker() -> None:
        try:
            normalized_url = normalize_repo_url(repo_url)
            record.status = "cloning"
            _push(Event(type="clone_started", data={"repo_url": normalized_url}))
            try:
                clone = clone_repo(normalized_url, job_id=job_id)
            except InvalidRepoUrlError as e:
                _fail(record, "invalid_url", str(e), _push)
                return
            except RepoNotFoundError as e:
                _fail(record, "not_found", str(e), _push)
                return
            except RepoPrivateError as e:
                _fail(record, "private", str(e), _push)
                return
            except RepoTooLargeError as e:
                _fail(record, "too_large", str(e), _push)
                return
            except RepoEmptyError as e:
                _fail(record, "empty_repo", str(e), _push)
                return
            except RepoCloneError as e:
                _fail(record, "internal", str(e), _push)
                return

            record.clone_path = clone.repo_path.resolve()
            record.status = "running"
            _push(Event(
                type="clone_done",
                data={
                    "size_mb": clone.size_mb,
                    "commit_sha": clone.commit_sha,
                    "source_files": clone.source_file_count,
                    "repo_path": str(clone.repo_path),
                },
            ))
            _maybe_warn_file_cap(clone.repo_path, _push)
            _run_pipeline(record, clone.repo_path, mode, provider_name, model_overrides, _push)
        finally:
            _push(None)

    threading.Thread(target=_worker, name=f"job-{job_id}", daemon=True).start()
    return record


def _maybe_warn_file_cap(repo_path: Path, push: Callable[[Event], None]) -> None:
    try:
        from analysis.file_walker import count_all_source_files

        max_files = int(os.getenv("MAX_FILES_TO_SCAN", "200"))
        total = count_all_source_files(repo_path)
        if total > max_files:
            push(Event(
                type="agent_progress",
                data={
                    "agent": "profiler",
                    "message": (
                        f"⚠ Repo {total} kaynak dosyası içeriyor; "
                        f"MAX_FILES_TO_SCAN={max_files} uygulanır "
                        "(src/app/lib öncelikli, dil dengeli)."
                    ),
                },
            ))
    except Exception:
        pass


def _start_pipeline_thread(
    record: JobRecord,
    repo_path: Path,
    mode: Mode,
    provider_name: str,
    model_overrides: Optional[dict[str, str]],
    push: Callable[[Optional[Event]], None],
) -> None:
    def _worker() -> None:
        try:
            _run_pipeline(record, repo_path, mode, provider_name, model_overrides, push)
        finally:
            push(None)

    threading.Thread(target=_worker, name=f"job-{record.job_id}", daemon=True).start()


def _run_pipeline(
    record: JobRecord,
    repo_path: Path,
    mode: Mode,
    provider_name: str,
    model_overrides: Optional[dict[str, str]],
    push: Callable[[Event], None],
) -> None:
    record.status = "running"
    try:
        state = run_pipeline(
            repo_path=repo_path,
            mode=mode,
            provider_name=provider_name,
            model_overrides=model_overrides,
            job_id=record.job_id,
            event_sink=push,
        )
        record.state = state
        record.status = "done"
    except Exception as e:
        logger.exception("pipeline crashed: %s", e)
        _fail(record, "internal", f"pipeline hatası: {e}", push)
        return

    try:
        if record.clone_path is not None:
            cleanup(record.clone_path)
    except Exception:
        logger.warning("cleanup failed for %s", record.clone_path)


def _fail(
    record: JobRecord,
    code: str,
    message: str,
    push: Callable[[Optional[Event]], None],
) -> None:
    record.status = "error"
    record.error = message
    record.error_code = code
    push(Event(type="error", data={"code": code, "message": message}))


def _reset_store() -> None:
    with _STORE_LOCK:
        JOB_STORE.clear()
