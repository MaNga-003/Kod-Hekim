"""Hibrit/Derin mod Hekimbaşı (Dr. Hekimbaşı) — heuristic skor + LLM özeti."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from llm.base import LLMError, LLMProvider

from agents.chief_heuristic import (
    health_score,
    severity_breakdown,
    top_priorities,
)
from agents.issue import Issue
from agents.types import FinalReport, ImpactBreakdown


CHIEF_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "roadmap": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["executive_summary", "roadmap"],
}


def _load_prompt() -> str:
    here = Path(__file__).resolve().parent.parent
    return (here / "prompts" / "chief.md").read_text(encoding="utf-8")


def chief_agent_llm(
    issues: list[Issue],
    impacts: list[ImpactBreakdown],
    fixes: list = (),  # type: ignore[assignment]
    *,
    provider: LLMProvider,
    model: str,
    on_progress: Optional[Callable[[str], None]] = None,
) -> FinalReport:
    progress = on_progress or (lambda msg: None)
    impacts_by_id = {x.issue_id: x for x in impacts}
    score = health_score(issues)
    breakdown = severity_breakdown(issues)
    top = top_priorities(issues, impacts_by_id)

    template = _load_prompt()
    top_block = "\n".join(
        f"- [{p.issue_id}] {p.code} (ROI={p.roi_score:.1f}) — {p.rationale[:160]}"
        for p in top
    ) or "(top 3 yok)"

    issues_block_lines = []
    for i in issues:
        imp = impacts_by_id.get(i.id)
        score_str = imp.impact_score if imp else "?"
        issues_block_lines.append(
            f"- [{i.id}] {i.severity} {i.code} @ {i.file}:{i.line_start} (impact={score_str})"
        )
    issues_block = "\n".join(issues_block_lines) or "(bulgu yok)"

    prompt = (
        template.replace("{overall}", str(score.overall))
        .replace("{perf}", str(score.performance))
        .replace("{sec}", str(score.security))
        .replace("{qual}", str(score.quality))
        .replace("{high}", str(breakdown["high"]))
        .replace("{medium}", str(breakdown["medium"]))
        .replace("{low}", str(breakdown["low"]))
        .replace("{total}", str(len(issues)))
        .replace("{top_block}", top_block)
        .replace("{issues_block}", issues_block)
    )

    summary = ""
    roadmap: list[str] = []

    progress("Hekimbaşı raporu yazılıyor…")
    try:
        resp = provider.complete(
            prompt,
            model=model,
            json_schema=CHIEF_SCHEMA,
            temperature=0.5,
            max_tokens=2048,
        )
        data = resp.get("json") or {}
        summary = data.get("executive_summary") or ""
        roadmap = list(data.get("roadmap") or [])
    except LLMError as e:
        progress(f"  ! LLM hata: {e}; heuristic özet kullanılacak.")
        summary = (
            f"Repo sağlık skoru {score.overall}/100. "
            f"{breakdown['high']} kritik, {breakdown['medium']} orta, "
            f"{breakdown['low']} düşük seviyeli bulgu var. "
            "LLM çağrısı başarısız olduğu için detaylı özet üretilemedi."
        )
        roadmap = [f"[{p.issue_id}] {p.code}: {p.rationale[:120]}" for p in top]

    return FinalReport(
        health=score,
        issues_count=len(issues),
        severity_breakdown=breakdown,
        top_priorities=top,
        executive_summary=summary,
        roadmap=roadmap,
        issues=[i.to_dict() for i in issues],
        impacts=[x.to_dict() for x in impacts],
        fixes=[f.to_dict() for f in fixes],
    )
