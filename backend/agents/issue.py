"""Ajan katmanının final `Issue` tipi.

Statik motor `IssueCandidate` üretir (analysis/static_rules/base.py).
Profiler bunları LLM ile confirm eder ve `Issue` (id + llm_confidence dahil) çıkarır.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from analysis.static_rules.base import Category, IssueCandidate, Severity


@dataclass
class Issue:
    id: str  # "issue-001" formatlı stabil ID
    code: str
    category: Category
    severity: Severity
    file: str
    line_start: int
    line_end: int
    snippet: str
    explanation: str
    static_confidence: float
    llm_confidence: Optional[float] = None  # Hibrit/Derin'de set edilir; Statik'te None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["static_confidence"] = round(self.static_confidence, 2)
        if self.llm_confidence is not None:
            d["llm_confidence"] = round(self.llm_confidence, 2)
        return d


def assign_ids(candidates: list[IssueCandidate]) -> list[tuple[str, IssueCandidate]]:
    """Stabil "issue-001", "issue-002" ID'leri ata.

    Sıra: severity (high→low), file, line_start — `scan_repo` zaten böyle sıralar
    ama burada da garantileyelim.
    """
    sev_rank = {"high": 0, "medium": 1, "low": 2}
    ordered = sorted(
        candidates,
        key=lambda c: (sev_rank.get(c.severity, 9), c.file, c.line_start, c.code),
    )
    return [(f"issue-{i + 1:03d}", c) for i, c in enumerate(ordered)]


def from_candidate(
    issue_id: str,
    cand: IssueCandidate,
    *,
    llm_confidence: Optional[float] = None,
    severity_override: Optional[Severity] = None,
    explanation_override: Optional[str] = None,
) -> Issue:
    """`IssueCandidate` → `Issue` dönüştürücü; LLM verdict'i varsa uygula."""
    return Issue(
        id=issue_id,
        code=cand.code,
        category=cand.category,
        severity=severity_override or cand.severity,
        file=cand.file,
        line_start=cand.line_start,
        line_end=cand.line_end,
        snippet=cand.snippet,
        explanation=explanation_override or cand.explanation,
        static_confidence=cand.static_confidence,
        llm_confidence=llm_confidence,
        extra=dict(cand.extra),
    )
