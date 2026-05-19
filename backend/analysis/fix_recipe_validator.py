"""Sözel çözüm reçetesi doğrulayıcı — Cerrah çıktısının uygulanabilir olduğunu kontrol eder."""

from __future__ import annotations

from typing import Optional

_PLACEHOLDER_MARKERS = (
    "üretilemedi",
    "geçersiz",
    "öncelik sınırı",
    "manuel inceleme gerekir",
)


def validate_recipe(text: str) -> tuple[bool, Optional[str]]:
    """Reçete metni yeterli mi? (diff/patch doğrulaması yok.)"""
    if not text or not text.strip():
        return False, "reçete boş"

    cleaned = text.strip()
    lower = cleaned.lower()

    if cleaned.startswith("(") and any(m in lower for m in _PLACEHOLDER_MARKERS):
        return False, "placeholder reçete"

    if len(cleaned) < 40:
        return False, "reçete çok kısa"

    return True, None
