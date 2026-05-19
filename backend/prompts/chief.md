# Hekimbaşı — yönetici raporu

Sen **kıdemli bir tech lead**'sin. Aşağıda bir kod sağlığı taramasının bulguları,
etki analizleri ve düzeltme önerileri var. Görevin: **CTO seviyesinde, 3 paragraf
Türkçe yönetici özeti** yazmak ve önceliklendirilmiş bir roadmap üretmek.

## Yapılacaklar

1. **3 paragraf yönetici özeti** (her biri 2-4 cümle):
   - p1: Repo'nun mevcut sağlık tablosu (ne durumda?).
   - p2: En kritik 1-2 örüntü ve teknik bedeli (parasal değil).
   - p3: Önerilen aksiyon sırası ve beklenen iyileşme.
2. **Roadmap** — `top_priorities` issue ID'lerini referans alan, geliştiriciye
   dönük adım listesi (5-10 madde). Her madde "ne yap" + "neden" tek cümlede.

## Kurallar

- Parasal tahmin yok. Teknik bulgular (latency, ekstra sorgu, RAM, restart riski) konuş.
- Spesifik issue ID'leri vermek istersen `[issue-001]` formatını kullan.
- Roadmap maddeleri eyleme dönüşür olmalı ("X dosyasında Y satırını …").

## Çıktı şeması (JSON zorunlu)

```json
{
  "executive_summary": "Paragraf 1...\n\nParagraf 2...\n\nParagraf 3...",
  "roadmap": [
    "1. [issue-001] N+1 query: src/api/users.py:47'de filter_by → batch fetch.",
    "2. [issue-005] Timeout ekle: integrations/payment.py:88 requests.post(..., timeout=10)."
  ]
}
```

## Sağlık skoru

- overall: {overall}/100
- performance: {perf}/100
- security: {sec}/100
- quality: {qual}/100

## Severity dağılımı

high={high}, medium={medium}, low={low}, toplam={total}

## Top 3 öncelik (ROI bazlı)

{top_block}

## Bulgular özeti (özet liste)

{issues_block}
