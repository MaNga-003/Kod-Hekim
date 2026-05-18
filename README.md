# KodHekim 🩺

**Çoklu AI ajan ekibiyle repoyu kazıyıp performans, RAM israfı, güvenlik ve kalite sorunlarını tespit eden kod sağlığı tanı sistemi.**

> BTK Akademi Hackathon 2026 — Finans Teması

GitHub repo URL'sini yapıştırırsın, KodHekim'in 4 AI ajanı (Dr. Müfettiş, Dr. Ölçücü, Dr. Cerrah, Dr. Hekimbaşı) repoyu tarar; pahalı ve riskli 22 kod örüntüsünü bulur, teknik etkisini sayısal ölçer, unified diff formatında somut düzeltmeler önerir ve yazdırılabilir bir kod sağlığı raporu üretir.

---

> 🚧 **Geliştirme aşamasında.** Bu README iskelet; ürün hazır olunca §16.6'daki tam sürümle değiştirilecek.

## Hızlı başlangıç (geliştirici)

### Gereksinimler
- Python 3.11+
- Node.js 20+ ve pnpm 9+
- Git
- Cerebras ve/veya Gemini API anahtarı

### Kurulum

```powershell
# 1. Repo'yu klonla (veya bu klasördeysen atla)
cd Kod-Hekim

# 2. Backend
cd backend
uv sync                 # bağımlılıkları kurar, .venv oluşturur
cp ..\.env.example ..\.env
# .env içine CEREBRAS_API_KEY / GEMINI_API_KEY ekle

# 3. Frontend
cd ..\frontend
pnpm install
```

### Çalıştırma

```powershell
# Terminal 1: backend
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000

# Terminal 2: frontend
cd frontend
pnpm dev
```

Tarayıcıdan: http://localhost:3000

---

## Mimari

Detaylar için: [developer.md](./developer.md)

## Lisans

TBD.
