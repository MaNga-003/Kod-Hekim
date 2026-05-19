"""LLM çağrıları için thread tabanlı timeout (Windows uyumlu)."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Callable, TypeVar

from llm.base import LLMError

T = TypeVar("T")


def run_with_timeout(
    fn: Callable[[], T],
    *,
    timeout_sec: float | None = None,
    label: str = "LLM",
) -> T:
    if timeout_sec is None:
        try:
            timeout_sec = float(os.getenv("LLM_REQUEST_TIMEOUT_SEC", "90"))
        except ValueError:
            timeout_sec = 90.0
    timeout = timeout_sec
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        try:
            return fut.result(timeout=timeout)
        except FuturesTimeout:
            raise LLMError(f"{label} zaman aşımı ({timeout:.0f}s)") from None
