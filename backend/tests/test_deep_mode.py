"""Faz J — Derin mod (LLM-Direct) testleri.

Kapsam:
- `ast_summary.summarize_repo` — fonksiyon/class/import çıkarımı, framework tespiti.
- `pick_full_inclusion_files` — entry point > __main__ > küçük dosyalar; bütçe.
- `profiler_agent_deep` — prompt placeholder dolumu, schema iletim,
  çıktı parse, severity sıralı id ataması, LLM hatası fallback.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.issue import Issue
from agents.profiler import (
    DEEP_SCHEMA,
    DEFAULT_DEEP_TOKEN_BUDGET,
    profiler_agent_deep,
    profiler_agent_static,
)
from analysis.ast_summary import (
    ClassInfo,
    FileSummary,
    FunctionInfo,
    RepoSummary,
    estimate_tokens,
    pick_full_inclusion_files,
    summarize_file,
    summarize_repo,
)
from llm.base import LLMError, LLMProvider, LLMResponse


# ---------------------------------------------------------------------------
# Yardımcı: sahte LLM provider
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# ast_summary.summarize_file / summarize_repo
# ---------------------------------------------------------------------------


_SAMPLE_PY = """\
import json
import time
from fastapi import FastAPI
from .models import User

app = FastAPI()
_cache = {}


@app.get("/users")
def list_users(limit: int = 50):
    return list(_cache.values())[:limit]


@app.post("/items")
async def add_item(payload: dict):
    return {"ok": True}


class UserService:
    def __init__(self):
        self.users = []

    async def fetch(self, uid: str):
        return self.users


if __name__ == "__main__":
    print("starting")
