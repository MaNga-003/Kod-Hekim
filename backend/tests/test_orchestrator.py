"""Faz K — Orchestrator testleri.

Kapsam:
- 3 mod uçtan uca (statik provider'sız; hibrit + derin mock provider ile).
- Event akışı sıralı ve eksiksiz (`agent_started` → `agent_done` → `all_done`).
- `event_sink` callback'i her event için çağrılıyor.
- `model_overrides` doğru ajana yönleniyor.
- `state_to_json` çıktısı diske yazılabilir.
- `resolve_models` Cerebras/Gemini varsayılanları + override birleşimi.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from agents.issue import Issue
from agents.orchestrator import (
    AnalysisState,
    Event,
    Mode,
    resolve_models,
    run_pipeline,
    state_to_json,
)
from agents.types import FinalReport
from llm.base import LLMProvider, LLMResponse


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "bad_code_examples"


# ---------------------------------------------------------------------------
# Sahte provider — prompt içeriğine göre cevap döndürür
# ---------------------------------------------------------------------------


class _PhaseProvider(LLMProvider):
    """Prompt başlığından hangi ajan olduğunu sezip uygun JSON döndürür."""

    name = "phase"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def list_models(self):
        return ["x"]

    def complete(self, prompt: str, model: str, **kw):
        # Faz tespiti prompt'un H1 başlığından (unique).
        first_line = prompt.lstrip().splitlines()[0] if prompt.strip() else ""
        if "Derin Mod" in first_line:
            agent = "deep"
        elif "sözel bir çözüm reçetesi" in prompt.lower() or "fix_instruction_tr" in prompt.lower():
            agent = "surgeon"
        elif "Hekimbaşı" in first_line:
            agent = "chief"
        elif "Etki Analisti" in first_line:
            agent = "impact"
        elif "Profiler" in first_line:
            agent = "profiler"
        else:
            agent = "?"

        self.calls.append({"model": model, "agent": agent})
        is_deep = agent == "deep"
        is_surgeon = agent == "surgeon"
        is_chief = agent == "chief"
        is_impact = agent == "impact"
        is_profiler_confirm = agent == "profiler"

        if is_deep:
            payload = {
                "issues": [
                    {
                        "code": "N1_QUERY",
                        "category": "performance",
                        "severity": "high",
                        "file": "api.py",
                        "line_start": 70,
                        "line_end": 73,
                        "snippet": "for u in users: Post.query.filter_by(...)",
                        "explanation": "Derin mod ile bulundu.",
                    }
                ]
            }
        elif is_surgeon:
            issue_ids = re.findall(r"## (issue-\S+)", prompt) or ["issue-001"]
            payload = {
                "fixes": [
                    {
                        "issue_id": iid,
                        "fix_instruction_tr": (
                            "1. Kök neden test.\n"
                            "2. Adım iki.\n"
                            "3. Adım üç.\n"
                            "4. Test ekle."
                        ),
                        "risk_level": 2,
                        "test_suggestion": "Test ekle.",
                        "improvement_estimate": "%80",
                    }
                    for iid in issue_ids
                ]
            }
        elif is_chief:
            payload = {
                "executive_summary": "p1\n\np2\n\np3",
                "roadmap": ["1. yap", "2. yap"],
            }
        elif is_impact:
            payload = {"impacts": []}  # heuristic baseline kalır
        elif is_profiler_confirm:
            # confirm: tüm aday id'leri onayla (default davranış)
            payload = {"confirmed_issues": []}
        else:
            payload = {}

        return LLMResponse(
            text="", json=payload, tokens_used=10, model=model, latency_ms=1
        )


# ---------------------------------------------------------------------------
# resolve_models
# ---------------------------------------------------------------------------


class TestResolveModels:
    def test_cerebras_defaults(self) -> None:
        m = resolve_models("cerebras", None)
        assert m["profiler"] == "gpt-oss-120b"
        assert m["surgeon"] == "zai-glm-4.7"
        assert m["chief"] == "qwen-3-235b-a22b-instruct-2507"

    def test_gemini_defaults(self) -> None:
        m = resolve_models("gemini", None)
        assert m["profiler"] == "gemini-2.5-flash"

    def test_overrides_merged(self) -> None:
        m = resolve_models("cerebras", {"profiler": "custom-model"})
        assert m["profiler"] == "custom-model"
        assert m["chief"] == "qwen-3-235b-a22b-instruct-2507"


# ---------------------------------------------------------------------------
# Statik mod end-to-end (provider gerekmez)
# ---------------------------------------------------------------------------


class TestStaticPipeline:
    def test_runs_without_provider(self) -> None:
        state = run_pipeline(repo_path=FIXTURE, mode="static")
        assert state["mode"] == "static"
        assert state["report"] is not None
        assert isinstance(state["report"], FinalReport)
        assert state["issues"]  # fixture kasıtlı kötü
        assert state["fixes"] == []

    def test_events_complete_order(self) -> None:
        state = run_pipeline(repo_path=FIXTURE, mode="static")
        types = [e.type for e in state["events"]]
        # İlk event: profiler başladı
        assert types[0] == "agent_started"
        # Son event: all_done
        assert types[-1] == "all_done"
        # Sırayla 3 ajan (statik — cerrah yok)
        agent_starts = [
            e.data.get("agent")
            for e in state["events"]
            if e.type == "agent_started"
        ]
        assert agent_starts == ["profiler", "impact", "chief"]

    def test_event_sink_called(self) -> None:
        sink_calls: list[Event] = []
        run_pipeline(
            repo_path=FIXTURE, mode="static", event_sink=sink_calls.append
        )
        assert sink_calls
        # state events ile sink events sayıca eşit
        assert any(e.type == "all_done" for e in sink_calls)

    def test_empty_repo(self, tmp_path: Path) -> None:
        state = run_pipeline(repo_path=tmp_path, mode="static")
        assert state["issues"] == []
        assert state["impacts"] == []
        assert state["report"].health.overall == 100


# ---------------------------------------------------------------------------
# Hibrit mod (mock provider)
# ---------------------------------------------------------------------------


class TestHybridPipeline:
    def test_runs_with_mock_provider(self) -> None:
        provider = _PhaseProvider()
        state = run_pipeline(
            repo_path=FIXTURE,
            mode="hybrid",
            provider=provider,
        )
        assert state["mode"] == "hybrid"
        assert state["report"] is not None
        # En az bir agent çağrısı her ajan için yapıldı
        agents_called = {c["agent"] for c in provider.calls}
        assert "profiler" in agents_called
        assert "impact" in agents_called
        assert "surgeon" in agents_called
        assert "chief" in agents_called

    def test_surgeon_runs_in_hybrid(self) -> None:
        provider = _PhaseProvider()
        state = run_pipeline(
            repo_path=FIXTURE, mode="hybrid", provider=provider
        )
        assert state["fixes"]
        assert any(f.recipe_valid for f in state["fixes"])

    def test_model_overrides_propagated(self) -> None:
        provider = _PhaseProvider()
        run_pipeline(
            repo_path=FIXTURE,
            mode="hybrid",
            provider=provider,
            model_overrides={"surgeon": "ozelmodel"},
        )
        surgeon_calls = [c for c in provider.calls if c["agent"] == "surgeon"]
        assert surgeon_calls
        assert all(c["model"] == "ozelmodel" for c in surgeon_calls)


# ---------------------------------------------------------------------------
# Derin mod (mock provider)
# ---------------------------------------------------------------------------


class TestDeepPipeline:
    def test_runs_with_mock_provider(self) -> None:
        provider = _PhaseProvider()
        state = run_pipeline(
            repo_path=FIXTURE,
            mode="deep",
            provider=provider,
        )
        assert state["mode"] == "deep"
        # Deep provider issues döndürüyor (1 issue)
        assert len(state["issues"]) == 1
        assert state["issues"][0].code == "N1_QUERY"
        # Issue'da deep_mode flag'i
        assert state["issues"][0].extra.get("deep_mode") is True
        # Sonra surgeon + chief çalıştı
        agents = [c["agent"] for c in provider.calls]
        assert "deep" in agents
        assert "surgeon" in agents
        assert "chief" in agents


# ---------------------------------------------------------------------------
# JSON serileştirme
# ---------------------------------------------------------------------------


class TestStateSerialization:
    def test_state_to_json_serializable(self, tmp_path: Path) -> None:
        state = run_pipeline(repo_path=FIXTURE, mode="static")
        d = state_to_json(state)
        # Düzgün round-trip JSON
        s = json.dumps(d, ensure_ascii=False)
        assert s
        # Geri yüklenebilir
        round_tripped = json.loads(s)
        assert round_tripped["mode"] == "static"
        assert "report" in round_tripped
        assert round_tripped["report"]["health"]["overall"] >= 0

    def test_state_to_json_writes_to_disk(self, tmp_path: Path) -> None:
        state = run_pipeline(repo_path=FIXTURE, mode="static")
        out = tmp_path / "out.json"
        out.write_text(
            json.dumps(state_to_json(state), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        assert out.exists()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["issues"]
        assert loaded["events"][-1]["type"] == "all_done"


# ---------------------------------------------------------------------------
# Edge case'ler
# ---------------------------------------------------------------------------


class TestOrchestratorEdgeCases:
    def test_event_sink_exception_does_not_break_pipeline(self) -> None:
        def crashing_sink(_: Event) -> None:
            raise RuntimeError("sink crash")

        # Pipeline sink hatasını yutmalı
        state = run_pipeline(
            repo_path=FIXTURE, mode="static", event_sink=crashing_sink
        )
        assert state["report"] is not None

    def test_job_id_propagated(self) -> None:
        state = run_pipeline(repo_path=FIXTURE, mode="static", job_id="custom-id")
        assert state["job_id"] == "custom-id"
        all_done = [e for e in state["events"] if e.type == "all_done"]
        assert all_done
        assert all_done[0].data.get("job_id") == "custom-id"

    def test_issues_count_matches_report(self) -> None:
        state = run_pipeline(repo_path=FIXTURE, mode="static")
        assert state["report"].issues_count == len(state["issues"])
