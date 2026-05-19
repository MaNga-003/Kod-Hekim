"""JavaScript / TypeScript için metin ve Tree-sitter tabanlı statik kurallar.

Python kuralları `ast` ile çalışır; JS/TS dosyaları bu modülde taranır.
"""

from __future__ import annotations

import re

from analysis.ast_parser import ParsedFile, snippet_for
from analysis.static_rules.base import IssueCandidate
from analysis.static_rules.hardcoded_secret import (
    _MIN_HINT_SECRET_LEN,
    _PATTERNS,
    _PLACEHOLDERS,
    _SECRET_NAME_HINTS,
)

# fetch( ... ) — yakın satırlarda AbortSignal / timeout yok
_FETCH_CALL = re.compile(r"\bfetch\s*\(")
_ABORT_HINT = re.compile(r"AbortSignal|signal\s*:|timeout\s*:", re.I)
# axios — timeout yok
_AXIOS_HTTP = re.compile(r"\baxios\.(get|post|put|delete|patch|request)\s*\(")
_AXIOS_TIMEOUT = re.compile(r"timeout\s*:")

# async gövde içinde sync FS
_ASYNC_DECL = re.compile(r"\basync\s+(?:function|\(|[\w$]+\s*=>)")
_SYNC_FS = re.compile(r"\breadFileSync\b|\bwriteFileSync\b|\bexistsSync\b")

# Event listener sızıntısı (basit)
_ADD_LISTENER = re.compile(r"\.addEventListener\s*\(")
_REMOVE_LISTENER = re.compile(r"\.removeEventListener\s*\(")

# Sınırsız cache ipuçları
_LRU_NONE = re.compile(r"@lru_cache\s*\(\s*\)|@lru_cache\s*\(\s*maxsize\s*=\s*None")
_CACHE_VAR_HINT = re.compile(r"\b(cache|memo|store|registry|_map)\b", re.I)
# Python requests/httpx timeout'suz
_PY_HTTP = re.compile(r"\b(requests\.(get|post|put|delete|patch)|httpx\.(get|post|Client))\s*\(")
_PY_TIMEOUT = re.compile(r"timeout\s*=")
# Loop içi string +=
_STR_PLUS_EQ = re.compile(r"\+\=")
_FOR_LOOP = re.compile(r"\bfor\b")
def _line_issues(
    rule_code: str,
    *,
    category: str,
    severity: str,
    parsed: ParsedFile,
    line_no: int,
    explanation: str,
    static_confidence: float = 0.75,
) -> IssueCandidate:
    return IssueCandidate(
        code=rule_code,
        category=category,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        file=parsed.file_path,
        line_start=line_no,
        line_end=line_no,
        snippet=snippet_for(parsed, line_no, line_no, context=2),
        explanation=explanation,
        static_confidence=static_confidence,
    )


def _scan_secrets(parsed: ParsedFile) -> list[IssueCandidate]:
    issues: list[IssueCandidate] = []
    seen: set[tuple[int, str]] = set()
    for i, line in enumerate(parsed.lines, start=1):
        for label, pattern in _PATTERNS:
            if pattern.search(line):
                key = (i, label)
                if key in seen:
                    continue
                seen.add(key)
                issues.append(
                    _line_issues(
                        "HARDCODED_SECRET",
                        category="security",
                        severity="high",
                        parsed=parsed,
                        line_no=i,
                        explanation=f"Satırda olası gömülü gizli anahtar ({label}).",
                        static_confidence=0.85,
                    )
                )
        for m in re.finditer(
            r"(?:const|let|var)\s+(\w+)\s*=\s*['\"]([^'\"]{8,})['\"]", line
        ):
            name, val = m.group(1), m.group(2)
            if val.lower() in _PLACEHOLDERS:
                continue
            if _SECRET_NAME_HINTS.search(name) and len(val) >= _MIN_HINT_SECRET_LEN:
                key = (i, "hint")
                if key in seen:
                    continue
                seen.add(key)
                issues.append(
                    _line_issues(
                        "HARDCODED_SECRET",
                        category="security",
                        severity="high",
                        parsed=parsed,
                        line_no=i,
                        explanation=(
                            f"`{name}` değişken adı gizli anahtar ipucu taşıyor; "
                            "değer kaynak kodda düz metin."
                        ),
                        static_confidence=0.8,
                    )
                )
    return issues


