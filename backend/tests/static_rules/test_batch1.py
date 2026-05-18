"""Batch 1: 7 basit kural — pozitif + negatif testler."""

from __future__ import annotations

import pytest

from analysis.static_rules.hardcoded_secret import HardcodedSecretRule
from analysis.static_rules.inefficient_string_concat import InefficientStringConcatRule
from analysis.static_rules.list_over_generator import ListOverGeneratorRule
from analysis.static_rules.load_full_file import LoadFullFileRule
from analysis.static_rules.missing_timeout import MissingTimeoutRule
from analysis.static_rules.mutable_default_arg import MutableDefaultArgRule
from analysis.static_rules.unclosed_resource import UnclosedResourceRule
from tests.static_rules._helpers import run_rule


# ---------------------------------------------------------------------------
# MUTABLE_DEFAULT_ARG
# ---------------------------------------------------------------------------


class TestMutableDefaultArg:
    rule = MutableDefaultArgRule()

    @pytest.mark.parametrize(
        "src",
        [
            "def f(x=[]): pass",
            "def f(x=[1,2,3]): pass",
            "def f(x={}): pass",
            "def f(x={'a':1}): pass",
            "def f(x=set()): pass",
            "def f(x=list()): pass",
            "def f(x=dict()): pass",
            "async def f(x=[]): pass",
            "def f(*, x=[]): pass",
        ],
    )
    def test_positive(self, src: str) -> None:
        assert run_rule(self.rule, src), src

    @pytest.mark.parametrize(
        "src",
        [
            "def f(x=None): pass",
            "def f(x=0): pass",
            "def f(x=()): pass",
            "def f(x='abc'): pass",
            "def f(x=frozenset()): pass",
            "def f(): pass",
        ],
    )
    def test_negative(self, src: str) -> None:
        assert run_rule(self.rule, src) == [], src


# ---------------------------------------------------------------------------
# INEFFICIENT_STRING_CONCAT
# ---------------------------------------------------------------------------


class TestInefficientStringConcat:
    rule = InefficientStringConcatRule()

    def test_in_for_loop(self) -> None:
        src = "s = ''\nfor i in range(10):\n    s += 'x'\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_in_while_loop(self) -> None:
        src = "s = ''\ni = 0\nwhile i < 10:\n    s += 'x'\n    i += 1\n"
        # Both `s += 'x'` and `i += 1` are AugAssign in loop — but rule should fire on both.
        # i is name, +=1 is int not string heuristically; rule cannot know type.
        # Our heuristic flags Name RHS too. Bu kabul edilebilir; LLM filter düşürür.
        issues = run_rule(self.rule, src)
        assert any(i.line_start == 4 for i in issues)

    def test_negative_outside_loop(self) -> None:
        src = "s = ''\ns += 'x'\n"
        assert run_rule(self.rule, src) == []

    def test_negative_int_increment_in_loop_is_still_flagged_but_ok(self) -> None:
        """`i += 1` Name + Name değil — int Constant; flag etmemeli."""
        src = "for i in range(3):\n    n = 0\n    n += 1\n"
        # n += 1 → value is Constant int, not string-like → no flag
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# MISSING_TIMEOUT
# ---------------------------------------------------------------------------


class TestMissingTimeout:
    rule = MissingTimeoutRule()

    @pytest.mark.parametrize(
        "src",
        [
            "import requests\nrequests.get('http://x')",
            "import requests\nrequests.post('http://x', json={})",
            "import httpx\nhttpx.get('http://x')",
            "import urllib.request\nurllib.request.urlopen('http://x')",
        ],
    )
    def test_positive(self, src: str) -> None:
        assert len(run_rule(self.rule, src)) == 1

    @pytest.mark.parametrize(
        "src",
        [
            "import requests\nrequests.get('http://x', timeout=5)",
            "import httpx\nhttpx.post('http://x', timeout=10, json={})",
            "import requests\nrequests.session()",  # farklı method
            "import socket\nsocket.socket()",  # http değil
        ],
    )
    def test_negative(self, src: str) -> None:
        assert run_rule(self.rule, src) == [], src


