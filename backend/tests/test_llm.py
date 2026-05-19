"""LLM provider katmanı birim testleri — SDK'lar mock'lanır, ağa gidilmez."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from llm.base import LLMError, LLMRateLimitError, LLMResponseError
from llm.registry import default_model, get_provider, list_supported, resolve_model
from llm.safe_json import safe_json_parse


# ---------------------------------------------------------------------------
# safe_json
# ---------------------------------------------------------------------------


class TestSafeJson:
    def test_plain_json(self) -> None:
        assert safe_json_parse('{"a": 1}') == {"a": 1}

    def test_array(self) -> None:
        assert safe_json_parse("[1, 2, 3]") == [1, 2, 3]

    def test_fenced_block(self) -> None:
        text = '```json\n{"k": "v"}\n```'
        assert safe_json_parse(text) == {"k": "v"}

    def test_fenced_no_lang(self) -> None:
        text = '```\n{"k": "v"}\n```'
        assert safe_json_parse(text) == {"k": "v"}

    def test_embedded_in_prose(self) -> None:
        text = 'Tabii, işte cevap: {"answer": 42} umarım yardımcı olur.'
        assert safe_json_parse(text) == {"answer": 42}

    def test_trailing_comma(self) -> None:
        assert safe_json_parse('{"a": 1,}') == {"a": 1}

    def test_python_literals(self) -> None:
        assert safe_json_parse('{"x": True, "y": None}') == {"x": True, "y": None}

    def test_empty_returns_none(self) -> None:
        assert safe_json_parse("") is None

    def test_garbage_returns_none(self) -> None:
        assert safe_json_parse("not json at all") is None

    def test_nested_object(self) -> None:
        text = '{"outer": {"inner": [1, 2]}}'
        assert safe_json_parse(text) == {"outer": {"inner": [1, 2]}}


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_list_supported_has_both(self) -> None:
        s = list_supported()
        assert "cerebras" in s and "gemini" in s
        assert s["cerebras"] and s["gemini"]

    def test_default_model_cerebras_profiler(self, monkeypatch) -> None:
        monkeypatch.delenv("CEREBRAS_DEFAULT_PROFILER", raising=False)
        assert default_model("cerebras", "profiler") == "gpt-oss-120b"

    def test_env_override(self, monkeypatch) -> None:
        monkeypatch.setenv("CEREBRAS_DEFAULT_PROFILER", "custom-model")
        assert default_model("cerebras", "profiler") == "custom-model"

    def test_resolve_model_override_wins(self, monkeypatch) -> None:
        monkeypatch.setenv("CEREBRAS_DEFAULT_PROFILER", "env-model")
        assert resolve_model("cerebras", "profiler", override="ui-model") == "ui-model"

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(LLMError):
            get_provider("openai")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Cerebras provider — SDK mock'lu
# ---------------------------------------------------------------------------


def _fake_cerebras_module(response_text: str = '{"ok": true}', tokens: int = 42, raise_exc=None):
    """`cerebras.cloud.sdk` modülünü mock'la."""
    cerebras_mod = SimpleNamespace()

    class FakeChoice:
        def __init__(self, content: str):
            self.message = SimpleNamespace(content=content)

    class FakeResponse:
        def __init__(self, content: str, tokens: int):
            self.choices = [FakeChoice(content)]
            self.usage = SimpleNamespace(total_tokens=tokens)

    class FakeCompletions:
        def __init__(self):
            self.create = MagicMock()
            if raise_exc:
                self.create.side_effect = raise_exc
            else:
                self.create.return_value = FakeResponse(response_text, tokens)

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.chat = FakeChat()

    cerebras_mod.Cerebras = FakeClient
    return cerebras_mod


class TestCerebrasProvider:
    def _install(self, monkeypatch, **kwargs):
        monkeypatch.setenv("CEREBRAS_API_KEY", "fake-key")
        cloud_mod = SimpleNamespace(sdk=_fake_cerebras_module(**kwargs))
        cerebras_pkg = SimpleNamespace(cloud=cloud_mod)
        monkeypatch.setitem(sys.modules, "cerebras", cerebras_pkg)
        monkeypatch.setitem(sys.modules, "cerebras.cloud", cloud_mod)
        monkeypatch.setitem(sys.modules, "cerebras.cloud.sdk", cloud_mod.sdk)

    def test_plain_complete(self, monkeypatch) -> None:
        self._install(monkeypatch, response_text="merhaba dünya", tokens=10)
        from llm.cerebras_provider import CerebrasProvider

        p = CerebrasProvider()
        resp = p.complete("selam", model="gpt-oss-120b")
        assert resp["text"] == "merhaba dünya"
        assert resp["tokens_used"] == 10
        assert resp["model"] == "gpt-oss-120b"
        assert resp["json"] is None
        assert resp["latency_ms"] >= 0

    def test_json_complete(self, monkeypatch) -> None:
        self._install(monkeypatch, response_text='{"answer": 7}', tokens=15)
        from llm.cerebras_provider import CerebrasProvider

        p = CerebrasProvider()
        resp = p.complete("?", model="gpt-oss-120b", json_schema={"type": "object"})
        assert resp["json"] == {"answer": 7}

    def test_missing_api_key_raises(self, monkeypatch) -> None:
        monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
        # Modülün import edilmesi için yine de mock kur
        cloud_mod = SimpleNamespace(sdk=_fake_cerebras_module())
        monkeypatch.setitem(sys.modules, "cerebras", SimpleNamespace(cloud=cloud_mod))
        monkeypatch.setitem(sys.modules, "cerebras.cloud", cloud_mod)
        monkeypatch.setitem(sys.modules, "cerebras.cloud.sdk", cloud_mod.sdk)

        from llm.cerebras_provider import CerebrasProvider

        with pytest.raises(LLMError):
            CerebrasProvider()

    def test_rate_limit_retries_then_raises(self, monkeypatch) -> None:
        # Bekleme yok — sleep'i no-op'la
        monkeypatch.setattr("llm.cerebras_provider.time.sleep", lambda *_: None)
        self._install(monkeypatch, raise_exc=RuntimeError("HTTP 429 Too Many Requests"))
        from llm.cerebras_provider import CerebrasProvider

        p = CerebrasProvider()
        with pytest.raises(LLMRateLimitError):
            p.complete("x", model="gpt-oss-120b")

    def test_non_rate_error_propagates(self, monkeypatch) -> None:
        self._install(monkeypatch, raise_exc=RuntimeError("Auth failed"))
        from llm.cerebras_provider import CerebrasProvider

        p = CerebrasProvider()
        with pytest.raises(LLMError):
            p.complete("x", model="gpt-oss-120b")

    def test_list_models(self, monkeypatch) -> None:
        self._install(monkeypatch)
        from llm.cerebras_provider import AVAILABLE_MODELS, CerebrasProvider

        p = CerebrasProvider()
        assert set(p.list_models()) == set(AVAILABLE_MODELS)


