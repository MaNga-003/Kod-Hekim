"""Faz L — FastAPI endpoint testleri.

Strateji:
- Pipeline thread'inde gerçek `clone_repo` ve `run_pipeline` çağrılır.
- Network'e çıkmamak için `clone_repo` patch'lenir — lokal fixture'a yönlenir.
- LLM çağrısı yapan modlar test'lerden uzak tutulur; sadece `static` modu kapsanır.

Kapsam:
- `POST /api/analyze` → 202 + job_id
- `GET /api/jobs/:id/status` → polling
- `GET /api/report/:id` → tamamlanınca rapor JSON
- `GET /api/analyze/:id/stream` → SSE event akışı, `all_done` sonrası kapanma
- `GET /api/models` → sağlayıcı + model listesi
- 404, validation, hatalı URL
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient

import api.store as store_mod
from analysis.repo_cloner import CloneResult, RepoNotFoundError
from main import app


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "bad_code_examples"


@pytest.fixture(autouse=True)
def _reset_store():
    store_mod._reset_store()
    yield
    store_mod._reset_store()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def patched_clone(monkeypatch) -> None:
    """`clone_repo` → fixture'a yönlendir (ağa çıkma)."""

    def fake_clone(url: str, job_id: Optional[str] = None, **_) -> CloneResult:
        if "bad-url" in url or url == "invalid":
            raise RepoNotFoundError("404 (fake)")
        return CloneResult(
            repo_path=FIXTURE,
            repo_url=url,
            size_mb=0.5,
            commit_sha="fakehash",
            job_id=job_id or "test",
            source_file_count=1,
        )

    monkeypatch.setattr("api.analyze.clone_repo", fake_clone)
    monkeypatch.setattr("api.store.clone_repo", fake_clone)
    # cleanup() fixture klasörünü silmesin
    monkeypatch.setattr("api.store.cleanup", lambda p: None)


