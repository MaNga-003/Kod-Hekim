"""Global test fixture'ları.

Burada `api.store.cleanup`'ı tüm test'lerde otomatik mock'lıyoruz: bir test
yanlışlıkla `cleanup_path = FIXTURE` durumuyla pipeline çalıştırırsa
fixture klasörünü silmesin.

Test'i gerçekten `cleanup`'ı çalıştırmak istiyorsa kendi fixture'ında
açıkça monkey-patch'i geri alır.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _safe_cleanup(monkeypatch):
    """`api.store.cleanup` test sürecinde no-op — fixture'ları korur."""
    try:
        import api.store as _store

        monkeypatch.setattr(_store, "cleanup", lambda _p: None)
    except ImportError:
        # api/store yüklenemese de test'leri durdurma
        pass
    yield
