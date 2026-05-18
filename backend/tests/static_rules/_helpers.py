"""Statik kural testleri için ortak yardımcılar."""

from __future__ import annotations

from analysis.ast_parser import parse_source
from analysis.static_rules.base import IssueCandidate, StaticRule


def run_rule(rule: StaticRule, source: str, file_path: str = "test.py") -> list[IssueCandidate]:
    parsed = parse_source(source, file_path)
    return rule.scan(parsed)


def codes(issues: list[IssueCandidate]) -> list[str]:
    return [i.code for i in issues]