def _wait_until_done(client: TestClient, job_id: str, timeout: float = 15.0) -> dict:
    """Polling: status `done` ya da `error` olana kadar."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = client.get(f"/api/jobs/{job_id}/status")
        if r.status_code == 200 and r.json()["status"] in {"done", "error"}:
            return r.json()
        time.sleep(0.1)
    raise TimeoutError(f"job {job_id} {timeout}s içinde bitmedi")


# ---------------------------------------------------------------------------
# Sağlık + models
# ---------------------------------------------------------------------------


class TestHealthAndModels:
    def test_root(self, client: TestClient) -> None:
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["name"] == "KodHekim"

    def test_health(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "providers_configured" in body

    def test_models_lists_providers(self, client: TestClient) -> None:
        r = client.get("/api/models")
        assert r.status_code == 200
        body = r.json()
        assert "cerebras" in body["providers"]
        assert "gemini" in body["providers"]
        cere = body["providers"]["cerebras"]
        assert "models" in cere and len(cere["models"]) >= 3
        assert "defaults" in cere
        # Belirli model var mı
        assert "gpt-oss-120b" in cere["models"]


# ---------------------------------------------------------------------------
# Analyze + status + report (statik mod, fake clone)
# ---------------------------------------------------------------------------


class TestAnalyzeStaticHappy:
    def test_post_returns_job_id(
        self, client: TestClient, patched_clone
    ) -> None:
        r = client.post(
            "/api/analyze",
            json={"repo_url": "https://github.com/x/y", "mode": "static"},
        )
        assert r.status_code == 202
        body = r.json()
        assert body["job_id"]
        # Pipeline arka thread'de çok hızlı başlayabilir; status zaten ilerlemiş olabilir
        assert body["status"] in {"running", "done"}
        assert body.get("source_files", 0) >= 1

    def test_full_lifecycle(self, client: TestClient, patched_clone) -> None:
        r = client.post(
            "/api/analyze",
            json={"repo_url": "https://github.com/x/y", "mode": "static"},
        )
        job_id = r.json()["job_id"]
        final = _wait_until_done(client, job_id)
        assert final["status"] == "done"

        rep = client.get(f"/api/report/{job_id}")
        assert rep.status_code == 200
        body = rep.json()
        assert body["mode"] == "static"
        assert body["report"] is not None
        assert body["report"]["health"]["overall"] >= 0
        assert len(body["issues"]) > 0
        assert body["events"][-1]["type"] == "all_done"

    def test_report_pending_returns_202(
        self, client: TestClient, patched_clone, monkeypatch
    ) -> None:
        # Pipeline yavaş bir kuyruğa girsin diye worker hemen sentinel atmasın:
        # bunun yerine post sonra report'u hemen sorgula — yarış olabilir,
        # garantili olması için clone'u yavaşlat.
        import agents.orchestrator as orch

        orig = orch.run_pipeline

        def slow_pipeline(*a, **kw):
            time.sleep(0.8)
            return orig(*a, **kw)

        monkeypatch.setattr("api.store.run_pipeline", slow_pipeline)

        r = client.post(
            "/api/analyze",
            json={"repo_url": "https://github.com/x/y", "mode": "static"},
        )
        job_id = r.json()["job_id"]
        # Hemen report sorgula — henüz bitmemiş
        rep = client.get(f"/api/report/{job_id}")
        assert rep.status_code == 202
        # Daha sonra bitince 200
        _wait_until_done(client, job_id)
        rep = client.get(f"/api/report/{job_id}")
        assert rep.status_code == 200


# ---------------------------------------------------------------------------
# Hata yolları
# ---------------------------------------------------------------------------


class TestErrorPaths:
    def test_empty_url_400(self, client: TestClient) -> None:
        r = client.post("/api/analyze", json={"repo_url": "  "})
        assert r.status_code == 400

    def test_unknown_job_id_404(self, client: TestClient) -> None:
        r = client.get("/api/report/does-not-exist")
        assert r.status_code == 404
        r = client.get("/api/jobs/does-not-exist/status")
        assert r.status_code == 404

    def test_clone_404_propagates(
        self, client: TestClient, patched_clone
    ) -> None:
        r = client.post(
            "/api/analyze",
            json={"repo_url": "https://github.com/x/bad-url", "mode": "static"},
        )
        assert r.status_code == 404
        body = r.json()
        assert "404" in body.get("detail", "").lower() or "bulunamad" in body.get("detail", "").lower()

    def test_invalid_mode_validation(self, client: TestClient) -> None:
        r = client.post(
            "/api/analyze",
            json={"repo_url": "https://github.com/x/y", "mode": "uydurma"},
        )
        assert r.status_code == 422

    def test_invalid_provider_validation(self, client: TestClient) -> None:
        r = client.post(
            "/api/analyze",
            json={
                "repo_url": "https://github.com/x/y",
                "provider": "openai",
            },
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# SSE stream — endpoint resolved + queue mechanic
# ---------------------------------------------------------------------------


class TestSSEStream:
    def test_stream_unknown_job_404(self, client: TestClient) -> None:
        with client.stream("GET", "/api/analyze/ghost/stream") as r:
            assert r.status_code == 404

    def test_queue_drained_with_sentinel(
        self, client: TestClient, patched_clone
    ) -> None:
        """Pipeline tamamlandığında event queue'da event'ler birikir,
        en sonda `None` sentinel olur. SSE generator bu sentinel'i görüp döner.

        Bu test SSE bağlantısının kendisini değil, queue mantığını doğrular —
        SSE entegrasyonu manuel curl/canlı server üzerinde doğrulanır.
        """
        r = client.post(
            "/api/analyze",
            json={"repo_url": "https://github.com/x/y", "mode": "static"},
        )
        job_id = r.json()["job_id"]
        _wait_until_done(client, job_id)

        record = store_mod.get_job(job_id)
        assert record is not None

        # Worker'da status="done" sonrası cleanup + sentinel push sırasıyla
        # gerçekleşir; sentinel'in queue'ya ulaşmasını bekle.
        events: list = []
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            while not record.queue.empty():
                events.append(record.queue.get_nowait())
            if events and events[-1] is None:
                break
            time.sleep(0.05)

        event_types = [e.type for e in events if e is not None]
        assert "clone_done" in event_types
        assert "agent_started" in event_types
        assert "all_done" in event_types
        # En son eleman sentinel (None) olmalı
        assert events[-1] is None

    # NOT: TestClient + sse-starlette stream iter_lines bağlantı kapatma
    # konusunda güvenilir değil (Windows ASGI). Stream endpoint'inin
    # gerçek davranışı uvicorn ile manuel doğrulanır (`curl -N`).
    # Burada queue mantığı (yukarıdaki test) protokolü garanti eder.
