"""F-G-H-I — Impact, Surgeon, Chief ajanları için birim testler (mocked LLM)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

from agents.chief import chief_agent_llm
from agents.chief_heuristic import (
    chief_agent_heuristic,
    health_score,
    severity_breakdown,
    top_priorities,
)
from agents.impact_analyst import impact_agent_llm
from agents.impact_heuristic import impact_agent_heuristic
from agents.issue import Issue
from agents.surgeon import surgeon_agent
from agents.types import FixSuggestion, ImpactBreakdown, TopPriority
from analysis.fix_recipe_validator import validate_recipe
from llm.base import LLMError, LLMProvider, LLMResponse


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "bad_code_examples"


# ---------------------------------------------------------------------------
# Yardımcı: sahte Issue üret
# ---------------------------------------------------------------------------


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
        snippet="for u in users: posts = ...",
        explanation="N+1 sorgu",
        static_confidence=0.8,
    )


class _FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, json_response: dict):
        self.json_response = json_response
        self.calls: list[dict] = []

    def list_models(self):
        return ["x"]

    def complete(self, prompt, model, **kw):
        self.calls.append({"prompt": prompt, "kw": kw})
        return LLMResponse(text="", json=self.json_response, tokens_used=10, model=model, latency_ms=5)


# ---------------------------------------------------------------------------
# fix_recipe_validator
# ---------------------------------------------------------------------------


class TestFixRecipeValidator:
    GOOD_RECIPE = (
        "1. Kök neden: N+1 sorgu.\n"
        "2. Batch fetch kullan.\n"
        "3. Sonuçları grupla.\n"
        "4. Integration test ekle."
    )

    def test_valid_recipe(self) -> None:
        ok, err = validate_recipe(self.GOOD_RECIPE)
        assert ok and err is None

    def test_empty_recipe(self) -> None:
        ok, err = validate_recipe("")
        assert not ok

    def test_garbage(self) -> None:
        ok, err = validate_recipe("(reçete üretilemedi)")
        assert not ok


# ---------------------------------------------------------------------------
# impact_heuristic
# ---------------------------------------------------------------------------


class TestImpactHeuristic:
    def test_produces_breakdown_per_issue(self) -> None:
        issues = [_issue("issue-001"), _issue("issue-002", code="HARDCODED_SECRET", category="security")]
        out = impact_agent_heuristic(issues)
        assert len(out) == 2
        assert all(isinstance(x, ImpactBreakdown) for x in out)
        assert all(0 <= x.impact_score <= 100 for x in out)
        # Security >= performance baseline (kategori multiplier)
        sec = next(x for x in out if x.issue_id == "issue-002")
        perf = next(x for x in out if x.issue_id == "issue-001")
        assert sec.impact_score >= perf.impact_score

    def test_unknown_code_uses_default(self) -> None:
        unknown = _issue(code="MADE_UP_CODE")
        out = impact_agent_heuristic([unknown])
        assert out[0].explanation_tr  # template default'unu üretiyor


# ---------------------------------------------------------------------------
# impact_analyst (LLM)
# ---------------------------------------------------------------------------


class TestImpactAnalystLLM:
    def test_llm_overrides_explanation(self) -> None:
        issues = [_issue("issue-001"), _issue("issue-002", code="MISSING_TIMEOUT")]
        provider = _FakeProvider({
            "impacts": [
                {"issue_id": "issue-001", "explanation_tr": "yeni açıklama 1", "impact_score": 88},
                {"issue_id": "issue-002", "explanation_tr": "yeni açıklama 2"},
            ]
        })
        out = impact_agent_llm(issues, provider=provider, model="x")
        exp_by_id = {x.issue_id: x.explanation_tr for x in out}
        assert exp_by_id["issue-001"] == "yeni açıklama 1"
        assert exp_by_id["issue-002"] == "yeni açıklama 2"
        scores = {x.issue_id: x.impact_score for x in out}
        assert scores["issue-001"] == 88

    def test_llm_error_keeps_heuristic(self) -> None:
        class Crash(LLMProvider):
            name = "crash"

            def list_models(self):
                return ["x"]

            def complete(self, *a, **kw):
                raise LLMError("down")

        issues = [_issue("issue-001")]
        out = impact_agent_llm(issues, provider=Crash(), model="x")
        assert len(out) == 1
        assert out[0].explanation_tr  # heuristic default korundu

    def test_empty_input(self) -> None:
        out = impact_agent_llm([], provider=_FakeProvider({"impacts": []}), model="x")
        assert out == []


# ---------------------------------------------------------------------------
# surgeon
# ---------------------------------------------------------------------------


GOOD_RECIPE = (
    "1. Kök neden: N+1 sorgu.\n"
    "2. Batch fetch kullan.\n"
    "3. Sonuçları grupla.\n"
    "4. Integration test ekle."
)


class TestSurgeon:
    def test_valid_recipe_passes_through(self, tmp_path: Path) -> None:
        (tmp_path / "api.py").write_text("# fake source\n", encoding="utf-8")
        provider = _FakeProvider({
            "fixes": [
                {
                    "issue_id": "issue-001",
                    "fix_instruction_tr": GOOD_RECIPE,
                    "risk_level": 2,
                    "test_suggestion": "Test ekle.",
                    "improvement_estimate": "%80",
                }
            ],
        })
        out = surgeon_agent(
            [_issue()],
            repo_path=tmp_path,
            provider=provider,
            model="x",
        )
        assert len(out) == 1
        fix = out[0]
        assert fix.recipe_valid
        assert fix.risk_level == 2

    def test_invalid_recipe_falls_back(self, tmp_path: Path) -> None:
        (tmp_path / "api.py").write_text("# fake source\n", encoding="utf-8")
        provider = _FakeProvider({
            "fixes": [
                {
                    "issue_id": "issue-001",
                    "fix_instruction_tr": "kısa",
                    "risk_level": 1,
                    "test_suggestion": "x",
                    "improvement_estimate": "y",
                }
            ],
        })
        out = surgeon_agent([_issue()], repo_path=tmp_path, provider=provider, model="x")
        assert len(provider.calls) == 1
        assert out[0].recipe_valid
        assert len(out[0].fix_instruction_tr) >= 40

    def test_llm_error_uses_heuristic_recipe(self, tmp_path: Path) -> None:
        (tmp_path / "api.py").write_text("x\n", encoding="utf-8")

        class Crash(LLMProvider):
            name = "crash"

            def list_models(self):
                return ["x"]

            def complete(self, *a, **kw):
                raise LLMError("nope")

        out = surgeon_agent([_issue()], repo_path=tmp_path, provider=Crash(), model="x")
        assert out[0].recipe_valid
        assert len(out[0].fix_instruction_tr) >= 40
        assert "N1_QUERY" in out[0].fix_instruction_tr or "1." in out[0].fix_instruction_tr


# ---------------------------------------------------------------------------
# chief
# ---------------------------------------------------------------------------


class TestChief:
    def _impacts_for(self, issues: list[Issue]) -> list[ImpactBreakdown]:
        return impact_agent_heuristic(issues)

    def test_health_score_perfect_when_no_issues(self) -> None:
        s = health_score([])
        assert s.overall == 100 and s.performance == 100 and s.security == 100 and s.quality == 100

    def test_health_score_drops_with_high_issues(self) -> None:
        issues = [_issue(severity="high") for _ in range(3)]
        s = health_score(issues)
        # 3 high performance → 30 penalty → 70 overall, perf=100-30*2=40
        assert s.overall < 100
        assert s.performance < s.overall  # performance ağırlıklı

    def test_severity_breakdown(self) -> None:
        issues = [_issue(severity="high"), _issue(severity="medium"), _issue(severity="low")]
        b = severity_breakdown(issues)
        assert b == {"high": 1, "medium": 1, "low": 1}

    def test_top_priorities_returns_at_most_k(self) -> None:
        issues = [_issue(f"issue-{i:03d}") for i in range(1, 11)]
        impacts = impact_agent_heuristic(issues)
        impacts_by_id = {x.issue_id: x for x in impacts}
        top = top_priorities(issues, impacts_by_id, k=3)
        assert len(top) == 3

    def test_heuristic_chief_returns_report(self) -> None:
        issues = [_issue()]
        report = chief_agent_heuristic(issues, self._impacts_for(issues))
        assert report.issues_count == 1
        assert report.health.overall < 100
        assert "Statik" in report.executive_summary

    def test_llm_chief_uses_summary(self) -> None:
        issues = [_issue()]
        provider = _FakeProvider({
            "executive_summary": "p1.\n\np2.\n\np3.",
            "roadmap": ["1. yap", "2. yap"],
        })
        report = chief_agent_llm(issues, self._impacts_for(issues), provider=provider, model="x")
        assert report.executive_summary.startswith("p1.")
        assert len(report.roadmap) == 2

    def test_llm_chief_falls_back_on_error(self) -> None:
        class Crash(LLMProvider):
            name = "crash"

            def list_models(self):
                return ["x"]

            def complete(self, *a, **kw):
                raise LLMError("down")

        issues = [_issue()]
        report = chief_agent_llm(issues, self._impacts_for(issues), provider=Crash(), model="x")
        assert "skoru" in report.executive_summary.lower()  # heuristic özet
