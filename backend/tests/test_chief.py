"""Faz I — Hekimbaşı (LLM + heuristic) genişletilmiş testleri.

Kapsama eklenenler:
- Sağlık skoru formülü: severity ağırlıkları (high=10, med=5, low=2),
  kategori ağırlıkları (perf×2, security×3, quality×1).
- Health score alt sınırı: max(0, 100-penalty).
- Top priorities ROI sıralı.
- LLM prompt'a tüm placeholder'lar dolduruldu.
- CHIEF_SCHEMA + temperature provider'a iletildi.
- FixSuggestion'lar to_dict() ile serialize ediliyor.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.chief import CHIEF_SCHEMA, chief_agent_llm
from agents.chief_heuristic import (
    chief_agent_heuristic,
    health_score,
    severity_breakdown,
    top_priorities,
)
from agents.impact_heuristic import impact_agent_heuristic
from agents.issue import Issue
from agents.types import FinalReport, FixSuggestion, HealthScore, ImpactBreakdown
from llm.base import LLMError, LLMProvider, LLMResponse


def _issue(
    iid: str = "issue-001",
    code: str = "N1_QUERY",
    category: str = "performance",
    severity: str = "high",
) -> Issue:
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


class _RecorderProvider(LLMProvider):
    name = "recorder"

    def __init__(self, response: dict):
        self.response = response
        self.calls: list[dict] = []

    def list_models(self):
        return ["x"]

    def complete(self, prompt, model, **kw):
        self.calls.append({"prompt": prompt, "kw": kw, "model": model})
        return LLMResponse(
            text="", json=self.response, tokens_used=10, model=model, latency_ms=2
        )


# ---------------------------------------------------------------------------
# Health score formülü
# ---------------------------------------------------------------------------


class TestHealthScoreFormula:
    """developer.md §4.4 + chief_heuristic.health_score()."""

    def test_severity_weights(self) -> None:
        """high=10, medium=5; low kalite gürültüsü skora girmez."""
        s = health_score([_issue(severity="high")])
        assert s.performance == 100 - 10 * 2
        s = health_score([_issue(severity="medium")])
        assert s.performance == 100 - 5 * 2
        # düşük performans bulguları skora girer (v4 §4.4)
        s = health_score([_issue(severity="low")])
        assert s.performance == 100 - 2 * 2
        # düşük kalite bulguları da skora girer
        s = health_score([_issue(category="quality", severity="low", code="DEAD_CODE")])
        assert s.quality == 100 - 2 * 1

    def test_category_multipliers(self) -> None:
        """perf+memory ×2, security+reliability ×3, quality ×1."""
        # security high tek başına → 3 * 10 = 30 → security=70
        s = health_score([_issue(category="security", severity="high")])
        assert s.security == 100 - 10 * 3
        # quality high → 1 * 10 = 10 → quality=90
        s = health_score([_issue(category="quality", severity="high")])
        assert s.quality == 100 - 10 * 1
        # reliability high security alt skoruna girer (penaltisi)
        s = health_score([_issue(category="reliability", severity="high")])
        assert s.security == 100 - 10 * 3
        # memory high performance alt skoruna girer
        s = health_score([_issue(category="memory", severity="high")])
        assert s.performance == 100 - 10 * 2

    def test_minimum_zero(self) -> None:
        """Odaklı skor: en fazla 12 bulgu + overall tavan ceza → skor 0'a yapışmaz."""
        issues = [
            Issue(
                id=f"p-{i}",
                code=f"P{i}",
                category="performance",
                severity="high",
                file=f"f{i}.py",
                line_start=1,
                line_end=1,
                snippet="",
                explanation="",
                static_confidence=0.8,
            )
            for i in range(50)
        ]
        s = health_score(issues)
        assert s.overall >= 40
        assert s.performance <= 50

    def test_overall_is_sum_penalty(self) -> None:
        """Tüm bulgular kategori cezasına girer (v4 §4.4)."""
        issues = [
            _issue("a", code="N1_QUERY", category="performance", severity="high"),
            _issue("b", code="HARDCODED_SECRET", category="security", severity="medium"),
            _issue("c", code="DEAD_CODE", category="quality", severity="low"),
        ]
        s = health_score(issues)
        assert s.overall == 100 - (10 + 5 + 2)

    def test_perfect_when_empty(self) -> None:
        s = health_score([])
        assert (s.overall, s.performance, s.security, s.quality) == (100, 100, 100, 100)