"""


class TestSummarizeFile:
    def test_extracts_imports_functions_classes(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text(_SAMPLE_PY, encoding="utf-8")
        s = summarize_file(f, tmp_path)
        assert s is not None
        assert s.file == "app.py"
        assert s.line_count > 0
        # Imports
        assert any("json" in i for i in s.imports)
        assert any("fastapi" in i.lower() for i in s.imports)
        assert any("models.User" in i for i in s.imports)
        # Functions
        names = {fn.name for fn in s.functions}
        assert {"list_users", "add_item"}.issubset(names)
        # async detection
        async_fn = next(fn for fn in s.functions if fn.name == "add_item")
        assert async_fn.is_async
        # Classes + methods
        assert len(s.classes) == 1
        cls = s.classes[0]
        assert cls.name == "UserService"
        assert "fetch" in cls.methods
        # Route decorator tespiti
        assert any("app.get" in d for d in s.route_decorators)
        # __main__ guard
        assert s.has_main_entry

    def test_syntax_error_returns_none(self, tmp_path: Path) -> None:
        f = tmp_path / "broken.py"
        f.write_text("def f(:\n", encoding="utf-8")
        assert summarize_file(f, tmp_path) is None

    def test_outline_renders(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text(_SAMPLE_PY, encoding="utf-8")
        s = summarize_file(f, tmp_path)
        outline = s.to_outline()
        assert "app.py" in outline
        assert "list_users" in outline
        assert "UserService" in outline


class TestSummarizeRepo:
    def test_walks_multiple_files_and_detects_frameworks(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text(_SAMPLE_PY, encoding="utf-8")
        (tmp_path / "b.py").write_text("import django\n\ndef foo(): pass\n", encoding="utf-8")
        repo = summarize_repo(tmp_path)
        assert len(repo.files) == 2
        assert "fastapi" in repo.detected_frameworks
        assert "django" in repo.detected_frameworks
        # total_lines toplandı
        assert repo.total_lines >= sum(f.line_count for f in repo.files) - 1


# ---------------------------------------------------------------------------
# pick_full_inclusion_files
# ---------------------------------------------------------------------------


class TestFileSelection:
    def test_entry_points_prioritized(self) -> None:
        files = [
            FileSummary(file="util.py", line_count=20),
            FileSummary(
                file="api.py", line_count=200, route_decorators=["app.get"]
            ),
            FileSummary(file="cli.py", line_count=50, has_main_entry=True),
        ]
        repo = RepoSummary(files=files)
        loader = {"util.py": "u" * 80, "api.py": "a" * 800, "cli.py": "c" * 200}
        picked = pick_full_inclusion_files(
            repo, loader.__getitem__, char_budget=10_000
        )
        ordered = [p[0] for p in picked]
        # api.py (route) önce, cli.py (main) ikinci, util.py sonra
        assert ordered.index("api.py") < ordered.index("cli.py")
        assert ordered.index("cli.py") < ordered.index("util.py")

    def test_budget_enforced(self) -> None:
        files = [FileSummary(file=f"f{i}.py", line_count=10) for i in range(10)]
        repo = RepoSummary(files=files)
        loader = lambda p: "x" * 200  # her dosya 200 char
        picked = pick_full_inclusion_files(repo, loader, char_budget=600)
        # ~200+200+200=600 → en fazla 2-3 dosya
        total = sum(len(src) for _, src in picked)
        assert total <= 600

    def test_handles_oserror(self) -> None:
        files = [FileSummary(file="missing.py", line_count=10)]
        repo = RepoSummary(files=files)

        def crash(_):
            raise OSError("nope")

        picked = pick_full_inclusion_files(repo, crash, char_budget=1000)
        assert picked == []


class TestTokenEstimate:
    def test_rough_char_per_token(self) -> None:
        assert estimate_tokens("a" * 100) == 25
        assert estimate_tokens("") == 1  # min 1


# ---------------------------------------------------------------------------
# profiler_agent_deep
# ---------------------------------------------------------------------------


_BAD_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "bad_code_examples"


class TestDeepProfiler:
    def test_prompt_includes_outline_and_files(self) -> None:
        provider = _RecorderProvider({"issues": []})
        profiler_agent_deep(
            _BAD_FIXTURE, provider=provider, model="x"
        )
        assert provider.calls
        prompt = provider.calls[0]["prompt"]
        # Placeholder'lar dolduruldu
        assert "{repo_outline}" not in prompt
        assert "{full_files}" not in prompt
        # Repo özet başlığı
        assert "Repo özeti" in prompt
        # Bilinen örüntü listesi
        assert "N1_QUERY" in prompt
        assert "MISSING_TIMEOUT" in prompt
        assert "HARDCODED_SECRET" in prompt

    def test_schema_and_temperature_transport(self) -> None:
        provider = _RecorderProvider({"issues": []})
        profiler_agent_deep(_BAD_FIXTURE, provider=provider, model="m1")
        kw = provider.calls[0]["kw"]
        assert kw.get("json_schema") == DEEP_SCHEMA
        assert kw.get("temperature") == 0.4

    def test_parses_issues_and_assigns_ids(self) -> None:
        provider = _RecorderProvider({
            "issues": [
                {
                    "code": "N1_QUERY",
                    "category": "performance",
                    "severity": "high",
                    "file": "api.py",
                    "line_start": 47,
                    "line_end": 53,
                    "snippet": "for u ...",
                    "explanation": "N+1 query.",
                },
                {
                    "code": "OTHER_unbatched_writes",
                    "category": "performance",
                    "severity": "medium",
                    "file": "writer.py",
                    "line_start": 12,
                    "line_end": 18,
                    "snippet": "...",
                    "explanation": "Batch yazılabilirdi.",
                },
            ]
        })
        out = profiler_agent_deep(_BAD_FIXTURE, provider=provider, model="x")
        assert len(out) == 2
        # Severity sıralı id ataması (high önce)
        assert out[0].severity == "high"
        assert out[0].id == "issue-001"
        assert out[1].severity == "medium"
        assert out[1].id == "issue-002"
        # OTHER_* kabul ediliyor
        assert out[1].code.startswith("OTHER_")
        # Derin mod işareti
        assert out[0].extra.get("deep_mode") is True
        assert out[0].llm_confidence == 1.0
        assert out[0].static_confidence == 0.0

    def test_invalid_category_coerced(self) -> None:
        provider = _RecorderProvider({
            "issues": [{
                "code": "X",
                "category": "uydurma_kategori",
                "severity": "alacaranji",
                "file": "x.py",
                "line_start": 1,
                "line_end": 1,
                "snippet": "",
                "explanation": "x",
            }]
        })
        out = profiler_agent_deep(_BAD_FIXTURE, provider=provider, model="x")
        assert len(out) == 1
        assert out[0].category == "quality"  # fallback
        assert out[0].severity == "medium"  # fallback

    def test_llm_error_falls_back_to_static(self) -> None:
        class Crash(LLMProvider):
            name = "crash"

            def list_models(self):
                return ["x"]

            def complete(self, *a, **kw):
                raise LLMError("down")

        static = profiler_agent_static(_BAD_FIXTURE)
        out = profiler_agent_deep(_BAD_FIXTURE, provider=Crash(), model="x")
        assert len(out) == len(static)
        assert len(out) > 0

    def test_progress_callback_invoked(self) -> None:
        msgs: list[str] = []
        provider = _RecorderProvider({"issues": []})
        profiler_agent_deep(
            _BAD_FIXTURE, provider=provider, model="x", on_progress=msgs.append
        )
        assert any("özet" in m.lower() or "ozet" in m.lower() for m in msgs)
        assert any("LLM" in m for m in msgs)

    def test_token_budget_limits_inclusion(self) -> None:
        """Çok düşük bütçe → hiç tam dosya inject edilmez, sadece outline."""
        provider = _RecorderProvider({"issues": []})
        # Outline + few-shot zaten bütçeyi aşacak; full_files boş kalmalı
        profiler_agent_deep(
            _BAD_FIXTURE, provider=provider, model="x", max_tokens_budget=100,
        )
        prompt = provider.calls[0]["prompt"]
        # Tam dosya block'unun yerine placeholder mesaj
        assert "tam dosya seçilmedi" in prompt
