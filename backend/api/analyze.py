"""POST /api/analyze — yeni analiz başlat."""

from __future__ import annotations

import asyncio
import os
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.orchestrator import Mode
from analysis.repo_cloner import (
    InvalidRepoUrlError,
    RepoCloneError,
    RepoEmptyError,
    RepoNotFoundError,
    RepoPrivateError,
    RepoTooLargeError,
    clone_repo,
    normalize_repo_url,
)
from api.store import start_job_with_clone


router = APIRouter(prefix="/api", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    repo_url: str = Field(..., description="Public GitHub repo URL'si")
    mode: Mode = "hybrid"
    provider: Literal["cerebras", "gemini"] = "cerebras"
    model_overrides: Optional[dict[str, str]] = None


class AnalyzeResponse(BaseModel):
    job_id: str
    status: str = "queued"
    source_files: Optional[int] = None


@router.post("/analyze", response_model=AnalyzeResponse, status_code=202)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """Yeni bir analiz job'ı kuyrukla.

    Klonlama bu istek içinde tamamlanır; başarısız klon HTTP hata döner.
    Pipeline arka planda çalışır — SSE: `GET /api/analyze/{job_id}/stream`.
    """
    if not req.repo_url.strip():
        raise HTTPException(status_code=400, detail="repo_url boş olamaz")

    if req.mode != "static" and req.provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(
            status_code=400,
            detail="GEMINI_API_KEY ayarlanmamış. .env dosyasına anahtarı ekleyin veya Statik mod kullanın.",
        )
    if req.mode != "static" and req.provider == "cerebras" and not os.getenv("CEREBRAS_API_KEY"):
        raise HTTPException(
            status_code=400,
            detail="CEREBRAS_API_KEY ayarlanmamış. .env dosyasına anahtarı ekleyin veya Statik mod kullanın.",
        )

    try:
        normalized = normalize_repo_url(req.repo_url.strip())
    except InvalidRepoUrlError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Klonlama bitmeden pipeline'a geçilmez — blocking thread pool
    try:
        clone = await asyncio.to_thread(clone_repo, normalized)
    except InvalidRepoUrlError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RepoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RepoPrivateError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except RepoTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    except RepoEmptyError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RepoCloneError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    record = start_job_with_clone(
        clone=clone,
        repo_url=normalized,
        mode=req.mode,
        provider_name=req.provider,
        model_overrides=req.model_overrides,
    )
    return AnalyzeResponse(
        job_id=record.job_id,
        status=record.status,
        source_files=clone.source_file_count,
    )