# ---------------------------------------------------------------------------
# Top priorities ROI sıralaması
# ---------------------------------------------------------------------------


class TestTopPriorities:
    def test_roi_descending(self) -> None:
        # 5 farklı impact_score
        issues = [_issue(f"i-{i}") for i in range(5)]
        impacts = [
            ImpactBreakdown(
                issue_id=f"i-{i}",
                impact_score=10 * (i + 1),  # 10, 20, 30, 40, 50
                remediation_effort_hours=1.0,
            )
            for i in range(5)
        ]
        impacts_by_id = {x.issue_id: x for x in impacts}
        top = top_priorities(issues, impacts_by_id, k=5)
        scores = [p.roi_score for p in top]
        assert scores == sorted(scores, reverse=True)
        # En yüksek skor en üstte
        assert top[0].issue_id == "i-4"

    def test_effort_floor_quarter_hour(self) -> None:
        """Effort 0 ya da negatif olsa bile ÷0 olmaz (min 0.25 saat)."""
        issues = [_issue("a")]
        impacts = {
            "a": ImpactBreakdown(
                issue_id="a", impact_score=80, remediation_effort_hours=0.0
            )
        }
        top = top_priorities(issues, impacts)
        # 80 / 0.25 = 320
        assert top[0].roi_score == pytest.approx(320.0)

    def test_missing_impact_skipped(self) -> None:
        """Impact bulunmayan issue, top'a girmez (silently skipped)."""
        issues = [_issue("a"), _issue("b")]
        impacts = {
            "a": ImpactBreakdown(issue_id="a", impact_score=50, remediation_effort_hours=1.0)
        }
        top = top_priorities(issues, impacts, k=3)
        ids = {p.issue_id for p in top}
        assert ids == {"a"}


# ---------------------------------------------------------------------------
# LLM Hekimbaşı — prompt placeholder dolumu
# ---------------------------------------------------------------------------


class TestChiefLLMPromptFilling:
    def test_all_placeholders_filled(self) -> None:
        issues = [
            _issue("issue-001", severity="high"),
            _issue("issue-002", severity="medium"),
            _issue("issue-003", severity="low"),
        ]
        impacts = impact_agent_heuristic(issues)
        provider = _RecorderProvider({
            "executive_summary": "p1\n\np2\n\np3",
            "roadmap": ["1. x", "2. y"],
        })
        chief_agent_llm(issues, impacts, provider=provider, model="x")

        prompt = provider.calls[0]["prompt"]
        # Placeholder'lar kalmamalı
        for ph in [
            "{overall}", "{perf}", "{sec}", "{qual}",
            "{high}", "{medium}", "{low}", "{total}",
            "{top_block}", "{issues_block}",
        ]:
            assert ph not in prompt

        # Bilgilerin değerleri prompt'ta görünür
        assert "high=1" in prompt
        assert "medium=1" in prompt
        assert "low=1" in prompt
        assert "toplam=3" in prompt
        assert "issue-001" in prompt

    def test_schema_and_temperature_transport(self) -> None:
        issues = [_issue()]
        impacts = impact_agent_heuristic(issues)
        provider = _RecorderProvider({"executive_summary": "x", "roadmap": []})
        chief_agent_llm(issues, impacts, provider=provider, model="m1")
        kw = provider.calls[0]["kw"]
        assert kw.get("json_schema") == CHIEF_SCHEMA
        assert kw.get("temperature") == 0.5


# ---------------------------------------------------------------------------
# LLM çıktısı → FinalReport
# ---------------------------------------------------------------------------


