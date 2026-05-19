"""GET /api/analyze/:job_id/stream — Server-Sent Events ile canlı log."""

from __future__ import annotations

import asyncio
import json
import os
import queue as _q
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from api.store import get_job


router = APIRouter(prefix="/api", tags=["stream"])


def _heartbeat_sec() -> int:
    try:
        return max(1, int(os.getenv("SSE_HEARTBEAT_SEC", "15")))
    except ValueError:
        return 15


@router.get("/analyze/{job_id}/stream")
async def stream(job_id: str, request: Request) -> EventSourceResponse:
    """Job'ın event akışını SSE olarak yayar.

    Event şeması (developer.md §6.2):
        {"event": "issue_found", "data": {...}, "timestamp": "..."}

    Akış `all_done` event'iyle veya client disconnect ile kapanır.
    Heartbeat: `SSE_HEARTBEAT_SEC` saniyede bir keepalive frame.
    """
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"job bulunamadı: {job_id}")

    heartbeat = _heartbeat_sec()

    loop = asyncio.get_running_loop()

    async def _get_with_heartbeat():
        """Sync queue.get() → run_in_executor; timeout ile heartbeat."""
        try:
            return await loop.run_in_executor(
                None, lambda: record.queue.get(timeout=heartbeat)
            )
        except _q.Empty:
            return "__HEARTBEAT__"

    async def event_gen() -> AsyncIterator[dict]:
        while True:
            if await request.is_disconnected():
                return
            ev = await _get_with_heartbeat()

            if ev == "__HEARTBEAT__":
                yield {"event": "heartbeat", "data": "{}"}
                continue

            if ev is None:
                # Sentinel — pipeline bitti
                return

            yield {
                "event": ev.type,
                "data": json.dumps(
                    {"data": ev.data, "timestamp": ev.timestamp},
                    ensure_ascii=False,
                ),
            }

    return EventSourceResponse(event_gen())
