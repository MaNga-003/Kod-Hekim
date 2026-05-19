"""Cerrah heuristic fallback — LLM yokken veya hata durumunda sözel reçete."""

from __future__ import annotations

from agents.issue import Issue
from agents.types import FixSuggestion, ImpactBreakdown

_RECIPES: dict[str, str] = {
    "N1_QUERY": (
        "1. Döngü içindeki tekil DB sorgularını tespit et.\n"
        "2. Toplu okuma (IN sorgusu, joinedload veya prefetch) ile tek seferde yükle.\n"
        "3. Integration test ile istek başına sorgu sayısının düştüğünü doğrula."
    ),
    "MISSING_TIMEOUT": (
        "1. Dış HTTP/DB çağrısına makul bir timeout ekle (ör. connect/read ayrı).\n"
        "2. Timeout ve geçici hatalar için sınırlı retry + backoff tanımla.\n"
        "3. Yavaş upstream senaryosunda worker'ların bloklanmadığını test et."
    ),
    "REPEATED_COMPUTE": (
        "1. Döngü içinde tekrarlanan invariant hesaplamayı döngü dışına taşı.\n"
        "2. Sonucu yerel değişkende sakla; döngüde yalnızca oku.\n"
        "3. Profil veya unit test ile çağrı sayısının azaldığını doğrula."
    ),
    "UNBOUNDED_CACHE": (
        "1. Cache'e TTL veya LRU/LFU eviction politikası ekle.\n"
        "2. Maksimum entry sayısı veya bellek üst sınırı tanımla.\n"
        "3. Uzun süreli yük altında RAM'in sabit kaldığını izle."
    ),
    "MEMORY_LEAK_LISTENER": (
        "1. Event listener / subscription kaydını yaşam döngüsüne bağla.\n"
        "2. Bileşen unmount veya context kapanışında removeListener çağır.\n"
        "3. Tekrarlayan mount/unmount testinde listener sayısının artmadığını doğrula."
    ),
    "DEAD_CODE": (
        "1. Kullanılmayan tanımın gerçekten referans alınmadığını IDE/grep ile doğrula.\n"
        "2. Güvenli ise tanımı ve ilgili import'ları kaldır.\n"
        "3. Test suite ve lint'in temiz geçtiğini kontrol et."
    ),
}

_DEFAULT_RECIPE = (
    "1. {file}:{line_start} satırındaki {code} bulgusunu incele.\n"
    "2. {explanation}\n"
    "3. Düzeltmeyi uyguladıktan sonra ilgili test veya manuel senaryoyu çalıştır."
)


def heuristic_fix(
    issue: Issue,
    impact: ImpactBreakdown | None = None,
) -> FixSuggestion:
    """Bulgu koduna göre uygulanabilir Türkçe reçete üret."""
    tmpl = _RECIPES.get(issue.code, _DEFAULT_RECIPE)
    try:
        instruction = tmpl.format(
            code=issue.code,
            file=issue.file,
            line_start=issue.line_start,
            explanation=issue.explanation or "Statik analiz bulgusu",
        )
    except (KeyError, IndexError):
        instruction = tmpl

    if impact and impact.explanation_tr:
        instruction = f"{instruction}\n\nNot: {impact.explanation_tr[:280]}"

    return FixSuggestion(
        issue_id=issue.id,
        fix_instruction_tr=instruction,
        risk_level=2 if issue.severity == "low" else 3,
        test_suggestion="İlgili modül için regression testi veya manuel smoke testi çalıştır.",
        improvement_estimate="Orta — kod değişikliği + doğrulama",
        recipe_valid=True,
    )
