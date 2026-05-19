"""Faz H — Cerrah genişletilmiş testleri (batch LLM, sözel reçete)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.issue import Issue
from agents.surgeon import SURGEON_BATCH_SCHEMA, _load_few_shot_block, surgeon_agent
from agents.types import FixSuggestion, ImpactBreakdown
from llm.base import LLMProvider, LLMResponse


GOOD_RECIPE = (
    "1. Kök neden: N+1 sorgu.\n"
    "2. Batch fetch kullan.\n"
    "3. Sonuçları grupla.\n"
    "4. Integration test ekle."
)


def _issue(
    iid: str = "issue-001",
    code: str = "N1_QUERY",
    category: str = "performance",
) -> Issue:
    return Issue(
        id=iid,
        code=code,
        category=category,  # type: ignore[arg-type]
        severity="high",
        file="api.py",
        line_start=10,
        line_end=12,
        snippet="for u in users: ...",
        explanation="statik açıklama",
        static_confidence=0.8,
    )


def _batch_json(*issues: Issue, **fields) -> dict:
    defaults = {
        "fix_instruction_tr": GOOD_RECIPE,
        "risk_level": 2,
        "test_suggestion": "t",
        "improvement_estimate": "i",
    }
    defaults.update(fields)
    return {
        "fixes": [
            {"issue_id": iss.id, **defaults}
            for iss in (issues or (_issue(),))
        ]
    }


class _RecorderProvider(LLMProvider):
    name = "recorder"

    def __init__(self, response: dict):
        self.response = response
        self.calls: list[dict] = []

    def list_models(self):
        return ["x"]

    def complete(self, prompt, model, **kw):
        self.calls.append({"prompt": prompt, "kw": kw, "model": model})
        return LLMResponse(
            text="", json=self.response, tokens_used=10, model=model, latency_ms=2
        )


class TestFewShotExamples:
    def test_few_shot_block_loaded(self) -> None:
        block = _load_few_shot_block()
        assert block, "few-shot block boş — examples/surgeon_*.json eksik"
        assert block.count("### Örnek:") >= 2
        assert "N1_QUERY" in block or "MISSING_TIMEOUT" in block

    def test_few_shot_examples_have_valid_json(self) -> None:
        examples = Path(__file__).resolve().parent.parent / "prompts" / "examples"
        files = list(examples.glob("surgeon_*.json"))
        assert len(files) >= 3, f"en az 3 surgeon örneği bekleniyor, bulunan: {len(files)}"
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            assert "issue" in data and "response" in data
            assert "fix_instruction_tr" in data["response"]
            assert len(data["response"]["fix_instruction_tr"]) >= 40
            assert "risk_level" in data["response"]
            assert 1 <= data["response"]["risk_level"] <= 5

    def test_few_shot_block_appears_in_prompt(self, tmp_path: Path) -> None:
        (tmp_path / "api.py").write_text("# stub\n", encoding="utf-8")
        provider = _RecorderProvider(_batch_json(_issue()))
        surgeon_agent([_issue()], repo_path=tmp_path, provider=provider, model="x")
        prompt = provider.calls[0]["prompt"]
        assert "### Örnek:" in prompt
        assert "Reçete:" in prompt


class TestSchemaTransport:
    def test_schema_passed_to_provider(self, tmp_path: Path) -> None:
        (tmp_path / "api.py").write_text("# stub\n", encoding="utf-8")
        provider = _RecorderProvider(_batch_json(_issue()))
        surgeon_agent([_issue()], repo_path=tmp_path, provider=provider, model="x")
        kw = provider.calls[0]["kw"]
        assert kw.get("json_schema") == SURGEON_BATCH_SCHEMA
        assert kw.get("temperature") == 0.25

    def test_impact_summary_in_prompt(self, tmp_path: Path) -> None:
        (tmp_path / "api.py").write_text("# stub\n", encoding="utf-8")
        provider = _RecorderProvider(_batch_json(_issue()))
        impacts = {
            "issue-001": ImpactBreakdown(
                issue_id="issue-001",
                impact_score=90,
                explanation_tr="ÖZEL_ETKI_METNI_BURADA",
            )
        }
        surgeon_agent(
            [_issue()], repo_path=tmp_path, provider=provider, model="x", impacts=impacts,
        )
        prompt = provider.calls[0]["prompt"]
        assert "ÖZEL_ETKI_METNI_BURADA" in prompt

    def test_no_impact_uses_placeholder(self, tmp_path: Path) -> None:
        (tmp_path / "api.py").write_text("# stub\n", encoding="utf-8")
        provider = _RecorderProvider(_batch_json(_issue()))
        surgeon_agent([_issue()], repo_path=tmp_path, provider=provider, model="x")
        prompt = provider.calls[0]["prompt"]
        assert "n/a" in prompt

    def test_prompt_requests_verbal_recipe_not_diff(self, tmp_path: Path) -> None:
        (tmp_path / "api.py").write_text("# stub\n", encoding="utf-8")
        provider = _RecorderProvider(_batch_json(_issue()))
        surgeon_agent([_issue()], repo_path=tmp_path, provider=provider, model="x")
        prompt = provider.calls[0]["prompt"].lower()
        assert "sözel" in prompt
        assert "fix_instruction_tr" in prompt
        assert "reçete" in prompt


class TestCodeWindow:
    def test_code_window_includes_target_lines(self, tmp_path: Path) -> None:
        lines = [f"line_{i}" for i in range(1, 51)]
        (tmp_path / "api.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
        provider = _RecorderProvider(_batch_json(_issue()))
        issue = Issue(
            id="issue-001",
            code="N1_QUERY",
            category="performance",
            severity="high",
            file="api.py",
            line_start=25,
            line_end=27,
            snippet="...",
            explanation="x",
            static_confidence=0.8,
        )
        surgeon_agent([issue], repo_path=tmp_path, provider=provider, model="x")
        prompt = provider.calls[0]["prompt"]
        assert "line_5" in prompt
        assert "line_45" in prompt
        assert "line_25" in prompt

    def test_missing_file_does_not_crash(self, tmp_path: Path) -> None:
        provider = _RecorderProvider(_batch_json(_issue()))
        out = surgeon_agent([_issue()], repo_path=tmp_path, provider=provider, model="x")
        assert len(out) == 1
        prompt = provider.calls[0]["prompt"]
        assert "okunamadı" in prompt


class TestMultiplePatternsShape:
    @pytest.mark.parametrize(
        "code,category",
        [
            ("N1_QUERY", "performance"),
            ("MISSING_TIMEOUT", "performance"),
            ("UNBOUNDED_CACHE", "memory"),
            ("HARDCODED_SECRET", "security"),
            ("DEAD_CODE", "quality"),
        ],
    )
    def test_fix_suggestion_shape(self, tmp_path: Path, code: str, category: str) -> None:
        (tmp_path / "api.py").write_text("# stub\n", encoding="utf-8")
        issue = _issue(code=code, category=category)
        provider = _RecorderProvider(_batch_json(issue))
        out = surgeon_agent([issue], repo_path=tmp_path, provider=provider, model="x")
        assert len(out) == 1
        fix = out[0]
        assert isinstance(fix, FixSuggestion)
        assert fix.issue_id == issue.id
        assert fix.recipe_valid
        assert 1 <= fix.risk_level <= 5
        assert fix.test_suggestion
        assert fix.improvement_estimate


class TestSurgeonEdgeCases:
    def test_empty_issue_list(self, tmp_path: Path) -> None:
        provider = _RecorderProvider(_batch_json(_issue()))
        out = surgeon_agent([], repo_path=tmp_path, provider=provider, model="x")
        assert out == []
        assert provider.calls == []

    def test_progress_callback_invoked(self, tmp_path: Path) -> None:
        (tmp_path / "api.py").write_text("# stub\n", encoding="utf-8")
        provider = _RecorderProvider(
            _batch_json(_issue("issue-A"), _issue("issue-B"))
        )
        msgs: list[str] = []
        surgeon_agent(
            [_issue("issue-A"), _issue("issue-B")],
            repo_path=tmp_path,
            provider=provider,
            model="x",
            on_progress=msgs.append,
        )
        assert any("issue-A" in m and "issue-B" in m for m in msgs)
