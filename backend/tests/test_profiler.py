"""Profiler ajanı testleri — LLM provider mock'lu, statik scan gerçek."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

from agents.profiler import (
    MAX_CANDIDATES_PER_CALL,
    profiler_agent_hybrid,
    profiler_agent_static,
)
from llm.base import LLMError, LLMProvider, LLMResponse


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "bad_code_examples"


class FakeProvider(LLMProvider):
    """Test için her çağrıda verilen verdict'i döndürür."""

    name = "fake"

    def __init__(self, verdict_factory):
        self.verdict_factory = verdict_factory
        self.calls: list[dict] = []

    def list_models(self) -> list[str]:
        return ["fake-model"]

    def complete(
        self,
        prompt: str,
        model: str,
        *,
        temperature: float = 0.2,
        json_schema: Optional[dict] = None,
        max_tokens: int = 4096,
        system: Optional[str] = None,
    ) -> LLMResponse:
        verdict = self.verdict_factory(prompt)
        self.calls.append({"prompt": prompt, "verdict": verdict})
        return LLMResponse(
            text="",
            json={"confirmed_issues": verdict},
            tokens_used=100,
            model=model,
            latency_ms=10,
        )


def _ids_in_prompt(prompt: str) -> list[str]:
    """Prompt içindeki '### issue-NNN' başlıklarını çıkar."""
    import re

    return re.findall(r"### (issue-\d+)", prompt)


# ---------------------------------------------------------------------------
# profiler_agent_static
# ---------------------------------------------------------------------------


class TestProfilerStatic:
    def test_returns_issues_with_ids(self) -> None:
        issues = profiler_agent_static(FIXTURE)
        assert len(issues) > 0
        ids = [i.id for i in issues]
        assert all(i.startswith("issue-") for i in ids)
        assert len(set(ids)) == len(ids), "ID'ler unique olmalı"

    def test_static_has_no_llm_confidence(self) -> None:
        issues = profiler_agent_static(FIXTURE)
        assert all(i.llm_confidence is None for i in issues)


# ---------------------------------------------------------------------------
# profiler_agent_hybrid
# ---------------------------------------------------------------------------


class TestProfilerHybrid:
    def test_all_confirmed_keeps_everything(self) -> None:
        """LLM her şeyi confirm ederse statik ile aynı sayıda Issue dönmeli."""

        def factory(prompt: str):
            return [
                {
                    "id": iid,
                    "confirmed": True,
                    "severity": "high",
                    "llm_confidence": 0.9,
                    "explanation": f"LLM-confirmed: {iid}",
                    "reason": None,
                }
                for iid in _ids_in_prompt(prompt)
            ]

        provider = FakeProvider(factory)
        static = profiler_agent_static(FIXTURE)
        hybrid = profiler_agent_hybrid(FIXTURE, provider=provider, model="fake-model")
        assert len(hybrid) == len(static)
        assert all(i.llm_confidence == 0.9 for i in hybrid)
        assert all(i.explanation.startswith("LLM-confirmed:") for i in hybrid)

    def test_rejecting_eliminates_false_positives(self) -> None:
        """LLM bir aday için confirmed=false derse o issue rapora girmemeli."""

        rejected: list[str] = []

        def factory(prompt: str):
            ids = _ids_in_prompt(prompt)
            verdicts = []
            for i, iid in enumerate(ids):
                if i == 0:
                    rejected.append(iid)
                    verdicts.append(
                        {
                            "id": iid,
                            "confirmed": False,
                            "llm_confidence": 0.95,
                            "reason": "false positive — test datası",
                        }
                    )
                else:
                    verdicts.append(
                        {
                            "id": iid,
                            "confirmed": True,
                            "severity": "medium",
                            "llm_confidence": 0.85,
                        }
                    )
            return verdicts

        provider = FakeProvider(factory)
        static = profiler_agent_static(FIXTURE)
        hybrid = profiler_agent_hybrid(FIXTURE, provider=provider, model="fake-model")
        assert len(hybrid) == len(static) - len(rejected)
        kept_ids = {i.id for i in hybrid}
        assert not (set(rejected) & kept_ids)

    def test_severity_override_applied(self) -> None:
        def factory(prompt: str):
            return [
                {
                    "id": iid,
                    "confirmed": True,
                    "severity": "low",  # her şey low'a düşür
                    "llm_confidence": 0.8,
                }
                for iid in _ids_in_prompt(prompt)
            ]

        hybrid = profiler_agent_hybrid(
            FIXTURE,
            provider=FakeProvider(factory),
            model="fake-model",
        )
        assert all(i.severity == "low" for i in hybrid)

    def test_llm_error_preserves_candidates(self) -> None:
        """LLM patlarsa adaylar statik haliyle korunmalı (graceful degrade)."""

        class CrashingProvider(LLMProvider):
            name = "crash"

            def list_models(self):
                return ["x"]

            def complete(self, *a, **kw):
                raise LLMError("Simulated outage")

        static = profiler_agent_static(FIXTURE)
        hybrid = profiler_agent_hybrid(
            FIXTURE,
            provider=CrashingProvider(),
            model="x",
        )
        assert len(hybrid) == len(static)
        assert all(i.llm_confidence is None for i in hybrid)

    def test_progress_callback_invoked(self) -> None:
        messages: list[str] = []

        def fact(_):
            return []

        provider = FakeProvider(fact)
        profiler_agent_hybrid(
            FIXTURE,
            provider=provider,
            model="x",
            on_progress=messages.append,
        )
        assert any("Statik" in m for m in messages)
        assert any("Profiler tamam" in m for m in messages)

    def test_chunking_respects_max(self, monkeypatch) -> None:
        """Aday sayısı > MAX_CANDIDATES_PER_CALL ise birden fazla çağrı yapılmalı."""
        # MAX'i 2'ye düşür → çok daha fazla çağrı olur
        monkeypatch.setattr("agents.profiler.MAX_CANDIDATES_PER_CALL", 2)

        def fact(prompt):
            return [
                {"id": iid, "confirmed": True, "llm_confidence": 0.9}
                for iid in _ids_in_prompt(prompt)
            ]

        provider = FakeProvider(fact)
        profiler_agent_hybrid(FIXTURE, provider=provider, model="x")
        # Fixture'da ~30+ aday var; chunk size 2 → en az 15 çağrı
        assert len(provider.calls) >= 10
        for call in provider.calls:
            assert len(call["verdict"]) <= 2
