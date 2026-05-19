"""Faz O — Demo & Pazarlama Özellikleri testleri.

Kapsam:
- `simulate_post_fix_score` / `score_delta` (§16.1)
- `POST /api/report/:job_id/simulate` endpoint
- `compute_actual_metrics` + `estimate_modes` (§16.3)
- `GET /api/report/:job_id/mode-comparison`
- `GET /api/badge/:owner/:repo.svg` (§16.4)
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

import api.store as store_mod
from analysis.mode_comparison import compute_actual_metrics, estimate_modes
from analysis.repo_cloner import CloneResult
from analysis.simulation import (
    score_delta,
    simulate_post_fix_score,
    to_payload,
)
from agents.chief_heuristic import health_score
from agents.issue import Issue
from agents.orchestrator import Event
from agents.types import HealthScore
from api.badge import _color, render_badge_svg
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


def _issue(iid: str, code: str = "N1_QUERY", category: str = "performance", severity: str = "high") -> Issue:
    return Issue(
        id=iid,
        code=code,
        category=category,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        file="api.py",
        line_start=10,
        line_end=12,
        snippet="...",
        explanation="...",
        static_confidence=0.8,
    )


def _wait_until_done(client: TestClient, job_id: str, timeout: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = client.get(f"/api/jobs/{job_id}/status")
        if r.status_code == 200 and r.json()["status"] in {"done", "error"}:
            return r.json()
        time.sleep(0.1)
    raise TimeoutError("job bitmedi")


@pytest.fixture
def patched_clone(monkeypatch) -> None:
    def fake_clone(url: str, job_id: Optional[str] = None, **_) -> CloneResult:
        return CloneResult(
            repo_path=FIXTURE, repo_url=url, size_mb=0.5,
            commit_sha="fake", job_id=job_id or "test",
            source_file_count=1,
        )

    monkeypatch.setattr("api.analyze.clone_repo", fake_clone)
    monkeypatch.setattr("api.store.clone_repo", fake_clone)
    monkeypatch.setattr("api.store.cleanup", lambda p: None)


# ---------------------------------------------------------------------------
# simulate_post_fix_score (§16.1)
# ---------------------------------------------------------------------------


class TestSimulation:
    def test_no_fixes_keeps_score(self) -> None:
        issues = [_issue("a"), _issue("b", severity="medium")]
        current = health_score(issues)
        simulated = simulate_post_fix_score(issues, set())
        assert simulated == current

    def test_all_fixes_perfect_score(self) -> None:
        issues = [_issue("a"), _issue("b")]
        simulated = simulate_post_fix_score(issues, {"a", "b"})
        assert simulated.overall == 100
        assert simulated.performance == 100

    def test_partial_fixes_improves_score(self) -> None:
        issues = [
            _issue("a", code="N1_QUERY", severity="high"),
            _issue("b", code="MISSING_TIMEOUT", severity="high"),
            _issue("c", code="UNBOUNDED_CACHE", category="memory", severity="high"),
        ]
        current = health_score(issues)
        simulated = simulate_post_fix_score(issues, {"a"})
        assert simulated.overall > current.overall
        assert simulated.performance > current.performance

    def test_score_delta(self) -> None:
        cur = HealthScore(overall=60, performance=40, security=80, quality=70)
        sim = HealthScore(overall=85, performance=70, security=90, quality=80)
        d = score_delta(cur, sim)
        assert d.overall == 25
        assert d.performance == 30
        assert d.security == 10

    def test_payload_shape(self) -> None:
        cur = HealthScore(overall=50, performance=50, security=50, quality=50)
        sim = HealthScore(overall=80, performance=80, security=80, quality=80)
        d = score_delta(cur, sim)
        p = to_payload(cur, sim, d)
        assert set(p.keys()) == {"current_score", "simulated_score", "delta"}
        assert p["delta"]["overall"] == 30


# ---------------------------------------------------------------------------
# POST /api/report/:job_id/simulate
# ---------------------------------------------------------------------------


class TestSimulateEndpoint:
    def test_simulate_endpoint(self, client: TestClient, patched_clone) -> None:
        # Önce job oluştur ve bitir
        r = client.post(
            "/api/analyze",
            json={"repo_url": "https://github.com/x/y", "mode": "static"},
        )
        job_id = r.json()["job_id"]
        _wait_until_done(client, job_id)

        # Raporu çek
        rep = client.get(f"/api/report/{job_id}").json()
        all_issue_ids = [i["id"] for i in rep["issues"]]

        # Tüm fix'leri kabul et → simulated 100
        sim = client.post(
            f"/api/report/{job_id}/simulate",
            json={"accepted_fix_ids": all_issue_ids},
        )
        assert sim.status_code == 200
        body = sim.json()
        assert body["simulated_score"]["overall"] == 100
        assert body["delta"]["overall"] >= 0

    def test_simulate_unknown_job(self, client: TestClient) -> None:
        r = client.post(
            "/api/report/ghost/simulate", json={"accepted_fix_ids": []}
        )
        assert r.status_code == 404

    def test_simulate_pending(
        self, client: TestClient, patched_clone, monkeypatch
    ) -> None:
        # Pipeline yavaşla
        import api.store as st

        orig = st.run_pipeline

        def slow(*a, **kw):
            time.sleep(0.8)
            return orig(*a, **kw)

        monkeypatch.setattr("api.store.run_pipeline", slow)
        r = client.post(
            "/api/analyze",
            json={"repo_url": "https://github.com/x/y", "mode": "static"},
        )
        job_id = r.json()["job_id"]
        # Hemen simulate çağır
        sim = client.post(
            f"/api/report/{job_id}/simulate", json={"accepted_fix_ids": []}
        )
        assert sim.status_code == 409


# ---------------------------------------------------------------------------
# Mode comparison (§16.3)
# ---------------------------------------------------------------------------


class TestModeComparison:
    def test_compute_actual_metrics(self) -> None:
        events = [
            Event(type="agent_started", data={}, timestamp="2026-05-18T10:00:00Z"),
            Event(type="issue_found", data={}, timestamp="2026-05-18T10:00:05Z"),
            Event(type="issue_found", data={}, timestamp="2026-05-18T10:00:06Z"),
            Event(type="all_done", data={}, timestamp="2026-05-18T10:00:10Z"),
        ]
        m = compute_actual_metrics(events)
        assert m["seconds"] == 10.0
        assert m["issues"] == 2

    def test_compute_actual_empty(self) -> None:
        m = compute_actual_metrics([])
        assert m == {"seconds": 0.0, "tokens": 0, "issues": 0}

    def test_estimate_modes_includes_actual(self) -> None:
        out = estimate_modes(
            file_count=10,
            actual_mode="static",
            actual_seconds=2.5,
            actual_tokens=0,
            actual_issues=20,
        )
        # 3 mod
        assert len(out) == 3
        names = {m.mode for m in out}
        assert names == {"static", "hybrid", "deep"}
        # is_actual yalnız static için
        actuals = [m for m in out if m.is_actual]
        assert len(actuals) == 1
        assert actuals[0].mode == "static"
        # static actual değerini olduğu gibi kullanıyor
        assert actuals[0].estimated_seconds == 2.5
        assert actuals[0].estimated_issues == 20

    def test_estimate_modes_token_progression(self) -> None:
        """Derin mod hibrit'ten daha fazla token tüketir."""
        out = estimate_modes(
            file_count=20, actual_mode="static",
            actual_seconds=1.0, actual_tokens=0, actual_issues=10,
        )
        by_mode = {m.mode: m for m in out}
        assert by_mode["static"].estimated_tokens == 0
        assert by_mode["hybrid"].estimated_tokens > 0
        assert by_mode["deep"].estimated_tokens > by_mode["hybrid"].estimated_tokens

    def test_mode_comparison_endpoint(
        self, client: TestClient, patched_clone
    ) -> None:
        r = client.post(
            "/api/analyze",
            json={"repo_url": "https://github.com/x/y", "mode": "static"},
        )
        job_id = r.json()["job_id"]
        _wait_until_done(client, job_id)

        rep = client.get(f"/api/report/{job_id}/mode-comparison")
        assert rep.status_code == 200
        body = rep.json()
        assert body["actual_mode"] == "static"
        assert body["file_count"] >= 1
        assert len(body["modes"]) == 3


