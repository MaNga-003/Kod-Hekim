"""Profiler ajanı (Dr. Müfettiş).

Hibrit mod: statik tarayıcı + LLM confirm.
Statik mod: yalnızca statik tarayıcı (LLM atlanır) — bkz. `profiler_agent_static`.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional

from analysis.ast_parser import ParsedFile, parse_file
from analysis.file_walker import walk_files
from analysis.scan import scan_repo
from analysis.static_rules.base import IssueCandidate
from llm.base import LLMError, LLMProvider

from agents.issue import Issue, assign_ids, from_candidate


# JSON schema — LLM'den dönecek structured output
CONFIRM_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "confirmed_issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "confirmed": {"type": "boolean"},
                    "severity": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "llm_confidence": {"type": "number"},
                    "explanation": {"type": "string"},
                    "reason": {"type": ["string", "null"]},
                },
                "required": ["id", "confirmed", "llm_confidence"],
            },
        }
    },
    "required": ["confirmed_issues"],
}


# Tek bir LLM çağrısına gönderilecek max aday sayısı (token bütçesi koruma)
MAX_CANDIDATES_PER_CALL = 10


# ---------------------------------------------------------------------------
# Statik mod
# ---------------------------------------------------------------------------


def profiler_agent_static(repo_path: Path | str) -> list[Issue]:
    """LLM atlanır — tüm statik bulgular doğrudan Issue olur."""
    report = scan_repo(repo_path)
    out: list[Issue] = []
    for issue_id, cand in assign_ids(report.issues):
        out.append(from_candidate(issue_id, cand, llm_confidence=None))
    return out


# ---------------------------------------------------------------------------
# Hibrit mod
# ---------------------------------------------------------------------------


def _load_prompt_template() -> str:
    here = Path(__file__).resolve().parent.parent
    return (here / "prompts" / "profiler_confirm.md").read_text(encoding="utf-8")


def _read_file_source(rel_path: str, repo_path: Path) -> str:
    """Aday sorunun referans verdiği dosyanın kaynağını oku (line cap'lı)."""
    abs_path = (repo_path / rel_path).resolve()
    try:
        text = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    # LLM context tasarrufu: 600 satır cap
    lines = text.splitlines()
    if len(lines) > 600:
        lines = lines[:600] + [f"# ... ({len(lines) - 600} satır daha)"]
    return "\n".join(lines)


def _format_candidate_block(items: list[tuple[str, IssueCandidate]]) -> str:
    chunks: list[str] = []
    for issue_id, c in items:
        chunks.append(
            f"### {issue_id}\n"
            f"- code: {c.code}\n"
            f"- category: {c.category}\n"
            f"- severity (statik): {c.severity}\n"
            f"- static_confidence: {round(c.static_confidence, 2)}\n"
            f"- line: {c.line_start}-{c.line_end}\n"
            f"- snippet:\n```python\n{c.snippet}\n```\n"
            f"- statik açıklama: {c.explanation}\n"
        )
    return "\n".join(chunks)


def _chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def profiler_agent_hybrid(
    repo_path: Path | str,
    *,
    provider: LLMProvider,
    model: str,
    on_progress: Optional[Callable[[str], None]] = None,
) -> list[Issue]:
    """Statik tarayıcı + LLM confirm. Hibrit modun varsayılan akışı."""
    repo_path = Path(repo_path).resolve()
    progress = on_progress or (lambda msg: None)

    progress("Statik tarayıcı çalışıyor…")
    report = scan_repo(repo_path)
    progress(f"{len(report.issues)} aday sorun bulundu, LLM confirm başlıyor…")

    if not report.issues:
        return []

    id_to_cand: dict[str, IssueCandidate] = {}
    by_file: dict[str, list[tuple[str, IssueCandidate]]] = defaultdict(list)
    for issue_id, cand in assign_ids(report.issues):
        id_to_cand[issue_id] = cand
        by_file[cand.file].append((issue_id, cand))

    template = _load_prompt_template()

    confirmed_ids: set[str] = set()
    verdicts: dict[str, dict] = {}

    for file_path, items in by_file.items():
        source = _read_file_source(file_path, repo_path)
        for chunk in _chunk(items, MAX_CANDIDATES_PER_CALL):
            block = _format_candidate_block(chunk)
            prompt = (
                template.replace("{file_path}", file_path)
                .replace("{file_source}", source or "(kaynak okunamadı)")
                .replace("{candidates_block}", block)
            )

            progress(f"LLM confirm: {file_path} ({len(chunk)} aday)")
            try:
                resp = provider.complete(
                    prompt,
                    model=model,
                    json_schema=CONFIRM_SCHEMA,
                    temperature=0.1,
                    max_tokens=4096,
                )
            except LLMError as e:
                # Bu chunk için LLM patladı — adayları statik confidence ile geçir
                progress(f"  ! LLM hata: {e}; aday severity'leriyle korunuyor.")
                for issue_id, _ in chunk:
                    confirmed_ids.add(issue_id)
                continue

            parsed = resp.get("json") or {}
            for v in parsed.get("confirmed_issues", []):
                issue_id = v.get("id")
                if issue_id not in id_to_cand:
                    continue  # uydurma id'leri yoksay
                verdicts[issue_id] = v
                if v.get("confirmed"):
                    confirmed_ids.add(issue_id)

            # Verdict gelmeyen adaylar — LLM verdict atladıysa default olarak tut.
            for issue_id, _ in chunk:
                if issue_id not in verdicts:
                    confirmed_ids.add(issue_id)

    # Final Issue listesi
    out: list[Issue] = []
    for issue_id, cand in assign_ids(report.issues):
        if issue_id not in confirmed_ids:
            continue
        v = verdicts.get(issue_id, {})
        sev = v.get("severity") if v.get("severity") in {"high", "medium", "low"} else None
        out.append(
            from_candidate(
                issue_id,
                cand,
                llm_confidence=v.get("llm_confidence"),
                severity_override=sev,  # type: ignore[arg-type]
                explanation_override=v.get("explanation") or None,
            )
        )

    progress(f"Profiler tamam: {len(out)}/{len(report.issues)} confirmed")
    return out
