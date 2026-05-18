# Ekran Görüntüleri

README.md ve pitch.md'nin referans verdiği 3 görüntü buraya konacak. Manuel
çekim ve dosyaya kaydetme gerekiyor — bu klasör şu an placeholder.

## Beklenen Dosyalar

| Dosya | Sayfa | Ne göstermeli |
|---|---|---|
| `01-landing.png` | `/` | URL input + Statik/Hibrit/Derin mod toggle + Cerebras/Gemini sağlayıcı seçimi + (opsiyonel) Gelişmiş panel açık |
| `02-analyze.png` | `/analyze/[jobId]` | 4 ajan kartı (en az biri "Running" durumda) + sağ panelde canlı SSE log + üstte mod ve provider rozetleri |
| `03-report.png` | `/report/[jobId]` | Sağlık skoru gauge'ı + 3 alt-rozet (Performans/Güvenlik/Kalite) + güvenlik bulguları kartı + en az bir issue card açık |

## Nasıl Çekilir

### 1. Uygulamayı çalıştır

```powershell
# Terminal 1 — backend
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
pnpm dev
```

### 2. Demo analizini başlat

Tarayıcıda `http://localhost:3000` aç. `pallets/flask`, `psf/requests` gibi
**küçük public bir Python repo** ver, **Hibrit** modu seç, **Cerebras** sağlayıcı
ile çalıştır (en hızlısı).

### 3. Üç sayfanın da görüntüsünü al

- **Windows:** `Win + Shift + S` → bölgeyi seç → `Ctrl+V` ile Paint'e yapıştır
  → PNG kaydet.
- **macOS:** `Cmd + Shift + 4` → bölge seç.
- **Linux:** `gnome-screenshot -a` veya benzer.

### 4. Bu klasöre kaydet

Dosya adlarını yukarıdaki tabloyla bire bir eşleştir (`01-landing.png` vb).

## İpuçları

- **Dark mode**'da çek — uygulama default dark, daha sinematik.
- 1440 × 900 veya 1920 × 1080 viewport — README thumbnail'larında iyi görünür.
- Analyze sayfasında en az 1-2 ajan "Done" olmuş, biri hâlâ "Running" olmalı —
  canlı akışı gösterir.
- Report sayfasında sağlık skoru 100 değil 50-80 aralığında olmalı (boş analiz değil).

## Alternatif: Demo Videosu

Eğer 3 statik PNG yerine `<10 sn` mp4/gif kayıt yapılırsa, dosyayı
`docs/screenshots/demo.gif` olarak kaydet ve README'de inline kullan.
