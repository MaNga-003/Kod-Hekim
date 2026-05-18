"""HARDCODED_SECRET — kaynak içinde gömülü gizli anahtar/şifre tespiti."""

from __future__ import annotations

import ast
import re

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate, StaticRule


# (etiket, regex)
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Stripe Live Key", re.compile(r"\bsk_live_[0-9a-zA-Z]{24,}\b")),
    ("GitHub Token", re.compile(r"\bghp_[0-9a-zA-Z]{36}\b")),
    ("GitHub Fine-Grained Token", re.compile(r"\bgithub_pat_[0-9a-zA-Z_]{82}\b")),
    ("Slack Bot Token", re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b")),
    ("Postgres Connection", re.compile(r"postgres(?:ql)?://[^:\s]+:[^@\s]+@[^/\s]+")),
    ("MongoDB Connection", re.compile(r"mongodb(?:\+srv)?://[^:\s]+:[^@\s]+@[^/\s]+")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
]

# Assignment hedef adında geçen ipuçları
_SECRET_NAME_HINTS = re.compile(
    r"(?i)(?:^|_)(?:secret|password|passwd|api[_-]?key|token|access[_-]?key|private[_-]?key)(?:$|_)"
)

# Hint eşleşirse minimum string uzunluğu (yanlış pozitifi azalt)
_MIN_HINT_SECRET_LEN = 8

# Aşikar placeholder'lar — flag etme
_PLACEHOLDERS = {
    "",
    "changeme",
    "change-me",
    "your-key-here",
    "your_key_here",
    "todo",
    "tbd",
    "example",
    "xxx",
    "secret",
    "password",
    "null",
    "none",
}


class HardcodedSecretRule(StaticRule):
    code = "HARDCODED_SECRET"
    category = "security"
    severity = "high"

    def scan(self, parsed: ParsedFile) -> list[IssueCandidate]:
        issues: list[IssueCandidate] = []

        # 1) Bilinen regex pattern'leri — her string literal üzerinde
        for node in ast.walk(parsed.tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            for label, regex in _PATTERNS:
                if regex.search(node.value):
                    issues.append(
                        self.make_issue(
                            file=parsed.file_path,
                            line_start=node.lineno,
                            line_end=node.end_lineno or node.lineno,
                            snippet=snippet_for(parsed, node.lineno, node.lineno),
                            explanation=(
                                f"{label} formatında bir gizli anahtar gömülü görünüyor. "
                                "Public repo'da → kalıcı sızıntı. Hemen rotate et ve env değişkenine taşı."
                            ),
                            static_confidence=0.92,
                            extra={"pattern": label},
                        )
                    )
                    break  # her literal için bir uyarı yeter

        # 2) Generic atamalar: `SECRET_KEY = "..."` gibi
        for node in ast.walk(parsed.tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
            value = node.value
            if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
                continue
            val = value.value
            if val.strip().lower() in _PLACEHOLDERS:
                continue
            if len(val) < _MIN_HINT_SECRET_LEN:
                continue

            for tgt in targets:
                name = getattr(tgt, "id", None) or getattr(tgt, "attr", None)
                if not name or not _SECRET_NAME_HINTS.search(name):
                    continue
                # Pattern eşleşmesi zaten yakalamış olabilir; tekrarı önle
                if any(i.line_start == node.lineno and i.code == self.code for i in issues):
                    continue
                issues.append(
                    self.make_issue(
                        file=parsed.file_path,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        snippet=snippet_for(parsed, node.lineno, node.lineno),
                        explanation=(
                            f"`{name}` değişkenine sabit gizli değer atanmış. "
                            "env değişkenine veya secrets manager'a taşı."
                        ),
                        static_confidence=0.7,
                        extra={"variable": name},
                    )
                )
                break

        return issues