# ---------------------------------------------------------------------------
# Gemini provider — SDK mock'lu
# ---------------------------------------------------------------------------


class _FakeGeminiModel:
    def __init__(self, name, system_instruction=None, response_text="ok", tokens=5, raise_exc=None):
        self.name = name
        self.response_text = response_text
        self.tokens = tokens
        self.raise_exc = raise_exc
        self.generate_content = MagicMock(side_effect=self._gen)

    def _gen(self, prompt, generation_config=None):
        if self.raise_exc:
            raise self.raise_exc
        return SimpleNamespace(
            text=self.response_text,
            usage_metadata=SimpleNamespace(total_token_count=self.tokens),
        )


def _fake_genai_module(response_text="ok", tokens=5, raise_exc=None):
    state = {"configured_key": None}

    def configure(api_key=None):
        state["configured_key"] = api_key

    def model_factory(name, **kwargs):
        return _FakeGeminiModel(
            name,
            response_text=response_text,
            tokens=tokens,
            raise_exc=raise_exc,
            **kwargs,
        )

    mod = SimpleNamespace(
        configure=configure,
        GenerativeModel=model_factory,
        _state=state,
    )
    return mod


class TestGeminiProvider:
    def _mock_response(self, monkeypatch, *, status: int = 200, body: dict | None = None, text: str = "ok", tokens: int = 5):
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        payload = body or {
            "candidates": [{"content": {"parts": [{"text": text}]}}],
            "usageMetadata": {"totalTokenCount": tokens},
        }

        class FakeResp:
            status_code = status
            def json(self):
                return payload
            text = str(payload)

        class FakeClient:
            def __init__(self, *a, **k):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def post(self, url, params=None, json=None):
                return FakeResp()

        monkeypatch.setattr("llm.gemini_provider.httpx.Client", FakeClient)

    def test_plain_complete(self, monkeypatch) -> None:
        self._mock_response(monkeypatch, text="merhaba", tokens=8)
        from llm.gemini_provider import GeminiProvider

        p = GeminiProvider()
        resp = p.complete("selam", model="gemini-2.5-flash")
        assert resp["text"] == "merhaba"
        assert resp["tokens_used"] == 8
        assert resp["json"] is None

    def test_json_complete(self, monkeypatch) -> None:
        self._mock_response(monkeypatch, text='{"k": 1}')
        from llm.gemini_provider import GeminiProvider

        p = GeminiProvider()
        resp = p.complete("?", model="gemini-2.5-pro", json_schema={"type": "object"})
        assert resp["json"] == {"k": 1}

    def test_missing_api_key_raises(self, monkeypatch) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        from llm.gemini_provider import GeminiProvider

        with pytest.raises(LLMError):
            GeminiProvider()

    def test_rate_limit_retries_then_raises(self, monkeypatch) -> None:
        monkeypatch.setattr("llm.gemini_provider.time.sleep", lambda *_: None)
        calls = {"n": 0}

        class RateResp:
            status_code = 429
            text = "quota exhausted"
            def json(self):
                return {"error": {"message": "quota exhausted"}}

        class FakeClient:
            def __init__(self, *a, **k):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def post(self, url, params=None, json=None):
                calls["n"] += 1
                return RateResp()

        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        monkeypatch.setattr("llm.gemini_provider.httpx.Client", FakeClient)
        from llm.gemini_provider import GeminiProvider

        p = GeminiProvider()
        with pytest.raises(LLMRateLimitError):
            p.complete("x", model="gemini-2.5-flash")
        assert calls["n"] >= 1

    def test_empty_candidate_raises_response_error(self, monkeypatch) -> None:
        self._mock_response(monkeypatch, body={"candidates": []})
        from llm.gemini_provider import GeminiProvider

        p = GeminiProvider()
        with pytest.raises(LLMResponseError):
            p.complete("x", model="gemini-2.5-flash")