class TestChiefLLMOutput:
    def test_executive_summary_three_paragraphs(self) -> None:
        """LLM 3 paragraf üretirse \\n\\n ayraçlarıyla geliyor."""
        issues = [_issue()]
        impacts = impact_agent_heuristic(issues)
        provider = _RecorderProvider({
            "executive_summary": "Paragraf 1.\n\nParagraf 2.\n\nParagraf 3.",
            "roadmap": ["1. yap"],
        })
        report = chief_agent_llm(issues, impacts, provider=provider, model="x")
        parts = [p for p in report.executive_summary.split("\n\n") if p.strip()]
        assert len(parts) == 3

    def test_roadmap_is_list(self) -> None:
        issues = [_issue()]
        impacts = impact_agent_heuristic(issues)
        provider = _RecorderProvider({
            "executive_summary": "x",
            "roadmap": ["adım 1", "adım 2", "adım 3"],
        })
        report = chief_agent_llm(issues, impacts, provider=provider, model="x")
        assert isinstance(report.roadmap, list)
        assert len(report.roadmap) == 3

    def test_missing_roadmap_handled(self) -> None:
        issues = [_issue()]
        impacts = impact_agent_heuristic(issues)
        provider = _RecorderProvider({"executive_summary": "x"})  # no roadmap key
        report = chief_agent_llm(issues, impacts, provider=provider, model="x")
        assert report.roadmap == []


# ---------------------------------------------------------------------------
# FinalReport serileştirme
# ---------------------------------------------------------------------------


class TestFinalReportSerialization:
    def test_report_fields_serialized_to_dict(self) -> None:
        issues = [_issue("issue-001")]
        impacts = impact_agent_heuristic(issues)
        provider = _RecorderProvider({"executive_summary": "x", "roadmap": []})
        report = chief_agent_llm(issues, impacts, provider=provider, model="x")
        assert report.issues_count == 1
        assert isinstance(report.issues[0], dict)
        assert report.issues[0]["id"] == "issue-001"

    def test_issues_and_impacts_serialized(self) -> None:
        issues = [_issue("i1"), _issue("i2", severity="medium")]
        impacts = impact_agent_heuristic(issues)
        report = chief_agent_heuristic(issues, impacts)
        # Detaylı listeler serialize edilmiş dict'ler olarak ulaşılabilir
        assert len(report.issues) == 2
        assert all(isinstance(d, dict) for d in report.issues)
        assert all(isinstance(d, dict) for d in report.impacts)
        ids = {d["id"] for d in report.issues}
        assert ids == {"i1", "i2"}


# ---------------------------------------------------------------------------
# Edge case'ler
# ---------------------------------------------------------------------------


class TestChiefEdgeCases:
    def test_empty_issues_llm_branch(self) -> None:
        provider = _RecorderProvider({"executive_summary": "Bulgu yok.", "roadmap": []})
        report = chief_agent_llm([], [], provider=provider, model="x")
        assert report.issues_count == 0
        assert report.health.overall == 100
        assert report.top_priorities == []

    def test_empty_issues_heuristic_branch(self) -> None:
        report = chief_agent_heuristic([], [])
        assert report.issues_count == 0
        assert report.health.overall == 100

    def test_progress_callback_invoked(self) -> None:
        provider = _RecorderProvider({"executive_summary": "x", "roadmap": []})
        msgs: list[str] = []
        chief_agent_llm(
            [_issue()],
            impact_agent_heuristic([_issue()]),
            provider=provider,
            model="x",
            on_progress=msgs.append,
        )
        assert msgs, "progress callback hiç tetiklenmedi"


# ---------------------------------------------------------------------------
# Prompt dosyası sözleşmesi
# ---------------------------------------------------------------------------


class TestChiefPromptContract:
    def test_prompt_mentions_no_money(self) -> None:
        path = Path(__file__).resolve().parent.parent / "prompts" / "chief.md"
        content = path.read_text(encoding="utf-8").lower()
        assert "parasal" in content
        # 3 paragraf gereksinimi
        assert "3 paragraf" in content or "3 paragraph" in content

    def test_prompt_has_all_placeholders(self) -> None:
        path = Path(__file__).resolve().parent.parent / "prompts" / "chief.md"
        content = path.read_text(encoding="utf-8")
        for ph in [
            "{overall}", "{perf}", "{sec}", "{qual}",
            "{high}", "{medium}", "{low}", "{total}",
            "{top_block}", "{issues_block}",
        ]:
            assert ph in content, f"prompt template'inde eksik placeholder: {ph}"
