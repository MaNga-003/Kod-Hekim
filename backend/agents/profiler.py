"""Profiler ajanı (Dr. Müfettiş).

Hibrit mod: statik tarayıcı + LLM confirm.
Statik mod: yalnızca statik tarayıcı (LLM atlanır) — bkz. `profiler_agent_static`.
Derin mod: AST özeti + tam kod LLM'e direkt, kendisi 23 örüntü + OTHER_* tespit eder.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional

from analysis.ast_parser import ParsedFile, parse_file
from analysis.ast_summary import (
    estimate_tokens,
    pick_full_inclusion_files,
    summarize_repo,
)
from analysis.file_walker import walk_files
from analysis.languages import resolve_languages
from analysis.scan import scan_repo
from analysis.static_rules.base import IssueCandidate
from llm.base import LLMError, LLMProvider

from agents.issue import Issue, assign_ids, from_candidate
from agents.pipeline_limits import MAX_PROFILER_LLM_CANDIDATES


logger = logging.getLogger(__name__)

# Statik güven bu eşiğin üstündeyse LLM reddi uygulanmaz (agresif eleme engeli).
STATIC_KEEP_THRESHOLD = 0.55
# Düşük statik güvenli adayları elemek için LLM'in yüksek eminlik + gerekçe şartı.
LLM_REJECT_CONFIDENCE = 0.85


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
                    "reason": {"type": "string"},
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
    langs = resolve_languages(repo_path)
    report = scan_repo(repo_path, languages=langs)
    if report.files_discovered == 0:
        return []
    lang_summary = ", ".join(
        f"{lang}={report.language_files.get(lang, 0)}"
        for lang in report.languages
    )
    # Progress için log (orchestrator SSE'ye taşır)
    import logging

    logging.getLogger(__name__).info(
        "Statik tarama: %s dosya, diller [%s], %d bulgu",
        report.files_scanned,
        lang_summary,
        len(report.issues),
    )
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


def _should_keep_candidate(
    cand: IssueCandidate,
    verdict: dict | None,
) -> tuple[bool, str]:
    """LLM verdict sonrası aday korunmalı mı?

    Varsayılan: koru. Yalnızca düşük statik güven + yüksek LLM red güveni +
    dolu ``reason`` varsa ele.
    """
    if not verdict:
        return True, "verdict yok — statik aday korundu"

    if verdict.get("confirmed") is True:
        return True, "LLM onayladı"

    llm_conf = float(verdict.get("llm_confidence") or 0)
    reason = (verdict.get("reason") or "").strip()

    if cand.static_confidence >= STATIC_KEEP_THRESHOLD:
        return (
            True,
            f"statik güven {cand.static_confidence:.2f} ≥ {STATIC_KEEP_THRESHOLD} — red yok sayıldı",
        )

    if llm_conf >= LLM_REJECT_CONFIDENCE and reason:
        return False, f"LLM red (conf={llm_conf:.2f}): {reason[:80]}"

    return True, f"belirsiz red (conf={llm_conf:.2f}) — statik aday korundu"


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
    langs = resolve_languages(repo_path)
    report = scan_repo(repo_path, languages=langs)
    progress(
        f"Diller: {', '.join(report.languages)} — "
        f"{report.files_scanned}/{report.files_discovered} dosya "
        f"({', '.join(f'{k}={v}' for k, v in sorted(report.language_files.items()))}) — "
        f"{len(report.issues)} aday sorun — LLM confirm başlıyor…"
    )

    if report.files_discovered == 0:
        progress("⚠ Uyarı: Repoda .py/.js/.jsx/.ts/.tsx kaynak dosyası bulunamadı.")
        return []

    if not report.issues:
        return []

    all_pairs = list(assign_ids(report.issues))
    sev_rank = {"high": 0, "medium": 1, "low": 2}
    all_pairs.sort(
        key=lambda p: (sev_rank.get(p[1].severity, 9), -p[1].static_confidence)
    )

    llm_cap = MAX_PROFILER_LLM_CANDIDATES
    llm_pairs = all_pairs[:llm_cap]
    auto_pairs = all_pairs[llm_cap:]

    if auto_pairs:
        progress(
            f"Profiler: {len(llm_pairs)} bulgu LLM confirm, "
            f"{len(auto_pairs)} yüksek güven statik geçiş (hız)"
        )

    id_to_cand: dict[str, IssueCandidate] = {i: c for i, c in all_pairs}
    by_file: dict[str, list[tuple[str, IssueCandidate]]] = defaultdict(list)
    for issue_id, cand in llm_pairs:
        by_file[cand.file].append((issue_id, cand))

    template = _load_prompt_template()

    confirmed_ids: set[str] = set()
    verdicts: dict[str, dict] = {}
    rejected_log: list[str] = []

    for issue_id, cand in auto_pairs:
        if cand.static_confidence >= STATIC_KEEP_THRESHOLD:
            confirmed_ids.add(issue_id)

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
                progress(f"  ! LLM hata ({type(e).__name__}): {e}; chunk statik olarak korunuyor.")
                logger.warning("Profiler LLM chunk failed: %s", e)
                for issue_id, _ in chunk:
                    confirmed_ids.add(issue_id)
                continue

            _text = (resp.get("text") or "").strip()
            if _text:
                progress(f"💭 {_text[:120]}")
            parsed = resp.get("json") or {}
            chunk_verdicts: dict[str, dict] = {}
            for v in parsed.get("confirmed_issues", []):
                issue_id = v.get("id")
                if issue_id not in id_to_cand:
                    continue
                chunk_verdicts[issue_id] = v
                verdicts[issue_id] = v

            for issue_id, cand in chunk:
                v = chunk_verdicts.get(issue_id)
                keep, note = _should_keep_candidate(cand, v)
                if keep:
                    confirmed_ids.add(issue_id)
                    if v and v.get("confirmed") is False:
                        progress(f"  ↳ {issue_id} korundu: {note}")
                        logger.info("Profiler kept despite LLM reject: %s — %s", issue_id, note)
                else:
                    rejected_log.append(f"{issue_id}: {note}")
                    progress(f"  ✗ {issue_id} elendi: {note}")
                    logger.info("Profiler rejected: %s — %s", issue_id, note)

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

    if report.issues and not out:
        progress(
            f"LLM filtresi sonrası 0 bulgu — statik güven ≥{STATIC_KEEP_THRESHOLD} adaylar geri yükleniyor."
        )
        for issue_id, cand in assign_ids(report.issues):
            if cand.static_confidence >= STATIC_KEEP_THRESHOLD:
                out.append(from_candidate(issue_id, cand, llm_confidence=None))

    if report.issues and not out:
        progress("Son çare: tüm statik tarama bulguları korunuyor.")
        for issue_id, cand in assign_ids(report.issues):
            out.append(from_candidate(issue_id, cand, llm_confidence=None))

    if rejected_log:
        progress(
            f"Profiler: {len(rejected_log)} düşük-güven aday elendi, "
            f"{len(out)}/{len(report.issues)} rapora girdi."
        )
    progress(f"Profiler tamam: {len(out)}/{len(report.issues)} confirmed")
    logger.info(
        "Profiler hybrid: static=%d confirmed=%d rejected=%d",
        len(report.issues),
        len(out),
        len(rejected_log),
    )
    return out


# ---------------------------------------------------------------------------
# Derin mod (LLM-Direct)
# ---------------------------------------------------------------------------


DEEP_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": ["performance", "memory", "reliability", "security", "quality"],
                    },
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "file": {"type": "string"},
                    "line_start": {"type": "integer", "minimum": 1},
                    "line_end": {"type": "integer", "minimum": 1},
                    "snippet": {"type": "string"},
                    "explanation": {"type": "string"},
                },
                "required": [
                    "code",
                    "category",
                    "severity",
                    "file",
                    "line_start",
                    "line_end",
                    "explanation",
                ],
            },
        }
    },
    "required": ["issues"],
}


# Token tahmini → karakter bütçesi (≈ 4 char/token, %20 emniyet payı)
DEFAULT_DEEP_TOKEN_BUDGET = 800_000


def _load_deep_prompt() -> str:
    here = Path(__file__).resolve().parent.parent
    return (here / "prompts" / "deep_mode.md").read_text(encoding="utf-8")


def _coerce_severity(value: str) -> str:
    v = (value or "").lower()
    return v if v in {"high", "medium", "low"} else "medium"


def _coerce_category(value: str) -> str:
    v = (value or "").lower()
    return v if v in {"performance", "memory", "reliability", "security", "quality"} else "quality"


def profiler_agent_deep(
    repo_path: Path | str,
    *,
    provider: LLMProvider,
    model: str,
    on_progress: Optional[Callable[[str], None]] = None,
    max_tokens_budget: int = DEFAULT_DEEP_TOKEN_BUDGET,
) -> list[Issue]:
    """Tek bir büyük LLM çağrısıyla repo'yu analiz eder.

    1. `summarize_repo` → outline (her dosya için imza/class özeti).
    2. Token bütçesine sığacak şekilde **tam kod** dosyalarını seç
       (entry point > __main__ > küçük dosyalar).
    3. Tek prompt → JSON schema'lı LLM çağrısı.
    4. Issue listesi (ID'leri burada üretiriz; statik confidence yok).
    """
    repo_root = Path(repo_path).resolve()
    progress = on_progress or (lambda msg: None)

    progress("Derin mod: repo özetleniyor…")
    summary = summarize_repo(repo_root)

    outline = summary.to_outline()
    template = _load_deep_prompt()
    prompt_overhead = estimate_tokens(template) + estimate_tokens(outline)

    # Geriye kalan token bütçesini full file inclusion'a ayır
    remaining_tokens = max(0, max_tokens_budget - prompt_overhead - 4_000)  # 4K çıktı payı
    char_budget = remaining_tokens * 4

    def _load(rel_path: str) -> str:
        abs_path = (repo_root / rel_path).resolve()
        return abs_path.read_text(encoding="utf-8", errors="replace")

    selected = pick_full_inclusion_files(summary, _load, char_budget=char_budget)
    progress(
        f"Derin mod: {len(selected)} dosya tam, {len(summary.files) - len(selected)} dosya sadece özet"
    )

    full_files_block = (
        "\n\n".join(
            f"### {fp} ###\n```python\n{src}\n```" for fp, src in selected
        )
        or "(tam dosya seçilmedi — sadece özet gönderildi)"
    )

    prompt = template.replace("{repo_outline}", outline).replace(
        "{full_files}", full_files_block
    )

    progress("Derin mod: LLM çağrısı…")
    try:
        resp = provider.complete(
            prompt,
            model=model,
            json_schema=DEEP_SCHEMA,
            temperature=0.4,
            max_tokens=4096,
        )
    except LLMError as e:
        progress(f"Derin mod: LLM hata ({type(e).__name__}): {e} — statik taramaya düşülüyor.")
        logger.warning("Deep profiler LLM failed, falling back to static: %s", e)
        return profiler_agent_static(repo_root)

    data = resp.get("json") or {}
    raw_issues = data.get("issues") or []
    progress(f"Derin mod: {len(raw_issues)} bulgu döndü")

    # Issue listesini stabil id'lerle üret (severity sırasına göre)
    sev_rank = {"high": 0, "medium": 1, "low": 2}
    sorted_raw = sorted(
        raw_issues,
        key=lambda r: (
            sev_rank.get(_coerce_severity(r.get("severity", "")), 9),
            str(r.get("file", "")),
            int(r.get("line_start") or 0),
            str(r.get("code", "")),
        ),
    )

    out: list[Issue] = []
    for idx, r in enumerate(sorted_raw):
        code = str(r.get("code") or "OTHER_unknown").strip()
        category = _coerce_category(str(r.get("category", "")))
        severity = _coerce_severity(str(r.get("severity", "")))
        file = str(r.get("file") or "?")
        try:
            line_start = max(1, int(r.get("line_start") or 1))
            line_end = max(line_start, int(r.get("line_end") or line_start))
        except (TypeError, ValueError):
            line_start = line_end = 1
        out.append(
            Issue(
                id=f"issue-{idx + 1:03d}",
                code=code,
                category=category,  # type: ignore[arg-type]
                severity=severity,  # type: ignore[arg-type]
                file=file,
                line_start=line_start,
                line_end=line_end,
                snippet=str(r.get("snippet") or ""),
                explanation=str(r.get("explanation") or ""),
                static_confidence=0.0,  # statik kural yok
                llm_confidence=1.0,  # LLM tek başına raporladı
                extra={"deep_mode": True},
            )
        )

    return out