# ---------------------------------------------------------------------------
# Badge endpoint (§16.4)
# ---------------------------------------------------------------------------


class TestBadge:
    def test_color_thresholds(self) -> None:
        assert _color(95) == "#4c1"
        assert _color(80) == "#97CA00"
        assert _color(60) == "#dfb317"
        assert _color(40) == "#fe7d37"
        assert _color(10) == "#e05d44"

    def test_render_badge_svg_is_valid_xml(self) -> None:
        svg = render_badge_svg("kodhekim", "78/100", "#97CA00")
        # XML parse edilebilmeli
        root = ElementTree.fromstring(svg)
        assert root.tag.endswith("svg")
        assert "kodhekim" in svg
        assert "78/100" in svg

    def test_badge_endpoint_unscored(self, client: TestClient) -> None:
        r = client.get("/api/badge/foo/bar.svg")
        assert r.status_code == 200
        assert "image/svg+xml" in r.headers["content-type"]
        assert "unscored" in r.text
        assert "kodhekim" in r.text

    def test_badge_endpoint_with_score(self, client: TestClient) -> None:
        r = client.get("/api/badge/foo/bar.svg?score=78")
        assert r.status_code == 200
        assert "78/100" in r.text
        # Renk yeşilimsi
        assert "97CA00" in r.text or "4c1" in r.text

    def test_badge_endpoint_invalid_score_falls_back(
        self, client: TestClient
    ) -> None:
        # Pydantic Query validation: int olmayan değer → 422
        r = client.get("/api/badge/foo/bar.svg?score=abc")
        assert r.status_code == 422
        # Range dışı → unscored fallback
        r = client.get("/api/badge/foo/bar.svg?score=500")
        assert r.status_code == 200
        assert "unscored" in r.text
