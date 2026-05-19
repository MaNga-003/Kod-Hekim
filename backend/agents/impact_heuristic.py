"""Statik mod etki ajanı — LLM yok, sabit Türkçe template'lar.

developer.md §3.1 ve §4.2: statik modda Türkçe açıklama
"sabit template'lerden doldurulur (örüntü tipine göre)".
"""

from __future__ import annotations

from analysis.impact_heuristics import compute_impact
from agents.issue import Issue
from agents.types import ImpactBreakdown


# Örüntü kodu → kısa Türkçe açıklama template'i
_TEMPLATES: dict[str, str] = {
    "N1_QUERY": "Döngü içinde DB çağrısı. Tipik bir istekte ~{db_calls_per_request_estimate} ekstra sorgu üretir; latency birkaç yüz ms artar, DB connection pool baskı altına girer.",
    "MISSING_TIMEOUT": "Timeout'suz dış HTTP çağrısı. Yavaş upstream pool'u tüketir, worker'lar bloklanır (risk skoru {pool_exhaustion_risk}/5).",
    "SYNC_IN_ASYNC": "Async fonksiyon içinde bloklayan sync çağrı. Event loop tamamen durur — tüm eşzamanlı isteklere yansır.",
    "MISSING_INDEX_HINT": "Aynı alan {filter_usages} farklı sorguda filtreleniyor; index yoksa her sorgu tablo taraması yapar.",
    "O_N_SQUARED": "İç içe loop ile O(n²) karmaşıklık. Liste büyüdükçe işlem süresi karesi oranında artar.",
    "LARGE_PAYLOAD": "Pagination'sız `.all()`. Tablo büyüdükçe yanıt boyutu ve latency çığ gibi büyür.",
    "REPEATED_COMPUTE": "Loop içinde aynı invariant hesaplama {redundant_calls_per_iteration} kez tekrarlanıyor.",
    "OVERFETCH_COLUMNS": "Tüm kolonlar çekiliyor ama yalnız {columns_used} kullanılıyor.",
    "UNBOUNDED_CACHE": "Cache eviction yok — RAM süresiz büyür, sonunda OOM.",
    "GLOBAL_ACCUMULATOR": "Modül-level koleksiyon her istekte büyüyor; klasik bellek sızıntısı.",
    "LIST_OVER_GENERATOR": "List comprehension yerine generator kullanılırsa peak RAM 2-10× düşer.",
    "LOAD_FULL_FILE": "Dosyanın tamamı RAM'e yükleniyor — büyük dosyada peak RAM = dosya boyutu.",
    "UNCLOSED_RESOURCE": "`with` kullanılmıyor; istisna durumunda handle açık kalır.",
    "UNHANDLED_EXCEPTION": "try/except yok; tek bozuk istek 5xx patlatır, restart loop riski.",
    "RACE_CONDITION": "Global mutable + lock'suz async erişim; veri bozulma riski.",
    "DEEP_RECURSION": "Base case net değil; büyük input'ta RecursionError riski.",
    "MUTABLE_DEFAULT_ARG": "Mutable default argument — aynı obje çağrılar arasında paylaşılır.",
    "HARDCODED_SECRET": "Kaynakta gömülü gizli anahtar; commit'lendiyse kalıcı sızıntı. Hemen rotate et.",
    "INEFFICIENT_STRING_CONCAT": "Loop içinde `+=`; O(n²) alloc — `''.join(...)` ile O(n).",
    "CIRCULAR_IMPORT": "Modüller arası döngü; startup zamanı artar, hata mesajları kafa karıştırıcı.",
    "SHADOW_VARIABLE": "Built-in/dış scope adıyla çakışan değişken — okunabilirlik ve bug yüzeyi.",
    "DEAD_CODE": "Referans verilmeyen tanım — bakım yükü.",
}

_DEFAULT_TEMPLATE = "Statik motor {code} örüntüsünü tespit etti."


def impact_agent_heuristic(issues: list[Issue]) -> list[ImpactBreakdown]:
    """LLM kullanmadan etki tahmini üret."""
    out: list[ImpactBreakdown] = []
    for issue in issues:
        score, dims, hours = compute_impact(issue)
        tmpl = _TEMPLATES.get(issue.code, _DEFAULT_TEMPLATE)
        # Sade format: missing key'leri string'e dönüştür ve `.get` ile koru
        try:
            explanation = tmpl.format(code=issue.code, **dims)
        except (KeyError, IndexError):
            explanation = tmpl.replace("{code}", issue.code)
        out.append(
            ImpactBreakdown(
                issue_id=issue.id,
                impact_score=score,
                impact_dimensions=dims,
                explanation_tr=explanation,
                remediation_effort_hours=hours,
            )
        )
    return out
