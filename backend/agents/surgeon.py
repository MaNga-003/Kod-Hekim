"""Cerrah ajanı (Dr. Cerrah) — batch sözel çözüm reçetesi (hızlı pipeline)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from analysis.fix_recipe_validator import validate_recipe
from llm.base import LLMError, LLMProvider

from agents.issue import Issue
from agents.surgeon_heuristic import heuristic_fix
from agents.pipeline_limits import MAX_SURGEON_FIXES, SURGEON_BATCH_SIZE
from agents.types import FixSuggestion, ImpactBreakdown

_FIX_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "issue_id": {"type": "string"},
        "fix_instruction_tr": {"type": "string"},
        "risk_level": {"type": "integer", "minimum": 1, "maximum": 5},
        "test_suggestion": {"type": "string"},
        "improvement_estimate": {"type": "string"},
    },
    "required": [
        "issue_id",
        "fix_instruction_tr",
        "risk_level",
        "test_suggestion",
        "improvement_estimate",
    ],
}

SURGEON_BATCH_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "fixes": {
            "type": "array",
            "items": _FIX_ITEM_SCHEMA,
        }
    },
    "required": ["fixes"],
}

WINDOW_LINES = 20


def _load_few_shot_block() -> str:
    import json as _json

    examples_dir = Path(__file__).resolve().parent.parent / "prompts" / "examples"
    if not examples_dir.exists():
        return ""
    parts: list[str] = []
    for path in sorted(examples_dir.glob("surgeon_*.json"))[:2]:
        try:
            data = _json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        issue = data.get("issue", {})
        response = data.get("response", {})
        recipe = response.get("fix_instruction_tr", "")
        parts.append(
            f"### Örnek: {issue.get('code', '?')}\n"
            f"```python\n{data.get('code_window', '')[:800]}\n```\n"
            f"Reçete:\n{recipe[:1200]}"
        )
    return "\n\n".join(parts)


def _code_window(repo_path: Path, rel_file: str, line_start: int, line_end: int) -> str:
    abs_path = (repo_path / rel_file).resolve()
    try:
        text = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(kaynak okunamadı)"
    lines = text.splitlines()
    lo = max(1, line_start - WINDOW_LINES)
    hi = min(len(lines), line_end + WINDOW_LINES)
    return f"# lines {lo}-{hi}\n" + "\n".join(lines[lo - 1 : hi])


def _chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def select_issues_for_surgeon(
    issues: list[Issue],
    impacts: dict[str, ImpactBreakdown],
    *,
    max_fixes: int | None = None,
) -> tuple[list[Issue], list[Issue]]:
    """En yüksek etki skorlu bulguları Cerrah için seç."""
    cap = max_fixes if max_fixes is not None else MAX_SURGEON_FIXES
    if len(issues) <= cap:
        return issues, []

    sev_rank = {"high": 0, "medium": 1, "low": 2}

    def sort_key(iss: Issue) -> tuple:
        imp = impacts.get(iss.id)
        score = imp.impact_score if imp else 0
        return (sev_rank.get(iss.severity, 9), -score)

    sorted_issues = sorted(issues, key=sort_key)
    return sorted_issues[:cap], sorted_issues[cap:]


def _build_batch_prompt(
    batch: list[Issue],
    repo_path: Path,
    impacts: dict[str, ImpactBreakdown],
) -> str:
    blocks: list[str] = []
    for issue in batch:
        impact = impacts.get(issue.id)
        window = _code_window(repo_path, issue.file, issue.line_start, issue.line_end)
        blocks.append(
            f"## {issue.id} — {issue.code} ({issue.severity})\n"
            f"file: {issue.file}:{issue.line_start}-{issue.line_end}\n"
            f"explanation: {issue.explanation}\n"
            f"impact: {impact.explanation_tr if impact else 'n/a'}\n"
            f"```\n{window[:2500]}\n```\n"
        )
    issues_text = "\n".join(blocks)
    few_shot = _load_few_shot_block()
    return (
        "Sen kıdemli bir yazılım cerrahısın. Aşağıdaki her bulgu için geliştiriciye "
        "Türkçe, adımsal ve sözel bir çözüm reçetesi yaz.\n"
        "Kod patch'i veya unified diff üretme — yalnızca mantıksal yönergeler.\n"
        f"Toplam {len(batch)} bulgu. JSON anahtarı: fixes "
        "(her öğede issue_id, fix_instruction_tr, risk_level, test_suggestion, "
        "improvement_estimate).\n\n"
        f"{few_shot}\n\n"
        f"{issues_text}"
    )


def surgeon_agent(
    issues: list[Issue],
    *,
    repo_path: Path | str,
    provider: LLMProvider,
    model: str,
    impacts: Optional[dict[str, ImpactBreakdown]] = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> list[FixSuggestion]:
    """Batch LLM: SURGEON_BATCH_SIZE bulgu / çağrı."""
    progress = on_progress or (lambda msg: None)
    repo_path = Path(repo_path).resolve()
    impacts = impacts or {}

    to_fix, skipped = select_issues_for_surgeon(issues, impacts)
    if skipped:
        progress(
            f"Cerrah: en kritik {len(to_fix)} bulgu için reçete "
            f"(MAX_SURGEON_FIXES={MAX_SURGEON_FIXES}, {len(skipped)} atlandı)"
        )

    out: list[FixSuggestion] = []

    for iss in skipped:
        out.append(
            FixSuggestion(
                issue_id=iss.id,
                fix_instruction_tr=(
                    "(öncelik sınırı — en kritik bulgular için reçete üretildi)"
                ),
                risk_level=2,
                test_suggestion="Manuel inceleme önerilir.",
                improvement_estimate="—",
                recipe_valid=False,
            )
        )

    batch_size = max(1, SURGEON_BATCH_SIZE)
    for batch in _chunk(to_fix, batch_size):
        ids = ", ".join(i.id for i in batch)
        progress(f"Cerrah batch ({len(batch)} bulgu): {ids}")
        prompt = _build_batch_prompt(batch, repo_path, impacts)

        try:
            resp = provider.complete(
                prompt,
                model=model,
                json_schema=SURGEON_BATCH_SCHEMA,
                temperature=0.25,
                max_tokens=4096,
            )
        except LLMError as e:
            progress(f"  ! Cerrah batch hata: {e}; heuristic reçete kullanılıyor.")
            for issue in batch:
                out.append(heuristic_fix(issue, impacts.get(issue.id)))
            continue

        by_id = {v.get("issue_id"): v for v in (resp.get("json") or {}).get("fixes", [])}
        for issue in batch:
            data = by_id.get(issue.id)
            if not data:
                out.append(heuristic_fix(issue, impacts.get(issue.id)))
                continue
            recipe = str(data.get("fix_instruction_tr") or "").strip()
            valid, _ = validate_recipe(recipe)
            if valid:
                out.append(
                    FixSuggestion(
                        issue_id=issue.id,
                        fix_instruction_tr=recipe,
                        risk_level=int(data.get("risk_level", 3)),
                        test_suggestion=str(data.get("test_suggestion", "")),
                        improvement_estimate=str(data.get("improvement_estimate", "")),
                        recipe_valid=True,
                    )
                )
            else:
                out.append(heuristic_fix(issue, impacts.get(issue.id)))

    return out


def _failed_fix(issue_id: str) -> FixSuggestion:
    return FixSuggestion(
        issue_id=issue_id,
        fix_instruction_tr="(reçete üretilemedi — manuel inceleme gerekir)",
        risk_level=3,
        test_suggestion="Manuel inceleme.",
        improvement_estimate="bilinmiyor",
        recipe_valid=False,
    )