def _scan_missing_timeout(parsed: ParsedFile) -> list[IssueCandidate]:
    issues: list[IssueCandidate] = []
    for i, line in enumerate(parsed.lines, start=1):
        if _FETCH_CALL.search(line):
            window = "\n".join(parsed.lines[max(0, i - 3) : min(len(parsed.lines), i + 8)])
            if not _ABORT_HINT.search(window):
                issues.append(
                    _line_issues(
                        "MISSING_TIMEOUT",
                        category="performance",
                        severity="high",
                        parsed=parsed,
                        line_no=i,
                        explanation=(
                            "`fetch(...)` çağrısında AbortSignal / timeout görünmüyor. "
                            "Askıda kalan istek connection pool'u tüketebilir."
                        ),
                        static_confidence=0.8,
                    )
                )
        if _AXIOS_HTTP.search(line) and not _AXIOS_TIMEOUT.search(line):
            issues.append(
                _line_issues(
                    "MISSING_TIMEOUT",
                    category="performance",
                    severity="high",
                    parsed=parsed,
                    line_no=i,
                    explanation=(
                        "Axios HTTP çağrısında `timeout` yapılandırması görünmüyor."
                    ),
                    static_confidence=0.82,
                )
            )
    return issues


def _scan_sync_in_async(parsed: ParsedFile) -> list[IssueCandidate]:
    issues: list[IssueCandidate] = []
    source = parsed.source
    for m in _ASYNC_DECL.finditer(source):
        start = m.start()
        # Sonraki ~800 karakter async gövde yaklaşımı
        chunk = source[start : start + 800]
        sync = _SYNC_FS.search(chunk)
        if sync:
            line_no = source[: sync.start()].count("\n") + 1
            issues.append(
                _line_issues(
                    "SYNC_IN_ASYNC",
                    category="performance",
                    severity="high",
                    parsed=parsed,
                    line_no=line_no,
                    explanation=(
                        "Async bağlamda senkron dosya sistemi çağrısı (`*Sync`) — "
                        "event loop'u bloklar."
                    ),
                    static_confidence=0.78,
                )
            )
    return issues


def _scan_memory_leak_listener(parsed: ParsedFile) -> list[IssueCandidate]:
    if not _ADD_LISTENER.search(parsed.source):
        return []
    if _REMOVE_LISTENER.search(parsed.source):
        return []
    line_no = next(
        (i for i, ln in enumerate(parsed.lines, 1) if _ADD_LISTENER.search(ln)),
        1,
    )
    return [
        _line_issues(
            "MEMORY_LEAK_LISTENER",
            category="memory",
            severity="medium",
            parsed=parsed,
            line_no=line_no,
            explanation=(
                "`addEventListener` kaydı var; eşleşen `removeEventListener` bulunamadı — "
                "uzun ömürlü süreçlerde listener birikimi."
            ),
            static_confidence=0.7,
        )
    ]


def _scan_unbounded_cache(parsed: ParsedFile) -> list[IssueCandidate]:
    issues: list[IssueCandidate] = []
    for i, line in enumerate(parsed.lines, start=1):
        if _LRU_NONE.search(line):
            issues.append(
                _line_issues(
                    "UNBOUNDED_CACHE",
                    category="memory",
                    severity="high",
                    parsed=parsed,
                    line_no=i,
                    explanation="Sınırsız LRU/cache dekoratörü — bellek sınırsız büyüyebilir.",
                    static_confidence=0.85,
                )
            )
        if "new Map(" in line and "max" not in line.lower():
            if not _CACHE_VAR_HINT.search(line):
                continue
            issues.append(
                _line_issues(
                    "UNBOUNDED_CACHE",
                    category="memory",
                    severity="high",
                    parsed=parsed,
                    line_no=i,
                    explanation=(
                        "`new Map()` için boyut/TTL sınırı görünmüyor — "
                        "anahtar birikimi RAM'i şişirebilir."
                    ),
                    static_confidence=0.72,
                )
            )
    return issues


