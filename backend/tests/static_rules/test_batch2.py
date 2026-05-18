"""Batch 2: 8 orta kural testleri."""

from __future__ import annotations

import pytest

from analysis.static_rules.deep_recursion import DeepRecursionRule
from analysis.static_rules.global_accumulator import GlobalAccumulatorRule
from analysis.static_rules.missing_index_hint import MissingIndexHintRule
from analysis.static_rules.o_n_squared import ONSquaredRule
from analysis.static_rules.repeated_compute import RepeatedComputeRule
from analysis.static_rules.shadow_variable import ShadowVariableRule
from analysis.static_rules.sync_in_async import SyncInAsyncRule
from analysis.static_rules.unbounded_cache import UnboundedCacheRule
from tests.static_rules._helpers import run_rule


# ---------------------------------------------------------------------------
# UNBOUNDED_CACHE
# ---------------------------------------------------------------------------


class TestUnboundedCache:
    rule = UnboundedCacheRule()

    def test_functools_cache(self) -> None:
        src = "from functools import cache\n@cache\ndef f(x): return x\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_lru_cache_none(self) -> None:
        src = "from functools import lru_cache\n@lru_cache(maxsize=None)\ndef f(x): return x\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_module_level_dict_cache_no_eviction(self) -> None:
        src = (
            "_cache = {}\n"
            "def memoize(key, val):\n"
            "    _cache[key] = val\n"
        )
        assert len(run_rule(self.rule, src)) == 1

    def test_negative_bounded_lru(self) -> None:
        src = "from functools import lru_cache\n@lru_cache(maxsize=128)\ndef f(x): return x\n"
        assert run_rule(self.rule, src) == []

    def test_negative_cache_with_eviction(self) -> None:
        src = (
            "_cache = {}\n"
            "def memoize(k, v):\n"
            "    _cache[k] = v\n"
            "def evict(k):\n"
            "    _cache.pop(k, None)\n"
        )
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# GLOBAL_ACCUMULATOR
# ---------------------------------------------------------------------------


class TestGlobalAccumulator:
    rule = GlobalAccumulatorRule()

    def test_module_list_append(self) -> None:
        src = "events = []\ndef on_event(e):\n    events.append(e)\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_module_dict_subscript_write(self) -> None:
        src = "store = {}\ndef put(k, v):\n    store[k] = v\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_negative_with_clear(self) -> None:
        src = (
            "events = []\n"
            "def add(e):\n"
            "    events.append(e)\n"
            "def reset():\n"
            "    events.clear()\n"
        )
        assert run_rule(self.rule, src) == []

    def test_negative_local_list(self) -> None:
        src = "def f():\n    items = []\n    items.append(1)\n"
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# SYNC_IN_ASYNC
# ---------------------------------------------------------------------------


class TestSyncInAsync:
    rule = SyncInAsyncRule()

    @pytest.mark.parametrize(
        "call",
        [
            "time.sleep(1)",
            "requests.get('http://x')",
            "requests.post('http://x', json={})",
            "subprocess.run(['ls'])",
        ],
    )
    def test_positive(self, call: str) -> None:
        src = f"async def h():\n    {call}\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_negative_sync_function(self) -> None:
        src = "def h():\n    import time\n    time.sleep(1)\n"
        assert run_rule(self.rule, src) == []

    def test_negative_await_async_call(self) -> None:
        src = "async def h():\n    await something()\n"
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# REPEATED_COMPUTE
# ---------------------------------------------------------------------------


class TestRepeatedCompute:
    rule = RepeatedComputeRule()

    def test_repeated_call_same_arg(self) -> None:
        src = "for i in range(10):\n    a = expensive('config')\n    b = expensive('config')\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_negative_uses_loop_var(self) -> None:
        src = "for i in range(10):\n    a = work(i)\n    b = work(i)\n"
        # `work(i)` loop-variant: i loop_var; flag etmemeli
        assert run_rule(self.rule, src) == []

    def test_negative_single_call(self) -> None:
        src = "for i in range(10):\n    expensive('x')\n"
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# SHADOW_VARIABLE
# ---------------------------------------------------------------------------


class TestShadowVariable:
    rule = ShadowVariableRule()

    def test_shadow_builtin_list(self) -> None:
        src = "def f():\n    list = [1,2,3]\n    return list\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_shadow_builtin_id(self) -> None:
        src = "def f():\n    id = 42\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_negative_normal_name(self) -> None:
        src = "def f():\n    items = []\n"
        assert run_rule(self.rule, src) == []

    def test_negative_self_in_method(self) -> None:
        src = "class C:\n    def m(self, x):\n        self.x = x\n"
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# DEEP_RECURSION
# ---------------------------------------------------------------------------


class TestDeepRecursion:
    rule = DeepRecursionRule()

    def test_no_base_case(self) -> None:
        src = "def f(n):\n    return f(n - 1)\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_negative_with_base_case(self) -> None:
        src = "def f(n):\n    if n <= 0:\n        return 0\n    return f(n - 1)\n"
        assert run_rule(self.rule, src) == []

    def test_negative_non_recursive(self) -> None:
        src = "def f(n):\n    return n * 2\n"
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# O_N_SQUARED
# ---------------------------------------------------------------------------


class TestONSquared:
    rule = ONSquaredRule()

    def test_nested_same_collection(self) -> None:
        src = "items = [1, 2, 3]\nfor a in items:\n    for b in items:\n        pass\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_range_len(self) -> None:
        src = (
            "items = [1,2,3]\n"
            "for i in range(len(items)):\n"
            "    for j in range(len(items)):\n"
            "        pass\n"
        )
        assert len(run_rule(self.rule, src)) == 1

    def test_negative_different_collections(self) -> None:
        src = "a = [1]\nb = [2]\nfor x in a:\n    for y in b:\n        pass\n"
        assert run_rule(self.rule, src) == []

    def test_negative_single_loop(self) -> None:
        src = "for x in [1,2,3]:\n    pass\n"
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# MISSING_INDEX_HINT
# ---------------------------------------------------------------------------


class TestMissingIndexHint:
    rule = MissingIndexHintRule()

    def test_three_filters_same_field(self) -> None:
        src = (
            "a = User.query.filter_by(email='a').first()\n"
            "b = User.query.filter_by(email='b').first()\n"
            "c = User.query.filter_by(email='c').first()\n"
        )
        issues = run_rule(self.rule, src)
        assert any(i.extra["field"] == "email" for i in issues)

    def test_negative_two_filters(self) -> None:
        src = (
            "a = User.query.filter_by(email='a').first()\n"
            "b = User.query.filter_by(email='b').first()\n"
        )
        assert run_rule(self.rule, src) == []

    def test_negative_id_excluded(self) -> None:
        src = "\n".join(f"x = M.query.filter_by(id={i}).first()" for i in range(5)) + "\n"
        assert run_rule(self.rule, src) == []
