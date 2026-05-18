"""Batch 3: 7 karmaşık kural testleri."""

from __future__ import annotations

from analysis.ast_parser import parse_source
from analysis.static_rules.circular_import import CircularImportRule
from analysis.static_rules.dead_code import DeadCodeRule
from analysis.static_rules.large_payload import LargePayloadRule
from analysis.static_rules.n1_query import N1QueryRule
from analysis.static_rules.overfetch_columns import OverfetchColumnsRule
from analysis.static_rules.race_condition import RaceConditionRule
from analysis.static_rules.unhandled_exception import UnhandledExceptionRule
from tests.static_rules._helpers import run_rule


# ---------------------------------------------------------------------------
# N1_QUERY
# ---------------------------------------------------------------------------


class TestN1Query:
    rule = N1QueryRule()

    def test_filter_in_for_loop(self) -> None:
        src = (
            "for user in users:\n"
            "    posts = Post.query.filter_by(user_id=user.id).all()\n"
        )
        assert len(run_rule(self.rule, src)) == 1

    def test_objects_get_in_loop(self) -> None:
        src = (
            "for uid in ids:\n"
            "    u = User.objects.get(pk=uid)\n"
        )
        assert len(run_rule(self.rule, src)) >= 1

    def test_negative_outside_loop(self) -> None:
        src = "u = User.objects.get(pk=1)\n"
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# LARGE_PAYLOAD
# ---------------------------------------------------------------------------


class TestLargePayload:
    rule = LargePayloadRule()

    def test_fastapi_get_all(self) -> None:
        src = (
            "@app.get('/users')\n"
            "def list_users():\n"
            "    return User.query.all()\n"
        )
        assert len(run_rule(self.rule, src)) == 1

    def test_flask_route_all(self) -> None:
        src = (
            "@app.route('/users')\n"
            "def list_users():\n"
            "    return User.query.all()\n"
        )
        assert len(run_rule(self.rule, src)) == 1

    def test_negative_with_limit(self) -> None:
        src = (
            "@app.get('/users')\n"
            "def list_users():\n"
            "    return User.query.limit(20).all()\n"
        )
        assert run_rule(self.rule, src) == []

    def test_negative_non_handler(self) -> None:
        src = (
            "def helper():\n"
            "    return User.query.all()\n"
        )
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# OVERFETCH_COLUMNS
# ---------------------------------------------------------------------------


class TestOverfetchColumns:
    rule = OverfetchColumnsRule()

    def test_only_one_attr_used(self) -> None:
        src = (
            "users = User.query.all()\n"
            "for u in users:\n"
            "    print(u.email)\n"
        )
        assert len(run_rule(self.rule, src)) == 1

    def test_negative_many_attrs(self) -> None:
        src = (
            "users = User.query.all()\n"
            "for u in users:\n"
            "    print(u.email, u.name, u.age, u.city)\n"
        )
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# UNHANDLED_EXCEPTION
# ---------------------------------------------------------------------------


class TestUnhandledException:
    rule = UnhandledExceptionRule()

    def test_handler_with_risky_call(self) -> None:
        src = (
            "@app.post('/parse')\n"
            "def parse_payload(body):\n"
            "    data = json.loads(body)\n"
            "    return data\n"
        )
        assert len(run_rule(self.rule, src)) == 1

    def test_negative_with_try(self) -> None:
        src = (
            "@app.post('/parse')\n"
            "def parse_payload(body):\n"
            "    try:\n"
            "        return json.loads(body)\n"
            "    except Exception:\n"
            "        return {}\n"
        )
        assert run_rule(self.rule, src) == []

    def test_negative_no_risky_calls(self) -> None:
        src = (
            "@app.get('/ping')\n"
            "def ping():\n"
            "    return 'ok'\n"
        )
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# RACE_CONDITION
# ---------------------------------------------------------------------------


class TestRaceCondition:
    rule = RaceConditionRule()

    def test_global_dict_mutate_in_async(self) -> None:
        src = (
            "state = {}\n"
            "async def handler(req):\n"
            "    state[req] = 1\n"
        )
        issues = run_rule(self.rule, src)
        assert len(issues) == 1
        assert issues[0].severity == "medium"  # cap

    def test_global_list_append_in_async(self) -> None:
        src = (
            "events = []\n"
            "async def on_event(e):\n"
            "    events.append(e)\n"
        )
        assert len(run_rule(self.rule, src)) == 1

    def test_negative_with_lock(self) -> None:
        src = (
            "import asyncio\n"
            "lock = asyncio.Lock()\n"
            "state = {}\n"
            "async def handler(r):\n"
            "    async with lock:\n"
            "        state[r] = 1\n"
        )
        assert run_rule(self.rule, src) == []

    def test_negative_in_sync_func(self) -> None:
        src = (
            "state = {}\n"
            "def handler(r):\n"
            "    state[r] = 1\n"
        )
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# CIRCULAR_IMPORT (project-level)
# ---------------------------------------------------------------------------


class TestCircularImport:
    rule = CircularImportRule()

    def test_simple_two_module_cycle(self) -> None:
        a = parse_source("from b import x\n", "pkg/a.py")
        b = parse_source("from a import y\n", "pkg/b.py")
        issues = self.rule.scan_project([a, b])
        assert len(issues) >= 1

    def test_negative_no_cycle(self) -> None:
        a = parse_source("from b import x\n", "pkg/a.py")
        b = parse_source("x = 1\n", "pkg/b.py")
        issues = self.rule.scan_project([a, b])
        assert issues == []


# ---------------------------------------------------------------------------
# DEAD_CODE (project-level)
# ---------------------------------------------------------------------------


class TestDeadCode:
    rule = DeadCodeRule()

    def test_unused_function(self) -> None:
        a = parse_source("def used(): pass\ndef unused(): pass\nused()\n", "pkg/a.py")
        issues = self.rule.scan_project([a])
        names = [i.extra["symbol"] for i in issues]
        assert "unused" in names
        assert "used" not in names

    def test_negative_test_file_ignored(self) -> None:
        a = parse_source("def helper_x(): pass\n", "pkg/tests/test_x.py")
        issues = self.rule.scan_project([a])
        assert issues == []

    def test_negative_private_function(self) -> None:
        a = parse_source("def _helper(): pass\n", "pkg/a.py")
        issues = self.rule.scan_project([a])
        assert issues == []
