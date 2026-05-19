"""Bulgu odaklama — skor ve rapor filtreleri."""

from __future__ import annotations

from agents.chief_heuristic import health_score
from agents.issue import Issue
from analysis.issue_focus import issues_for_report, issues_for_scoring, is_scoring_issue
from analysis.scan import scan_repo
from pathlib import Path


def _issue(**kw) -> Issue:
    defaults = dict(
        id="x",
        code="N1_QUERY",
        category="performance",
        severity="high",
        file="a.py",
        line_start=1,
        line_end=1,
        snippet="",
        explanation="",
        static_confidence=0.8,
    )
    defaults.update(kw)
    return Issue(**defaults)  # type: ignore[arg-type]


def test_dead_code_excluded_from_scoring() -> None:
    issues = [
        _issue(code="N1_QUERY", severity="high"),
        _issue(code="DEAD_CODE", category="quality", severity="low"),
    ]
    scoring = issues_for_scoring(issues)
    assert all(i.code != "DEAD_CODE" for i in scoring)
    assert len(scoring) == 1


def test_scoring_caps_at_twelve_high() -> None:
    many = [
        _issue(id=f"h{i}", code=f"ISSUE_{i}", severity="high", file=f"f{i}.py")
        for i in range(20)
    ]
    assert len(issues_for_scoring(many)) == 12


def test_report_limits_dead_code() -> None:
    dead = [
        _issue(id=f"d{i}", code="DEAD_CODE", category="quality", severity="low", file=f"f{i}.py")
        for i in range(10)
    ]
    out = issues_for_report(dead)
    assert sum(1 for i in out if i.code == "DEAD_CODE") <= 3


def test_repeated_compute_counts_for_scoring() -> None:
    issues = [
        _issue(code="REPEATED_COMPUTE", category="performance", severity="low"),
    ]
    assert len(issues_for_scoring(issues)) == 1
    score = health_score(issues)
    assert score.overall < 100
    assert score.performance < 100


def test_bad_fixture_score_not_zero() -> None:
    repo = Path(__file__).resolve().parent / "fixtures" / "bad_code_examples"
    report = scan_repo(repo)
    from agents.profiler import profiler_agent_static

    issues = profiler_agent_static(repo)
    score = health_score(issues)
    assert len(issues) >= 15
    assert score.overall >= 40, f"Skor çok düşük: {score}"
