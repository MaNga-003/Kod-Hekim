"""Hibrit/Derin mod Etki Analisti (Dr. Ölçücü).

Akış:
  1. Heuristic'lerden sayısal metrikleri ve default Türkçe açıklamayı al.
  2. LLM'e tüm bulguları (batched) gönder; rafine Türkçe açıklama + skor güncelleme.
  3. ImpactBreakdown üret — her Issue için tam bir kayıt garanti edilir.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from llm.base import LLMError, LLMProvider

from agents.impact_heuristic import impact_agent_heuristic
from agents.issue import Issue
from agents.types import ImpactBreakdown


logger = logging.getLogger(__name__)

IMPACT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "impacts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "explanation_tr": {"type": "string"},
                    "impact_score": {"type": "integer"},
                    "remediation_effort_hours": {"type": "number"},
                },
                "required": ["issue_id", "explanation_tr"],
            },
        }
    },
    "required": ["impacts"],
}


BATCH_SIZE = 8


def _load_prompt() -> str:
    here = Path(__file__).resolve().parent.parent
    return (here / "prompts" / "impact_analyst.md").read_text(encoding="utf-8")


def _format_issue_block(items: list[tuple[Issue, ImpactBreakdown]]) -> str:
    chunks: list[str] = []
    for issue, baseline in items:
        chunks.append(
            f"### {issue.id} — {issue.code}\n"
            f"- severity: {issue.severity}\n"
            f"- file:line: {issue.file}:{issue.line_start}\n"
            f"- snippet:\n```python\n{issue.snippet}\n```\n"
            f"- statik açıklama: {issue.explanation}\n"
            f"- heuristic skor: {baseline.impact_score}\n"
            f"- heuristic dimensions: {baseline.impact_dimensions}\n"
            f"- default Türkçe: {baseline.explanation_tr}\n"
            f"- önerilen efor (saat): {baseline.remediation_effort_hours}\n"
        )
    return "\n".join(chunks)


def _chunks(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def impact_agent_llm(
    issues: list[Issue],
    *,
    provider: LLMProvider,
    model: str,
    on_progress: Optional[Callable[[str], None]] = None,
) -> list[ImpactBreakdown]:
    """Hibrit/Derin mod — her Issue için ImpactBreakdown garantisi."""
    progress = on_progress or (lambda msg: None)

    if not issues:
        progress("Etki Analisti: bulgu yok, atlanıyor.")
        return []

    progress(f"Etki Analisti: {len(issues)} bulgu için heuristic hesaplanıyor…")
    baselines = impact_agent_heuristic(issues)
    by_id = {b.issue_id: b for b in baselines}

    if len(by_id) != len(issues):
        missing = [i.id for i in issues if i.id not in by_id]
        progress(
            f"⚠ Heuristic eksik ({len(by_id)}/{len(issues)}); eksikler yeniden üretiliyor: {missing[:5]}"
        )
        logger.warning("Impact heuristic mismatch: missing %s", missing)
        for issue in issues:
            if issue.id not in by_id:
                extra = impact_agent_heuristic([issue])
                if extra:
                    by_id[issue.id] = extra[0]

    template = _load_prompt()
    paired = [(i, by_id[i.id]) for i in issues if i.id in by_id]
    llm_updated = 0
    llm_errors = 0

    for chunk in _chunks(paired, BATCH_SIZE):
        block = _format_issue_block(chunk)
        prompt = template.replace("{issues_block}", block)
        progress(f"Etki Analisti: {len(chunk)} bulgu LLM'e gönderiliyor…")
        try:
            resp = provider.complete(
                prompt,
                model=model,
                json_schema=IMPACT_SCHEMA,
                temperature=0.2,
                max_tokens=4096,
            )
        except LLMError as e:
            llm_errors += 1
            progress(
                f"  ! LLM hata ({type(e).__name__}): {e}; bu chunk için heuristic korunuyor."
            )
            logger.warning("Impact LLM batch failed: %s", e)
            continue

        for v in (resp.get("json") or {}).get("impacts", []):
            iid = v.get("issue_id")
            if iid not in by_id:
                logger.warning("Impact LLM unknown issue_id: %s", iid)
                continue
            b = by_id[iid]
            if v.get("explanation_tr"):
                b.explanation_tr = v["explanation_tr"]
            if isinstance(v.get("impact_score"), int):
                b.impact_score = max(0, min(100, v["impact_score"]))
            if isinstance(v.get("remediation_effort_hours"), (int, float)):
                b.remediation_effort_hours = float(v["remediation_effort_hours"])
            llm_updated += 1

    ordered = [by_id[i.id] for i in issues if i.id in by_id]
    if len(ordered) != len(issues):
        progress(
            f"⚠ Etki Analisti: {len(ordered)}/{len(issues)} eşleşme — eksik kayıtlar tamamlanıyor."
        )
        for issue in issues:
            if issue.id not in by_id:
                fallback = impact_agent_heuristic([issue])
                if fallback:
                    by_id[issue.id] = fallback[0]
        ordered = [by_id[i.id] for i in issues if i.id in by_id]

    progress(
        f"Etki Analisti tamam: {len(ordered)}/{len(issues)} bulgu, "
        f"LLM güncelleme={llm_updated}, hata={llm_errors}"
    )
    logger.info(
        "Impact analyst: issues=%d impacts=%d llm_updated=%d errors=%d",
        len(issues),
        len(ordered),
        llm_updated,
        llm_errors,
    )
    return ordered
