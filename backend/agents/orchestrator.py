"""KodHekim pipeline orchestrator.

4 ajanlı pipeline:
  - static: profiler_static → impact_heuristic → chief_heuristic
  - hybrid: profiler_hybrid → impact_llm → surgeon → chief_llm
  - deep:   profiler_deep   → impact_llm → surgeon → chief_llm
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, Optional, TypedDict

from agents.chief import chief_agent_llm
from agents.chief_heuristic import chief_agent_heuristic
from agents.impact_analyst import impact_agent_llm
from agents.impact_heuristic import impact_agent_heuristic
from agents.issue import Issue
from agents.profiler import (
    profiler_agent_deep,
    profiler_agent_hybrid,
    profiler_agent_static,
)
from agents.surgeon import surgeon_agent
from agents.types import FinalReport, FixSuggestion, ImpactBreakdown
from llm.base import LLMProvider


Mode = Literal["static", "hybrid", "deep"]
ProviderName = Literal["cerebras", "gemini"]


@dataclass
class Event:
    type: str
    data: dict = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace(
                "+00:00", "Z"
            )

    def to_dict(self) -> dict:
        return {"type": self.type, "data": self.data, "timestamp": self.timestamp}


class AnalysisState(TypedDict):
    job_id: str
    repo_path: str
    mode: Mode
    provider: str
    model_overrides: dict[str, str]
    issues: list[Issue]
    impacts: list[ImpactBreakdown]
    fixes: list[FixSuggestion]
    scanned_files: list[str]
    report: Optional[FinalReport]
    events: list[Event]


_DEFAULTS_CEREBRAS: dict[str, str] = {
    "profiler": "gpt-oss-120b",
    "impact": "gpt-oss-120b",
    "surgeon": "zai-glm-4.7",
    "chief": "qwen-3-235b-a22b-instruct-2507",
    "deep": "qwen-3-235b-a22b-instruct-2507",
}

_DEFAULTS_GEMINI: dict[str, str] = {
    "profiler": "gemini-2.5-flash",
    "impact": "gemini-2.5-flash",
    "surgeon": "gemini-2.5-pro",
    "chief": "gemini-2.5-pro",
    "deep": "gemini-2.5-pro",
}


def resolve_models(provider_name: str, overrides: Optional[dict[str, str]]) -> dict[str, str]:
    base = _DEFAULTS_CEREBRAS if provider_name == "cerebras" else _DEFAULTS_GEMINI
    return {**base, **(overrides or {})}


def run_pipeline(
    *,
    repo_path: str | Path,
    mode: Mode = "hybrid",
    provider_name: str = "cerebras",
    model_overrides: Optional[dict[str, str]] = None,
    provider: Optional[LLMProvider] = None,
    job_id: Optional[str] = None,
    event_sink: Optional[Callable[[Event], None]] = None,
) -> AnalysisState:
    job_id = job_id or str(uuid.uuid4())
    events: list[Event] = []

    def emit(type_: str, **data: Any) -> None:
        ev = Event(type=type_, data=data)
        events.append(ev)
        if event_sink:
            try:
                event_sink(ev)
            except Exception:
                pass

    state: AnalysisState = {
        "job_id": job_id,
        "repo_path": str(repo_path),
        "mode": mode,
        "provider": provider_name,
        "model_overrides": dict(model_overrides or {}),
        "issues": [],
        "impacts": [],
        "fixes": [],
        "scanned_files": [],
        "report": None,
        "events": events,
    }

    if provider is None and mode != "static":
        from llm.registry import get_provider  # noqa: WPS433

        provider = get_provider(provider_name)

    models = resolve_models(provider_name, model_overrides)

    # 1) Dr. Müfettiş — Profiler
    emit("agent_started", agent="profiler", mode=mode)
    profiler_progress = lambda m: emit("agent_progress", agent="profiler", message=m)  # noqa: E731

    if mode == "static":
        issues = profiler_agent_static(repo_path)
    elif mode == "hybrid":
        assert provider is not None
        issues = profiler_agent_hybrid(
            repo_path,
            provider=provider,
            model=models["profiler"],
            on_progress=profiler_progress,
        )
    else:
        assert provider is not None
        issues = profiler_agent_deep(
            repo_path,
            provider=provider,
            model=models["deep"],
            on_progress=profiler_progress,
        )

    state["issues"] = issues
    from analysis.file_walker import walk_files  # noqa: WPS433
    from analysis.languages import resolve_languages  # noqa: WPS433

    scan_langs = resolve_languages(repo_path)
    state["scanned_files"] = [
        f.rel_path for f in walk_files(repo_path, languages=scan_langs)
    ]
    for i in issues:
        emit("issue_found", agent="profiler", issue_id=i.id, code=i.code, severity=i.severity)
    emit("agent_done", agent="profiler", count=len(issues))

    # 2) Dr. Ölçücü — Etki Analisti
    emit("agent_started", agent="impact")
    impact_progress = lambda m: emit("agent_progress", agent="impact", message=m)  # noqa: E731

    if mode == "static":
        impacts = impact_agent_heuristic(issues)
    else:
        assert provider is not None
        impacts = impact_agent_llm(
            issues,
            provider=provider,
            model=models["impact"],
            on_progress=impact_progress,
        )

    state["impacts"] = impacts
    emit(
        "agent_progress",
        agent="impact",
        message=f"Profiler'dan {len(issues)} bulgu alındı → {len(impacts)} etki kaydı üretildi",
    )
    for x in impacts:
        emit("impact_calculated", issue_id=x.issue_id, impact_score=x.impact_score)
    emit("agent_done", agent="impact", count=len(impacts))

    # 3) Dr. Cerrah (statik mod'da atlanır)
    fixes: list[FixSuggestion] = []
    if mode != "static" and issues:
        emit("agent_started", agent="surgeon")
        surgeon_progress = lambda m: emit("agent_progress", agent="surgeon", message=m)  # noqa: E731
        impacts_by_id = {x.issue_id: x for x in impacts}
        assert provider is not None
        fixes = surgeon_agent(
            issues,
            repo_path=Path(repo_path),
            provider=provider,
            model=models["surgeon"],
            impacts=impacts_by_id,
            on_progress=surgeon_progress,
        )
        for f in fixes:
            emit(
                "fix_generated",
                issue_id=f.issue_id,
                recipe_valid=f.recipe_valid,
                risk_level=f.risk_level,
            )
        emit("agent_done", agent="surgeon", count=len(fixes))

    state["fixes"] = fixes

    # 4) Dr. Hekimbaşı
    emit("agent_started", agent="chief")

    if mode == "static":
        report = chief_agent_heuristic(issues, impacts, fixes)
    else:
        chief_progress = lambda m: emit("agent_progress", agent="chief", message=m)  # noqa: E731
        assert provider is not None
        report = chief_agent_llm(
            issues,
            impacts,
            fixes,
            provider=provider,
            model=models["chief"],
            on_progress=chief_progress,
        )

    state["report"] = report
    emit(
        "agent_done",
        agent="chief",
        overall=report.health.overall,
        issues_count=report.issues_count,
    )
    emit("all_done", job_id=job_id, mode=mode)

    return state


def state_to_json(state: AnalysisState) -> dict:
    report = state["report"]
    report_json: Optional[dict] = None
    if report is not None:
        report_json = {
            "health": asdict(report.health),
            "issues_count": report.issues_count,
            "severity_breakdown": report.severity_breakdown,
            "top_priorities": [
                {
                    "issue_id": p.issue_id,
                    "code": p.code,
                    "rationale": p.rationale,
                    "roi_score": p.roi_score,
                }
                for p in report.top_priorities
            ],
            "executive_summary": report.executive_summary,
            "roadmap": list(report.roadmap),
            "issues": list(report.issues),
            "impacts": list(report.impacts),
            "fixes": list(report.fixes),
        }
    return {
        "job_id": state["job_id"],
        "repo_path": state["repo_path"],
        "mode": state["mode"],
        "provider": state["provider"],
        "model_overrides": state["model_overrides"],
        "issues": [i.to_dict() for i in state["issues"]],
        "impacts": [x.to_dict() for x in state["impacts"]],
        "fixes": [f.to_dict() for f in state["fixes"]],
        "scanned_files": list(state.get("scanned_files") or []),
        "report": report_json,
        "events": [e.to_dict() for e in state["events"]],
    }


def _cli_event_printer(ev: Event) -> None:
    payload = json.dumps(ev.data, ensure_ascii=False, default=str)
    if len(payload) > 200:
        payload = payload[:200] + "…"
    print(f"[{ev.type}] {payload}", flush=True)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kodhekim-orchestrator",
        description="KodHekim analiz pipeline'ı (statik / hibrit / derin).",
    )
    parser.add_argument("repo_path", help="Analiz edilecek yerel repo dizini")
    parser.add_argument(
        "--mode", choices=("static", "hybrid", "deep"), default="static"
    )
    parser.add_argument(
        "--provider", choices=("cerebras", "gemini"), default="cerebras"
    )
    parser.add_argument(
        "--out",
        default="result.json",
        help="Sonuç JSON'unun yazılacağı yol (default: result.json)",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Event log'unu sustur"
    )
    args = parser.parse_args(argv)

    sink = None if args.quiet else _cli_event_printer

    state = run_pipeline(
        repo_path=args.repo_path,
        mode=args.mode,
        provider_name=args.provider,
        event_sink=sink,
    )

    out_path = Path(args.out)
    out_path.write_text(
        json.dumps(state_to_json(state), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nSonuç: {out_path.resolve()}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
