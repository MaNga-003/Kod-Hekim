"""GET /api/report/:job_id — final raporu döndür."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.orchestrator import state_to_json
from analysis.mode_comparison import compute_actual_metrics, estimate_modes
from analysis.simulation import score_delta, simulate_post_fix_score, to_payload
from api.store import get_job


router = APIRouter(prefix="/api", tags=["report"])


class SimulateRequest(BaseModel):
    accepted_fix_ids: list[str]


@router.get("/report/{job_id}")
async def report(job_id: str) -> dict:
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"job bulunamadı: {job_id}")

    if record.status == "error":
        # error_code → HTTP status mapping (developer.md §6 + §15 risk tablosu)
        ERROR_STATUS_MAP = {
            "invalid_url": 400,
            "not_found": 404,
            "private": 403,
            "too_large": 413,  # Payload Too Large
            "internal": 500,
        }
        status = ERROR_STATUS_MAP.get(record.error_code or "", 500)
        raise HTTPException(
            status_code=status,
            detail={
                "code": record.error_code or "internal",
                "message": record.error or "bilinmeyen hata",
                "job_id": job_id,
            },
        )

    if record.status != "done" or record.state is None:
        # 202 ile pending durumunu bildir; client polling yapabilir
        raise HTTPException(
            status_code=202,
            detail={"status": record.status, "job_id": job_id},
        )

    return state_to_json(record.state)


@router.post("/report/{job_id}/simulate")
async def simulate(job_id: str, req: SimulateRequest) -> dict:
    """Kabul edilen fix'ler uygulansa sağlık skoru ne olur?

    developer.md §16.1 — Önce/Sonra simülasyonu.
    """
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"job bulunamadı: {job_id}")
    if record.status != "done" or record.state is None or record.state["report"] is None:
        raise HTTPException(
            status_code=409,
            detail={"status": record.status, "message": "rapor henüz hazır değil"},
        )

    issues = record.state["issues"]
    current = record.state["report"].health
    simulated = simulate_post_fix_score(issues, set(req.accepted_fix_ids))
    delta = score_delta(current, simulated)
    return to_payload(current, simulated, delta)


@router.get("/report/{job_id}/mode-comparison")
async def mode_comparison(job_id: str) -> dict:
    """3 mod için tahmini metrikler (developer.md §16.3)."""
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"job bulunamadı: {job_id}")
    if record.status != "done" or record.state is None:
        raise HTTPException(
            status_code=409,
            detail={"status": record.status, "message": "rapor henüz hazır değil"},
        )

    state = record.state
    actual = compute_actual_metrics(state["events"])
    # Dosya sayısı tahmini — issue'lardan tekil file count, daha iyi proxy yok
    file_count = len({i.file for i in state["issues"]}) or 1

    metrics = estimate_modes(
        file_count=file_count,
        actual_mode=state["mode"],
        actual_seconds=actual["seconds"],
        actual_tokens=actual["tokens"],
        actual_issues=actual["issues"],
    )
    return {
        "actual_mode": state["mode"],
        "file_count": file_count,
        "modes": [m.to_dict() for m in metrics],
    }


@router.get("/jobs/{job_id}/status")
async def job_status(job_id: str) -> dict:
    """Lightweight durum sorgusu (rapor beklemeden)."""
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"job bulunamadı: {job_id}")
    return {
        "job_id": record.job_id,
        "status": record.status,
        "mode": record.mode,
        "provider": record.provider,
        "error_code": record.error_code,
        "error": record.error,
    }
