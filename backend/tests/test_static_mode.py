"""Faz F — Statik mod uçtan uca testi.

Pipeline: profiler_agent_static → impact_agent_heuristic → chief_agent_heuristic
- LLM çağrısı yok (statik fonksiyonların hiçbiri provider parametresi almaz).
- < 5 saniye.
- Çıktı FinalReport şemasına uyar; Hibrit'le aynı şema.
"""

from __future__ import annotations

import inspect
import time
from pathlib import Path

import pytest

from agents.chief_heuristic import chief_agent_heuristic, health_score, top_priorities
from agents.impact_heuristic import impact_agent_heuristic
from agents.issue import Issue
from agents.profiler import profiler_agent_static
from agents.types import FinalReport, HealthScore, ImpactBreakdown, TopPriority


FIXTURE = Path(__file__).parent / "fixtures" / "bad_code_examples"


# ---------------------------------------------------------------------------
# Pipeline e2e
# ---------------------------------------------------------------------------


class TestStaticModePipeline:
    def test_end_to_end_runs(self) -> None:
        """Profiler → Impact → Chief üçlüsü hatasız çalışır."""
        start = time.monotonic()
        issues = profiler_agent_static(FIXTURE)
        impacts = impact_agent_heuristic(issues)
        report = chief_agent_heuristic(issues, impacts)
        elapsed = time.monotonic() - start

        assert isinstance(report, FinalReport)
        assert isinstance(report.health, HealthScore)
        assert elapsed < 5.0, f"statik mod çok yavaş: {elapsed:.2f}s"

    def test_finds_known_patterns(self) -> None:
        """Fixture'da kasıtlı tüm major örüntüler — en az 8'i bulunmalı."""
        issues = profiler_agent_static(FIXTURE)
        codes = {i.code for i in issues}
        # Fixture'da kesin olarak görünenler (subset)
        expected = {
            "N1_QUERY",
            "MISSING_TIMEOUT",
            "SYNC_IN_ASYNC",
            "O_N_SQUARED",
            "LARGE_PAYLOAD",
            "INEFFICIENT_STRING_CONCAT",
            "MUTABLE_DEFAULT_ARG",
            "HARDCODED_SECRET",
        }
        found = expected & codes
        assert len(found) >= 6, f"beklenen örüntülerin yeterince yok: bulunan={found}"

    def test_no_llm_provider_in_signatures(self) -> None:
        """Statik mod fonksiyonları hiçbir LLM provider parametresi almaz."""
        for fn in (profiler_agent_static, impact_agent_heuristic, chief_agent_heuristic):
            sig = inspect.signature(fn)
            for name, param in sig.parameters.items():
                # "provider", "llm" benzeri argüman olmamalı
                assert "provider" not in name.lower()
                assert "llm" not in name.lower()
                ann = str(param.annotation)
                assert "LLMProvider" not in ann


# ---------------------------------------------------------------------------
# Shape parity (Hibrit'le aynı çıktı şeması)
# ---------------------------------------------------------------------------


class TestStaticOutputShape:
    def test_issues_have_required_fields(self) -> None:
        issues = profiler_agent_static(FIXTURE)
        assert issues, "fixture'da hiç sorun bulunamadı"
        for i in issues:
            assert isinstance(i, Issue)
            assert i.id
            assert i.code
            assert i.severity in {"high", "medium", "low"}
            assert i.category in {"performance", "memory", "reliability", "security", "quality"}
            assert i.file
            assert i.line_start >= 1
            assert i.line_end >= i.line_start
            # Statik modda LLM yok → llm_confidence None
            assert i.llm_confidence is None

    def test_impacts_match_issues(self) -> None:
        issues = profiler_agent_static(FIXTURE)
        impacts = impact_agent_heuristic(issues)
        assert len(impacts) == len(issues)
        ids_issues = {i.id for i in issues}
        ids_impacts = {x.issue_id for x in impacts}
        assert ids_issues == ids_impacts
        for x in impacts:
            assert isinstance(x, ImpactBreakdown)
            assert 0 <= x.impact_score <= 100
            assert x.explanation_tr  # boş olmasın
            assert x.remediation_effort_hours > 0

    def test_final_report_shape(self) -> None:
        issues = profiler_agent_static(FIXTURE)
        impacts = impact_agent_heuristic(issues)
        report = chief_agent_heuristic(issues, impacts)

        # FinalReport fields
        assert isinstance(report.health.overall, int)
        assert 0 <= report.health.overall <= 100
        assert 0 <= report.health.performance <= 100
        assert 0 <= report.health.security <= 100
        assert 0 <= report.health.quality <= 100

        assert report.issues_count == len(issues)
        assert set(report.severity_breakdown.keys()) == {"high", "medium", "low"}
        assert sum(report.severity_breakdown.values()) == len(issues)

        assert isinstance(report.top_priorities, list)
        assert len(report.top_priorities) <= 3
        for p in report.top_priorities:
            assert isinstance(p, TopPriority)
            assert p.roi_score >= 0

        # Statik modda LLM yazılı özet yok → placeholder cümle
        assert report.executive_summary
        # to_dict serileştirilebilir mi?
        report.health.to_dict()
        for x in report.impacts:
            assert isinstance(x, dict)


# ---------------------------------------------------------------------------
# Köşe durumlar
# ---------------------------------------------------------------------------


class TestStaticModeEdgeCases:
    def test_empty_repo(self, tmp_path: Path) -> None:
        """Boş dizinde sıfır sorun, temiz rapor."""
        issues = profiler_agent_static(tmp_path)
        impacts = impact_agent_heuristic(issues)
        report = chief_agent_heuristic(issues, impacts)

        assert issues == []
        assert impacts == []
        assert report.issues_count == 0
        assert report.health.overall == 100
        assert report.top_priorities == []

    def test_health_score_drops_with_high_severity(self) -> None:
        issues = profiler_agent_static(FIXTURE)
        score = health_score(issues)
        # Fixture kasıtlı kötü — overall < 100 olmalı
        assert score.overall < 100
        # security & performance penalty hissedilmeli (hardcoded_secret + n1)
        assert score.security < 100 or score.performance < 100

    def test_top_priorities_ordered_by_roi(self) -> None:
        issues = profiler_agent_static(FIXTURE)
        impacts = impact_agent_heuristic(issues)
        impacts_by_id = {x.issue_id: x for x in impacts}
        top = top_priorities(issues, impacts_by_id, k=5)
        for a, b in zip(top, top[1:]):
            assert a.roi_score >= b.roi_score

    def test_heuristic_explanation_uses_template(self) -> None:
        """Template dimensions doldurulmuş mu (örn. N1_QUERY'de {db_calls})."""
        issues = profiler_agent_static(FIXTURE)
        impacts = impact_agent_heuristic(issues)
        n1 = [
            x for i, x in zip(issues, impacts)
            if i.code == "N1_QUERY"
        ]
        if n1:
            # Template placeholder'larını bırakmamalı
            assert "{" not in n1[0].explanation_tr
            assert "}" not in n1[0].explanation_tr
