"""Bozuk veya markdown-sarılı JSON'u olabildiğince kurtar.

LLM çoğu zaman temiz JSON döndürür, bazen ```json bloklarına sarar veya
trailing-comma/single-quote gibi küçük hatalar yapar. Bu modül en kötü senaryoda
None döndürür; çağıran retry stratejisini kendi yönetir.
"""

from __future__ import annotations

import json
import re
from typing import Optional


_FENCE_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)


def _strip_fences(text: str) -> str:
    """```json ... ``` veya ``` ... ``` bloklarını içeriğine indir."""
    m = _FENCE_PATTERN.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def _extract_first_json_object(text: str) -> Optional[str]:
    """Metnin içindeki ilk dengeli `{...}` veya `[...]` parçasını çıkar."""
    text = text.strip()
    if not text:
        return None
    starters = {"{": "}", "[": "]"}
    start = -1
    open_ch = ""
    for i, ch in enumerate(text):
        if ch in starters:
            start = i
            open_ch = ch
            break
    if start < 0:
        return None
    close_ch = starters[open_ch]
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _fix_common_issues(text: str) -> str:
    # Trailing commas: ,] veya ,}
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    # Python-stili True/False/None → JSON
    text = re.sub(r"\bTrue\b", "true", text)
    text = re.sub(r"\bFalse\b", "false", text)
    text = re.sub(r"\bNone\b", "null", text)
    return text


def safe_json_parse(text: str) -> Optional[dict | list]:
    """LLM çıktısını best-effort olarak JSON'a parse et.

    Hiçbir şey başaramazsa None döndür (çağıran retry yapsın).
    """
    if not text:
        return None

    candidates: list[str] = []
    stripped = _strip_fences(text)
    candidates.append(stripped)
    extracted = _extract_first_json_object(stripped)
    if extracted:
        candidates.append(extracted)

    for cand in candidates:
        for variant in (cand, _fix_common_issues(cand)):
            try:
                return json.loads(variant)
            except (json.JSONDecodeError, ValueError):
                continue
    return None
