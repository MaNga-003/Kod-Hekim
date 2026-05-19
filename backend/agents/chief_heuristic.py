"""Statik mod Hekimbaşı — LLM yok, sade heuristic rapor.

developer-v4 §3.1: statik mod'da yönetici özeti yazılmaz; skor + top 3 yeter.
"""

from __future__ import annotations

from agents.issue import Issue
from agents.types import FinalReport, HealthScore, ImpactBreakdown, TopPriority

# Çok bulgulu repolarda overall skorun anlamsız şekilde 0'a yapışmasını önler
_OVERALL_PENALTY_CAP = 55


def health_score(issues: list[Issue]) -> HealthScore:
    """developer-v4 §4.4 — tüm bulgular kategori bazında skora girer."""
    severity_weights = {"high": 10, "medium": 5, "low": 2}

    def cat_penalty(cat: str) -> int:
        return sum(
            severity_weights[i.severity]
            for i in issues
            if i.category == cat
        )

    perf_penalty = cat_penalty("performance") + cat_penalty("memory")
    sec_penalty = cat_penalty("security") + cat_penalty("reliability")
    qual_penalty = cat_penalty("quality")

    total_penalty = min(_OVERALL_PENALTY_CAP, perf_penalty + sec_penalty + qual_penalty)

    return HealthScore(
        overall=max(0, 100 - total_penalty),
        performance=max(0, 100 - min(50, perf_penalty * 2)),
        security=max(0, 100 - min(50, sec_penalty * 3)),
        quality=max(0, 100 - min(40, qual_penalty * 1)),
    )


def severity_breakdown(issues: list[Issue]) -> dict:
    out = {"high": 0, "medium": 0, "low": 0}
    for i in issues:
        out[i.severity] += 1
    return out


def top_priorities(
    issues: list[Issue], impacts: dict[str, ImpactBreakdown], k: int = 3
) -> list[TopPriority]:
    scored: list[TopPriority] = []
    for issue in issues:
        impact = impacts.get(issue.id)
        if impact is None:
            continue
        effort = max(0.25, impact.remediation_effort_hours)
        roi = impact.impact_score / effort
        scored.append(
            TopPriority(
                issue_id=issue.id,
                code=issue.code,
                rationale=impact.explanation_tr or issue.explanation,
                roi_score=roi,
            )
        )
    scored.sort(key=lambda p: -p.roi_score)
    return scored[:k]


def chief_agent_heuristic(
    issues: list[Issue],
    impacts: list[ImpactBreakdown],
    fixes: list = (),  # type: ignore[assignment]
) -> FinalReport:
    impacts_by_id = {x.issue_id: x for x in impacts}
    top = top_priorities(issues, impacts_by_id)
    breakdown = severity_breakdown(issues)

    return FinalReport(
        health=health_score(issues),
        issues_count=len(issues),
        severity_breakdown=breakdown,
        top_priorities=top,
        executive_summary=(
            "Statik mod — yönetici özeti LLM gerektirir. Hibrit/Derin modu kullan."
        ),
        roadmap=[f"[{p.issue_id}] {p.code}: {p.rationale[:120]}" for p in top],
        issues=[i.to_dict() for i in issues],
        impacts=[x.to_dict() for x in impacts],
        fixes=[f.to_dict() for f in fixes],
    )
