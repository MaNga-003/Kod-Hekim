"""Pipeline veri tipleri — Issue dışında (o `agents/issue.py`'da)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Etki Analisti çıktısı (developer.md §4.2)
# ---------------------------------------------------------------------------


@dataclass
class ImpactBreakdown:
    issue_id: str
    impact_score: int  # 0-100
    impact_dimensions: dict = field(default_factory=dict)
    explanation_tr: str = ""
    remediation_effort_hours: float = 0.5

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Cerrah çıktısı (developer.md §4.3)
# ---------------------------------------------------------------------------


@dataclass
class FixSuggestion:
    issue_id: str
    fix_instruction_tr: str
    risk_level: int  # 1-5
    test_suggestion: str
    improvement_estimate: str
    recipe_valid: bool

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Hekimbaşı çıktısı (developer.md §4.4)
# ---------------------------------------------------------------------------


@dataclass
class HealthScore:
    overall: int
    performance: int
    security: int
    quality: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TopPriority:
    issue_id: str
    code: str
    rationale: str  # neden öncelikli
    roi_score: float  # impact / effort


@dataclass
class FinalReport:
    health: HealthScore
    issues_count: int
    severity_breakdown: dict  # {"high": N, "medium": N, "low": N}
    top_priorities: list[TopPriority]
    executive_summary: str  # 3 paragraf (Hibrit/Derin), heuristic'de placeholder
    roadmap: list[str]  # önceliklendirilmiş yapılacaklar
    # Detaylı bulgular dahil edilmek istenirse:
    issues: list[dict] = field(default_factory=list)
    impacts: list[dict] = field(default_factory=list)
    fixes: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "health": self.health.to_dict(),
            "issues_count": self.issues_count,
            "severity_breakdown": self.severity_breakdown,
            "top_priorities": [
                {
                    "issue_id": p.issue_id,
                    "code": p.code,
                    "rationale": p.rationale,
                    "roi_score": round(p.roi_score, 2),
                }
                for p in self.top_priorities
            ],
            "executive_summary": self.executive_summary,
            "roadmap": self.roadmap,
            "issues": self.issues,
            "impacts": self.impacts,
            "fixes": self.fixes,
        }
        return d