# ---------------------------------------------------------------------------
# HARDCODED_SECRET
# ---------------------------------------------------------------------------


class TestHardcodedSecret:
    rule = HardcodedSecretRule()

    def test_aws_access_key(self) -> None:
        src = 'key = "AKIAIOSFODNN7EXAMPLE"'
        issues = run_rule(self.rule, src)
        assert any("AWS" in i.extra.get("pattern", "") for i in issues)

    def test_stripe_key(self) -> None:
        src = 'stripe_secret = "sk_live_abcdefghijklmnopqrstuvwx"'
        assert len(run_rule(self.rule, src)) >= 1

    def test_github_token(self) -> None:
        src = 'TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"'
        assert len(run_rule(self.rule, src)) >= 1

    def test_postgres_url(self) -> None:
        src = 'DB = "postgres://user:supersecret@db.example.com/app"'
        assert any("Postgres" in i.extra.get("pattern", "") for i in run_rule(self.rule, src))

    def test_generic_secret_assignment(self) -> None:
        src = 'API_KEY = "a-real-looking-key-12345"'
        assert len(run_rule(self.rule, src)) == 1

    def test_negative_placeholder(self) -> None:
        src = 'SECRET = "changeme"'
        assert run_rule(self.rule, src) == []

    def test_negative_short_value(self) -> None:
        src = 'PASSWORD = "x"'
        assert run_rule(self.rule, src) == []

    def test_negative_no_secret_hint(self) -> None:
        src = 'username = "alice-smith-12345"'  # uzun ama isim ipucu yok
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# LOAD_FULL_FILE
# ---------------------------------------------------------------------------


class TestLoadFullFile:
    rule = LoadFullFileRule()

    def test_read_no_args(self) -> None:
        src = "with open('x') as f:\n    data = f.read()\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_readlines(self) -> None:
        src = "with open('x') as f:\n    lines = f.readlines()\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_negative_chunked_read(self) -> None:
        src = "with open('x') as f:\n    data = f.read(1024)\n"
        assert run_rule(self.rule, src) == []

    def test_negative_iter_lines(self) -> None:
        src = "with open('x') as f:\n    for line in f:\n        pass\n"
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# UNCLOSED_RESOURCE
# ---------------------------------------------------------------------------


class TestUnclosedResource:
    rule = UnclosedResourceRule()

    def test_open_outside_with(self) -> None:
        src = "f = open('x')\nf.read()\nf.close()\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_socket_outside_with(self) -> None:
        src = "import socket\ns = socket.socket()\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_negative_with_open(self) -> None:
        src = "with open('x') as f:\n    f.read()\n"
        assert run_rule(self.rule, src) == []

    def test_negative_with_socket(self) -> None:
        src = "import socket\nwith socket.socket() as s:\n    pass\n"
        assert run_rule(self.rule, src) == []


# ---------------------------------------------------------------------------
# LIST_OVER_GENERATOR
# ---------------------------------------------------------------------------


class TestListOverGenerator:
    rule = ListOverGeneratorRule()

    def test_for_in_listcomp(self) -> None:
        src = "for x in [c for c in range(100)]:\n    print(x)\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_sum_listcomp(self) -> None:
        src = "total = sum([x*x for x in range(100)])\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_join_listcomp(self) -> None:
        src = "s = ''.join([str(x) for x in range(10)])\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_any_listcomp(self) -> None:
        src = "ok = any([x > 0 for x in range(10)])\n"
        assert len(run_rule(self.rule, src)) == 1

    def test_negative_genexp(self) -> None:
        src = "total = sum(x*x for x in range(100))\n"
        assert run_rule(self.rule, src) == []

    def test_negative_list_used_as_list(self) -> None:
        src = "items = [x*x for x in range(100)]\nitems.append(0)\n"
        assert run_rule(self.rule, src) == []
