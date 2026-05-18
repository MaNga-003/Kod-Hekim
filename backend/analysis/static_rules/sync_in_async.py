"""SYNC_IN_ASYNC — `async def` içinde bloklayan senkron çağrı."""

from __future__ import annotations

import ast

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule, call_func_name


_BLOCKING_CALLS = {
    "time.sleep",
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.delete",
    "requests.patch",
    "requests.request",
    "urllib.request.urlopen",
    "subprocess.run",
    "subprocess.call",
    "subprocess.check_output",
    # open() özel — ayrıca handle ediliyor (with bloğu içinde de blocking olsa MVP'de pas)
}


class SyncInAsyncRule(StaticRule):
    code = "SYNC_IN_ASYNC"
    category = "performance"
    severity = "high"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []

        for func in ast.walk(parsed.tree):
            if not isinstance(func, ast.AsyncFunctionDef):
                continue
            for node in ast.walk(func):
                if not isinstance(node, ast.Call):
                    continue
                fname = call_func_name(node)
                if fname in _BLOCKING_CALLS:
                    issues.append(
                        self.make_issue(
                            file=parsed.file_path,
                            line_start=node.lineno,
                            line_end=node.end_lineno or node.lineno,
                            snippet=snippet_for(parsed, node.lineno, node.lineno),
                            explanation=(
                                f"`async def {func.name}` içinde `{fname}(...)` "
                                "senkron/bloklayan çağrı. Event loop bloklanır → "
                                f"tüm eşzamanlı işler durur. `await asyncio.sleep` / "
                                "`httpx.AsyncClient` / `aiofiles` kullan."
                            ),
                            static_confidence=0.92,
                            extra={"function": fname, "async_func": func.name},
                        )
                    )
        return issues