def _scan_python_text(parsed: ParsedFile) -> list[IssueCandidate]:
    """Python dosyasında AST olmasa da çalışan metin kuralları."""
    issues: list[IssueCandidate] = []
    for i, line in enumerate(parsed.lines, start=1):
        if _PY_HTTP.search(line) and not _PY_TIMEOUT.search(line):
            window = "\n".join(parsed.lines[max(0, i - 2) : min(len(parsed.lines), i + 6)])
            if not _PY_TIMEOUT.search(window):
                issues.append(
                    _line_issues(
                        "MISSING_TIMEOUT",
                        category="performance",
                        severity="high",
                        parsed=parsed,
                        line_no=i,
                        explanation=(
                            "HTTP istemci çağrısında `timeout=` görünmüyor — "
                            "yavaş upstream worker'ları bloklayabilir."
                        ),
                        static_confidence=0.78,
                    )
                )
        if _LRU_NONE.search(line):
            issues.append(
                _line_issues(
                    "UNBOUNDED_CACHE",
                    category="memory",
                    severity="high",
                    parsed=parsed,
                    line_no=i,
                    explanation="Sınırsız `@lru_cache` — bellek sınırsız büyüyebilir.",
                    static_confidence=0.85,
                )
            )
    in_for = False
    for i, line in enumerate(parsed.lines, start=1):
        if _FOR_LOOP.search(line):
            in_for = True
            continue
        if in_for and _STR_PLUS_EQ.search(line) and ("'" in line or '"' in line):
            issues.append(
                _line_issues(
                    "INEFFICIENT_STRING_CONCAT",
                    category="quality",
                    severity="low",
                    parsed=parsed,
                    line_no=i,
                    explanation="Döngü içinde string `+=` — O(n²) alloc; join veya liste kullan.",
                    static_confidence=0.65,
                )
            )
            in_for = False
    return issues


def _scan_js_ts_extra(parsed: ParsedFile) -> list[IssueCandidate]:
    """Ek JS/TS metin kuralları."""
    issues: list[IssueCandidate] = []
    for i, line in enumerate(parsed.lines, start=1):
        if ".forEach(" in line:
            window = "\n".join(parsed.lines[max(0, i - 5) : i])
            if window.count(".forEach(") >= 1 and i > 1:
                issues.append(
                    _line_issues(
                        "O_N_SQUARED",
                        category="performance",
                        severity="medium",
                        parsed=parsed,
                        line_no=i,
                        explanation="İç içe `forEach` / döngü — O(n²) iterasyon riski.",
                        static_confidence=0.6,
                    )
                )
        if re.search(r"^(const|let|var)\s+\w+\s*=\s*\[\]", line.strip()):
            for j in range(i, min(len(parsed.lines), i + 8)):
                if ".push(" in parsed.lines[j]:
                    issues.append(
                        _line_issues(
                            "GLOBAL_ACCUMULATOR",
                            category="memory",
                            severity="high",
                            parsed=parsed,
                            line_no=i,
                            explanation=(
                                "Modül düzeyinde dizi tanımı + push — "
                                "istekler arası birikim riski."
                            ),
                            static_confidence=0.68,
                        )
                    )
                    break
    return issues


def scan_text_rules(parsed: ParsedFile) -> list[IssueCandidate]:
    """Dil bağımsız metin kuralları — Python, JavaScript, TypeScript."""
    issues: list[IssueCandidate] = []
    issues.extend(_scan_secrets(parsed))
    issues.extend(_scan_missing_timeout(parsed))
    if parsed.language in {"javascript", "typescript"}:
        issues.extend(_scan_sync_in_async(parsed))
        issues.extend(_scan_memory_leak_listener(parsed))
        issues.extend(_scan_unbounded_cache(parsed))
        issues.extend(_scan_js_ts_extra(parsed))
    elif parsed.language == "python":
        issues.extend(_scan_python_text(parsed))
    return issues


def scan_js_ts(parsed: ParsedFile) -> list[IssueCandidate]:
    """Geriye uyumluluk — JS/TS dosyaları için metin kuralları."""
    if parsed.language not in {"javascript", "typescript"}:
        return []
    return scan_text_rules(parsed)
