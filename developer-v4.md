# KodHekim — Developer Spesifikasyonu (v4)

> **BTK Akademi Hackathon 2026 — Finans Teması**
> "Çoklu AI ajan ekibiyle repoyu kazıyıp performans, RAM israfı, güvenlik ve kalite sorunlarını tespit eden, somut tanı raporu çıkaran **kod sağlığı tanı sistemi**."

**Son güncelleme:** 19 Mayıs 2026 (Adım 6 — Kod Sağlığı Isı Haritası)
**Geliştirici sayısı:** 1
**Çalışma modeli:** Sprintsiz, kesintisiz tek bir roadmap üzerinden baştan sona ilerleme. Geliştirici kendi ritmini kendi belirler; her faz tamamlandıktan sonra bir sonrakine geçilir.

---

## 0. Yönetici Özeti

### Problem
Kötü yazılmış bir döngü, gereksiz veritabanı sorgusu, sınırsız büyüyen cache, bellek sızıntısı, timeout'suz HTTP çağrısı — bunlar görünmez. Kod çalıştıkça sunucuyu yorar, RAM'i şişirir, latency'yi yükseltir, instance'ı upgrade etmeye iter. CTO "faturalar şişiyor" diye yakınır, kimse asıl suçluyu (kodu) bulamaz. Geleneksel linterlar style, güvenlik tarayıcıları CVE, APM araçları runtime'a bakar — kimse **kod örüntüsü → kaynak baskısı** bağlantısını kuran tanı çıkaramaz.

### Çözüm
Kullanıcı GitHub repo URL'sini yapıştırır. KodHekim'in 4 AI ajanı işbaşı yapar:

1. **Profiler** — Statik kural motoru + LLM ile **22 farklı pahalı/riskli kod örüntüsü** tespit eder (performans, RAM, güvenilirlik, güvenlik, kalite).
2. **Etki Analisti** — Her sorunun teknik etkisini ölçer (ekstra DB çağrısı sayısı, bellek sızıntı hızı, latency etkisi, restart riski). Parasal değil, somut teknik veri.
3. **Cerrah** — Her sorun için **sözel, mantıksal ve adımsal mimari çözüm önerisi** üretir (Türkçe reçete metni; kod patch/diff üretmez).
4. **Hekimbaşı** — Tüm bulguları toplayıp yönetici özetli, tarayıcıdan yazdırılabilir bir kod sağlığı raporu yazar.

### Üç analiz modu
Kullanıcı UI'dan seçer:

| Mod | Nasıl | Hız | Yer |
|---|---|---|---|
| **Statik** | Sadece kural motoru | ⚡⚡⚡ | Hızlı CI/CD entegrasyonu için |
| **Hibrit** *(default)* | Kural motoru + LLM confirm | ⚡⚡ | Genel kullanım için |
| **Derin** | Kod + AST direkt LLM'e | ⚡ | Beklenmedik örüntüler için, küçük-orta repo |

### Çıktı
```
Repo sağlık skoru: 62/100
  ├─ Performans: 58/100
  ├─ Güvenlik:   90/100
  └─ Kalite:     71/100

Tespit edilen sorun: 18 (yüksek: 5, orta: 8, düşük: 5)
En kritik: src/api/users.py:47 — N+1 query (~1000 ekstra DB çağrısı/istek)
Düzeltme efor tahmini: ~9 geliştirici saati

▸ Önce/Sonra simülasyonu: seçilen sorunlar giderilse skor 62 → 91
```

### Ek özellikler (jüri için kritik)
- **🎯 Önce/Sonra simülasyonu** — Kullanıcı raporda sorunları tick'ler, sağlık skorunun nereye çıkacağını canlı görür.
- **👨‍⚕️ Ajan karakterleri** — 4 ajanın her biri kişilik olarak konumlandırılır (avatar + Türkçe doktor unvanı + uzmanlık).
- **📊 Mod karşılaştırma** — Analiz sonunda Statik/Hibrit/Derin için süre + token + bulgu karşılaştırması.
- **🏷️ GitHub badge** — README'ye eklenebilen `kodhekim score: 78/100` SVG rozeti.
- **🧠 LLM düşünme stream'i, 🔎 repo ön-tarama, 🎯 auto-scroll** — polish dokunuşları.

### MVP Kapsamı
> Python, JavaScript ve TypeScript dilleri tam olarak desteklenmektedir.

### Yarışma temasına uyum (Finans)
KOBİ Finans Asistanı'nın yazılım versiyonu. Yarışma şartnamesinde "KOBİ Finans Asistanı" örneği var — KodHekim onun **operasyonel maliyet (cloud bill)** ayağını çözüyor. Ürün parasal tahmin yapmıyor, somut teknik bulgular üretip geliştiricinin/CTO'nun kendi maliyet kararını alabileceği veriyi sağlıyor. Bu **kasıtlı bir tasarım kararı**: parasal tahminler her zaman varsayım içerir ve "ekstra 1000 DB çağrısı / istek" gibi somut bir veri parasal bir tahminden daha ikna edicidir.

---

## 1. Sistem Mimarisi

```
┌─────────────────────────────────────────────────────────────────┐
│                       FRONTEND (Next.js 14)                     │
│  ┌──────────┐   ┌─────────────────┐   ┌──────────────────────┐ │
│  │ Landing  │ → │  Analiz Sayfası │ → │  Tanı Raporu Sayfası │ │
│  │ URL +    │   │  Canlı log      │   │  Sorunlar + Etki +   │ │
│  │ Mod seç  │   │                 │   │  Reçeteler           │ │
│  └──────────┘   └─────────────────┘   └──────────────────────┘ │
└──────────────┬─────────────────────────────┬────────────────────┘
               │ HTTP                        │ SSE (live)
               ▼                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI · Python)                   │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              Orchestrator (LangGraph)                     │ │
│  │  ┌────────┐  ┌──────────────┐  ┌────────┐  ┌──────────┐  │ │
│  │  │Profiler│→ │Etki Analisti │→ │ Cerrah │→ │Hekimbaşı │  │ │
│  │  └────────┘  └──────────────┘  └────────┘  └──────────┘  │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────────────────┐ │
│  │Repo Cloner │  │  AST Parser │  │ Static Rule Engine       │ │
│  │(gitpython) │  │ Python·JS·TS│  │ (22 örüntü plugin)       │ │
│  │            │  │ ast + tree- │  │                          │ │
│  │            │  │ sitter      │  │                          │ │
│  └────────────┘  └─────────────┘  └──────────────────────────┘ │
│                              │                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │             LLM Provider Abstraction                      │ │
│  │  ┌───────────────────┐         ┌───────────────────────┐  │ │
│  │  │ Cerebras Provider │         │   Gemini Provider     │  │ │
│  │  │ (gpt-oss-120b,    │         │ (2.5 Pro / 2.5 Flash) │  │ │
│  │  │  llama, qwen,     │         │                       │  │ │
│  │  │  glm-4.7)         │         │                       │  │ │
│  │  └───────────────────┘         └───────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Teknoloji yığını

| Katman | Seçim | Sebep |
|---|---|---|
| Frontend | Next.js 14 (App Router) + React + TailwindCSS | Hızlı SSR, geniş ekosistem |
| Backend | FastAPI (Python 3.11) | AI ekosistemi Python'da, async-first |
| Agent Orchestration | LangGraph | Multi-agent state machine, durum yönetimi |
| LLM Sağlayıcı 1 | **Cerebras Cloud SDK** | Çoklu açık model, çok yüksek hız |
| LLM Sağlayıcı 2 | **Google Gemini SDK** | 1M context window — Derin mod için |
| Static Analysis | `ast` (Python) + `tree-sitter-python`, `tree-sitter-javascript`, `tree-sitter-typescript` | AST düzeyinde precision; **Python, JavaScript, TypeScript** — üç dil aktif |
| Dil desteği | Python · JavaScript · TypeScript | `.py`, `.js`/`.jsx`, `.ts`/`.tsx`; karışık repolarda `mixed` mod |
| Live Updates | Server-Sent Events (SSE) | WebSocket'ten basit, yeterli |
| Repo Cloning | `gitpython` + shallow clone (depth=1) | Hız |
| State/Cache | In-memory dict (job_id → state) | Yeterli; Redis opsiyonel |
| Rapor formatı | **Web rapor + tarayıcı "Yazdır"** | PDF üretimi yok; CSS `@media print` yeterli |
| Deploy | Vercel (frontend) + Render (backend) | Ücretsiz tier |

### AST ayrıştırıcı (3 dil)

| Dil | Dosya uzantıları | Ayrıştırıcı |
|---|---|---|
| **Python** | `.py` | `ast` (stdlib) |
| **JavaScript** | `.js`, `.jsx` | `tree-sitter-javascript` |
| **TypeScript** | `.ts`, `.tsx` | `tree-sitter-typescript` |

Her dosya uzantısına göre doğru ayrıştırıcı seçilir; statik kural motoru aynı `StaticRule` arayüzü üzerinden üç dilde de çalışır (`backend/analysis/ast_parser.py`).

### Üç dil tarama katmanı (Adım 2 — uygulama sözleşmesi)

```
languages.py          → python | javascript | typescript | mixed
       ↓
file_walker.py        → .py/.js/.jsx/.ts/.tsx (node_modules, .next, venv hariç)
       ↓
ast_parser.py         → Python: ast | JS/TS: Tree-sitter (yoksa metin modu)
       ↓
scan.py               ├─ Python + AST  → ALL_RULES (22 AST plugin)
                       ├─ Python, AST yok → scan_text_rules (secret, timeout, cache…)
                       └─ JS/TS         → scan_text_rules + js_ts_scan heuristikleri
       ↓
profiler_agent_*      → Statik: tüm adaylar | Hibrit: LLM confirm | Derin: LLM-direct
```

**Kritik kurallar:**
- Klon dizini **sistem temp** altında olmalı (`%TEMP%/kodhekim`); `backend/tmp` kullanılırsa `uvicorn --reload` job store'u sıfırlar → SSE 404 / analiz hatası.
- Statik modda **hiçbir aday LLM ile filtrelenmez** — skor tüm bulgulardan hesaplanır (§4.4).
- Cerrah yalnızca Hibrit/Derin modda çalışır; LLM hata verirse `surgeon_heuristic.py` yedek reçete üretir.

---

## 2. LLM Sağlayıcı Soyutlaması

Kullanıcı UI'dan **hangi sağlayıcıyı + hangi modeli** kullanacağına karar verir. Her ajan farklı bir model çalıştırabilir.

### 2.1 Sağlayıcı arayüzü

```python
# backend/llm/base.py
from abc import ABC, abstractmethod
from typing import TypedDict, Optional

class LLMResponse(TypedDict):
    text: str
    json: Optional[dict]
    tokens_used: int
    model: str
    latency_ms: int

class LLMProvider(ABC):
    @abstractmethod
    def list_models(self) -> list[str]: ...

    @abstractmethod
    def complete(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.2,
        json_schema: Optional[dict] = None,
        max_tokens: int = 4096,
    ) -> LLMResponse: ...
```

### 2.2 Cerebras sağlayıcısı

Desteklenecek modeller:

| Model ID | Önerilen kullanım | Not |
|---|---|---|
| `gpt-oss-120b` | Genel amaçlı, en sağlam seçim | 120B, ~3000 t/s |
| `llama3.1-8b` | Çok hızlı sınıflandırma | ⚠️ 27 Mayıs 2026'da deprecate olacak |
| `qwen-3-235b-a22b-instruct-2507` | Ağır akıl yürütme | ⚠️ 27 Mayıs 2026'da deprecate olacak |
| `zai-glm-4.7` | Kod analizi | GLM-4 ailesi, kod için güçlü |

> ⚠️ **Hackathon teslim tarihi 19 Mayıs**, deprecate tarihi 27 Mayıs. Submit anında 4'ü de çalışır. Deprecate olacak modeller için güncel ID'ler (`llama-3.3-70b`, `qwen-3-32b` veya benzeri) planlanır. Doc Ek A'da detay.

```python
# backend/llm/cerebras_provider.py
from cerebras.cloud.sdk import Cerebras

class CerebrasProvider(LLMProvider):
    AVAILABLE_MODELS = [
        "gpt-oss-120b",
        "llama3.1-8b",
        "qwen-3-235b-a22b-instruct-2507",
        "zai-glm-4.7",
    ]

    def __init__(self, api_key: str):
        self.client = Cerebras(api_key=api_key)

    def list_models(self) -> list[str]:
        return self.AVAILABLE_MODELS

    def complete(self, prompt, model, temperature=0.2, json_schema=None, max_tokens=4096):
        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }
        if json_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "out", "strict": True, "schema": json_schema},
            }
        import time
        start = time.monotonic()
        resp = self.client.chat.completions.create(**kwargs)
        latency = int((time.monotonic() - start) * 1000)
        text = resp.choices[0].message.content
        return LLMResponse(
            text=text,
            json=_safe_json_parse(text) if json_schema else None,
            tokens_used=resp.usage.total_tokens,
            model=model,
            latency_ms=latency,
        )
```

### 2.3 Gemini sağlayıcısı

```python
# backend/llm/gemini_provider.py
import google.generativeai as genai
import time

class GeminiProvider(LLMProvider):
    AVAILABLE_MODELS = ["gemini-2.5-pro", "gemini-2.5-flash"]

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)

    def list_models(self):
        return self.AVAILABLE_MODELS

    def complete(self, prompt, model, temperature=0.2, json_schema=None, max_tokens=4096):
        m = genai.GenerativeModel(model)
        config = {"temperature": temperature, "max_output_tokens": max_tokens}
        if json_schema:
            config["response_mime_type"] = "application/json"
            config["response_schema"] = json_schema
        start = time.monotonic()
        resp = m.generate_content(prompt, generation_config=config)
        return LLMResponse(
            text=resp.text,
            json=_safe_json_parse(resp.text) if json_schema else None,
            tokens_used=resp.usage_metadata.total_token_count,
            model=model,
            latency_ms=int((time.monotonic() - start) * 1000),
        )
```

### 2.4 Sağlayıcı seçici

```python
# backend/llm/registry.py
def get_provider(name: str) -> LLMProvider:
    if name == "cerebras":
        return CerebrasProvider(api_key=os.environ["CEREBRAS_API_KEY"])
    if name == "gemini":
        return GeminiProvider(api_key=os.environ["GEMINI_API_KEY"])
    raise ValueError(f"Unknown provider: {name}")
```

### 2.5 Varsayılan ajan-model eşlemesi

| Ajan | Cerebras varsayılan | Gemini varsayılan |
|---|---|---|
| Profiler confirm | `gpt-oss-120b` | `gemini-2.5-flash` |
| Etki Analisti | `gpt-oss-120b` | `gemini-2.5-flash` |
| Cerrah | `zai-glm-4.7` | `gemini-2.5-pro` |
| Hekimbaşı | `qwen-3-235b-a22b-instruct-2507` | `gemini-2.5-pro` |
| **Derin mod (LLM-Direct)** | `qwen-3-235b-a22b-instruct-2507` | **`gemini-2.5-pro`** (1M context — önerilen) |

### 2.6 UI'da seçim (Landing)

```
┌──────────────────────────────────────────────┐
│  Analiz Modu:                                │
│  ○ Statik   ⦿ Hibrit (önerilen)   ○ Derin    │
│  (hover/focus → tooltip: hız, token, kapsam) │
│                                              │
│  Sağlayıcı:                                  │
│  ⦿ Cerebras    ○ Gemini                      │
│                                              │
│  ▸ Gelişmiş: Ajan başına model               │
│    Profiler:     [gpt-oss-120b ▾]            │
│    Etki:         [gpt-oss-120b ▾]            │
│    Hekimbaşı:    [qwen-3-235b... ▾]          │
└──────────────────────────────────────────────┘
```

`POST /api/analyze` body:
```json
{
  "repo_url": "https://github.com/user/repo",
  "mode": "static" | "hybrid" | "deep",
  "provider": "cerebras" | "gemini",
  "model_overrides": {
    "profiler": "gpt-oss-120b",
    "impact": "gpt-oss-120b",
    "chief": "qwen-3-235b-a22b-instruct-2507",
    "deep_mode": "gemini-2.5-pro"
  }
}
```

---

## 3. Üç Analiz Modu

**Dil kapsamı:** Üç mod da **Python**, **JavaScript** ve **TypeScript** kaynak dosyalarını analiz eder. Dosya yürüyücü `*.py`, `*.js`, `*.jsx`, `*.ts`, `*.tsx` uzantılarını tarar; repoda birden fazla dil varsa otomatik `mixed` dil modu seçilir. 22 örüntünün hangi dillerde aktif olduğu §5'te `StaticRule.languages` ile belirtilir.

### 3.1 Statik mod
Yalnızca kural motoru, LLM yok. Hız: 50 dosyalı repo < 5 saniye. Token tüketimi: 0. Python, JS ve TS dosyalarının tamamı statik kurallardan geçer.

- Profiler: kural motoru tüm aday sorunları işaretler, hiçbiri filtrelenmez (LLM confirm yok).
- Etki Analisti: salt heuristic-tabanlı metrik üretir (sayısal). Türkçe açıklama: sabit template'lerden doldurulur (örüntü tipine göre).
- Cerrah: **devre dışı** (LLM olmadan sözel çözüm önerisi üretilemez). UI'da "Çözüm reçetesi (Hibrit veya Derin modda etkin)" mesajı.
- Hekimbaşı: salt heuristic — sağlık skoru, sorun listesi, top 3 öncelik (LLM yazılı özet yok).

### 3.2 Hibrit mod (default)
Kural motoru + LLM confirm. Tüm 4 ajan çalışır.

- Profiler: aday sorunları LLM batch'lerle confirm eder (yanlış pozitif elenir, severity ayarlanır).
- Etki Analisti: heuristic metrikler + LLM Türkçe açıklama.
- Cerrah: LLM ile **Türkçe, adımsal sözel çözüm reçetesi** üretir.
- Hekimbaşı: LLM ile yönetici özeti yazar.

Token tüketimi: ~110K (~50 dosyalı orta boy Python/JS/TS repo).

### 3.3 Derin mod (LLM-Direct)

**Amaç:** Statik kural motorunun yakalayamadığı **beklenmedik örüntüleri** keşfetmek. LLM kendi bilgisiyle analiz eder.

**Akış:**
1. Repo dosyalarını yürü (tıpkı diğer modlarda).
2. Her dosya için **özetlenmiş AST + ham kod** çıkar (Python `ast`, JS/TS Tree-sitter).
   - "Özetlenmiş AST": fonksiyon imzaları + class yapısı + import grafiği + kontrol akışı outline (`backend/analysis/ast_summary.py` tarafından üretilir; üç dilde aynı özet şeması).
3. **Tek bir büyük prompt** halinde LLM'e gönder:
   - Sistem mesajı: "Aşağıdaki repo'da kaynak (CPU/RAM/I/O/güvenlik) tüketen örüntüleri bul. Bilinen 22 örüntü dışında da arayabilirsin."
   - Eklenecek: 22 örüntü listesi (referans), repo özet AST, *seçilmiş* tam kod dosyaları (en büyük 10 + entry point).
4. LLM, kendi belirlediği `code` ile sorunlar üretir (`OTHER_<kebab-case>` kabul edilir).
5. Üretilen sorunlar `IssueCandidate` formatına dönüştürülür, sonra Etki Analisti + Cerrah + Hekimbaşı **aynı pipeline'a** girer.

**Önemli kısıtlar:**
- **Token bütçesi tavanı:** 800K token (Gemini 2.5 Pro 1M sınırı).
- Repo > tavan ise: en önemli dosyalar seçilir (entry point + en çok import edilen 20 dosya), kalan dosyalar sadece AST özeti olarak girer.
- **Sağlayıcı uyarısı:** Cerebras tarafında `qwen-3-235b` context daha küçük; UI'da "Derin mod için Gemini 2.5 Pro önerilir" uyarısı.

**LLM prompt iskeleti (`prompts/deep_mode.md`):**
```
Sen bir senior performance & security engineer'sın. Aşağıdaki repo'yu analiz et
ve kaynak tüketen / güvenlik açığı yaratan örüntüleri tespit et.

Bilinen örüntü listesi (referans):
{KNOWN_PATTERNS}

Bunların dışında da örüntü bulabilirsin. Bulduğun her sorun için:
- code: bilinen örüntü ID'si veya "OTHER_<açıklayıcı-isim>"
- severity: high | medium | low
- file, line_start, line_end
- snippet (5-15 satır)
- explanation (Türkçe, 2 cümle)
- why_costly: bu sorun hangi kaynağı yorar?

Repo özeti:
{REPO_SUMMARY}

Tam dosya içerikleri:
{FULL_FILES}

JSON döndür: {"issues": [...]}
```

**Çıktı format:** Hibrit moddaki ile aynı şema, sadece `code` alanı `"OTHER_*"` olabilir.

**Trade-off uyarısı (UI'da kullanıcıya gösterilir):**
- ✅ Beklenmedik örüntüleri yakalar
- ✅ Bağlama duyarlıdır (örn. bu kod tam olarak ne yapıyor)
- ⚠️ Yanlış pozitif oranı Hibrit'ten yüksek olabilir
- ⚠️ Yavaş ve token-pahalı
- ⚠️ Çok büyük repo'larda dosya kırpılır

---

## 4. Ajan Detayları

### 4.0 Ajan karakterleri

Her ajan UI'da **avatar + Türkçe doktor unvanı + uzmanlık rozeti** ile görünür. Akılda kalıcılık + Türk jürisine sıcaklık için.

| Ajan | Avatar | Unvan | Uzmanlık rozeti |
|---|---|---|---|
| Profiler | 🔍 | **Dr. Müfettiş** | "Kodun her köşesini araştırır" |
| Etki Analisti | 📊 | **Dr. Ölçücü** | "Sayısal etkiyi hesaplar" |
| Cerrah | 🩹 | **Dr. Cerrah** | "Adımsal çözüm reçetesi yazar" |
| Hekimbaşı | ⚕️ | **Dr. Hekimbaşı** | "Tanıyı raporlar" |

Frontend bileşeni: `components/agent-persona.tsx` — avatar (emoji veya SVG), unvan, rozet, durum (Pending/Running/Done).

### 4.1 Dr. Müfettiş — Profiler Ajanı

**Görev:** 22 örüntüyü tespit etmek (mod'a göre LLM confirm var/yok).

**Girdi:** Repo klasör yolu, dil(ler) (`python` | `javascript` | `typescript` | `mixed`), analiz modu.

**İşlem akışı (Hibrit):**
1. Dosyaları yürü (`*.py`, `*.js`, `*.ts`, `*.tsx`, `*.jsx` — `node_modules`, `venv`, `.git`, `dist`, `build`, `.next`, `__pycache__` hariç).
2. Her dosya için uzantıya göre doğru AST ayrıştırıcıyı seç:
   - **Python** (`.py`): `ast` (stdlib)
   - **JavaScript** (`.js`, `.jsx`): `tree-sitter-javascript`
   - **TypeScript** (`.ts`, `.tsx`): `tree-sitter-typescript`
3. **Statik kural motoru** ile aday sorunları işaretle — her kuralın `languages` listesi hangi dilde aktif olduğunu belirler; üç dil aynı plugin arayüzünü paylaşır.
4. **LLM ile context confirm** — batch'lerle.
5. Onaylanmış sorunları JSON listesi olarak yay.

**Statik mod:** 4. adım atlanır.
**Derin mod:** §3.3 akışı uygulanır.

**Çıktı şeması:**
```json
{
  "issues": [
    {
      "id": "issue-001",
      "code": "N1_QUERY",
      "category": "performance" | "memory" | "reliability" | "security" | "quality",
      "severity": "high" | "medium" | "low",
      "file": "src/api/users.py",
      "line_start": 47,
      "line_end": 53,
      "snippet": "...",
      "explanation": "...",
      "static_confidence": 0.9,
      "llm_confidence": 0.95
    }
  ]
}
```

### 4.2 Dr. Ölçücü — Etki Analisti Ajanı

**Görev:** Her sorunun teknik etkisini somut metriklerle ölçer + Türkçe açıklama üretir. **Hiçbir koşulda parasal değer üretmez.**

**Girdi:** Profiler'ın çıktısı + repo metadata (dosya sayısı, dil, hot-path sinyalleri).

**Üretilen metrikler örüntü tipine göre:**

| Sorun tipi | Ölçülen etki | Ölçüm yöntemi |
|---|---|---|
| `N1_QUERY` | Ekstra DB çağrısı / istek | Loop iter × DB call (AST'den) |
| `MEMORY_LEAK_LISTENER` | Sızıntı/saat tahmini | Listener kayıt frekansı + handler boyutu |
| `SYNC_IN_ASYNC` | Engellenen event-loop süresi | sleep/blocking call sayısı |
| `MISSING_INDEX_HINT` | Tahmini full-scan ekstra I/O | Filter sıklığı |
| `O_N_SQUARED` | Komplekslik (input boyutuna göre) | İç içe loop derinliği |
| `LARGE_PAYLOAD` | Tahmini transfer boyutu | `.all()` + model alan sayısı |
| `REPEATED_COMPUTE` | Gereksiz hesaplama / istek | Loop iter × fonksiyon karmaşıklığı |
| `UNCLOSED_RESOURCE` | Açık kalan handle / istek | `open` sayısı |
| `OVERFETCH_COLUMNS` | Ekstra kolon / sorgu | Çekilen − kullanılan kolon sayısı |
| `MISSING_TIMEOUT` | Connection pool tükenme riski (1-5) | Endpoint sıklığı |
| `INEFFICIENT_STRING_CONCAT` | Ekstra heap alloc / iter | Loop boyutu |
| `DEEP_RECURSION` | Maks stack derinliği tahmini | Recursive call zinciri |
| **`UNBOUNDED_CACHE`** | Sınırsız büyüme hızı tahmini | Cache anahtar üretim alanı tahmini |
| **`GLOBAL_ACCUMULATOR`** | Sızıntı hızı (entry/istek) | append çağrı sıklığı |
| **`LIST_OVER_GENERATOR`** | Peak RAM çarpanı | Tahmini koleksiyon boyutu |
| **`LOAD_FULL_FILE`** | Peak RAM (dosya boyutu) | Dosya context'i (büyük dosya endpoint'lerine yakınlık) |
| `UNHANDLED_EXCEPTION` | Restart loop riski (1-5) | Çağrı sıklığı + critical path |
| `RACE_CONDITION` | Data corruption riski (1-5) | Paylaşılan mutable + lock yokluğu |
| `HARDCODED_SECRET` | Açığa çıkma kapsamı | Git geçmişine işlenmiş mi + repo public mi |
| `CIRCULAR_IMPORT` | Startup zamanı etkisi (ms) | Import zinciri uzunluğu |
| `MUTABLE_DEFAULT_ARG` | Sızıntı potansiyeli (1-5) | Fonksiyon çağrı sıklığı |
| `SHADOW_VARIABLE` | Okunabilirlik / bug yüzeyi | Scope mesafesi |
| `DEAD_CODE` | Bakım yükü | Satır sayısı |

**LLM'in rolü:** Statik metrikleri Türkçe açıklamalı somut etki cümlesine çevirir. Örnek:
> "Bu N+1 query, sayfa başına ~50 ortalama kullanıcı için her istekte 50 ekstra DB çağrısı demektir. Saniyede 10 istek varsa DB için saniyede 500 ekstra sorgu. Aynı endpoint p99 latency'sini 850ms aralığından ~150ms aralığına çekmesi muhtemeldir."

**Çıktı şeması:**
```json
{
  "issue_id": "issue-001",
  "impact_score": 87,
  "impact_dimensions": {
    "db_calls_per_request": 1000,
    "estimated_latency_ms": 850,
    "scaling_risk": "high"
  },
  "explanation_tr": "...",
  "remediation_effort_hours": 0.5
}
```

### 4.3 Dr. Cerrah — Cerrah Ajanı

**Görev:** Her sorun için mantıksal, adımsal ve **Türkçe sözel düzeltme rehberi** üretmek. Statik modda **çalışmaz** (kullanıcıya "çözüm reçetesi için Hibrit/Derin moda geçin" mesajı).

**Tasarım kararı:** Cerrah artık unified diff veya otomatik kod patch'i üretmez. Riskli otomatik kod değişikliği yerine geliştiriciye **mimari yönlendirme** sunar — daha güvenli ve esnek bir "sözel danışman" modeli.

**Girdi:** Sorun detayı, etki metriği (motivasyon olarak prompt'a girer), orijinal kod context'i (sorunun olduğu dosyanın tamamı, en fazla 200 satır pencere).

**İşlem:**
1. LLM'e structured prompt: "Bu sorunun nasıl çözüleceğini geliştiriciye Türkçe, adımsal ve sözel bir reçete olarak anlat."
2. Yan etki riski + test önerisi + iyileşme tahmini.
3. Sözel metin üretildiği için **kod doğrulayıcı (diff parser / retry mekanizması) gerekmez** — çıktı doğrudan rapora yazılır.

**Prompt template (`prompts/surgeon.md`):**
```
Sen bir senior performance engineer'sın. Aşağıdaki kod sorununu düzeltmek için
geliştiriciye rehberlik et.

Sorun: {issue_code}
Açıklama: {explanation}
Teknik etki: {impact_summary}
Dosya: {file_path}

Orijinal kod (sorunun olduğu satırlar ± 30):
```{language}
{original_snippet}
```

Bu sorunun nasıl çözüleceğini geliştiriciye **Türkçe, adımsal ve sözel bir reçete** olarak anlat:
1. Kök neden (1-2 cümle)
2. Adım adım düzeltme yönergeleri (numaralı liste)
3. Yan etki riski (1-5)
4. Test önerisi (tek cümle)
5. Tahmini iyileşme (ms ya da %)

JSON döndür: {"fix_instruction_tr": "...", "risk_level": int, "test_suggestion": "...", "improvement_estimate": "..."}
```

**Çıktı:**
```json
{
  "issue_id": "issue-001",
  "fix_instruction_tr": "1. Döngü içindeki tekil sorguları kaldır.\n2. Tüm user_id'leri topla.\n3. Tek batch sorgu ile Post'ları çek (IN (...) veya joinedload).\n4. Sonuçları bellekte user_id'ye göre grupla.",
  "risk_level": 2,
  "test_suggestion": "Integration test ile yanıtın hâlâ tüm post'ları içerdiğini doğrula.",
  "improvement_estimate": "Yanıt süresi 850ms → 45ms (~%95 hızlanma)"
}
```

### 4.4 Dr. Hekimbaşı — Hekimbaşı Ajanı

**Görev:** Tüm bulguları toplayıp yöneticiye sunulabilir Türkçe rapor üretir.

**Girdi:** Tüm sorunlar + etki metrikleri + Cerrah reçeteleri.

**Çıktı:**
- **Sağlık skoru** (0–100) + 3 alt-kategori rozeti (performans, güvenlik, kalite).
- **Top 3 öncelik** (en yüksek ROI'li sorunlar).
- **3 paragraf yönetici özeti** — LLM ile yazılır (Hibrit/Derin modda).
- **Geliştirici roadmap'i** — öncelik sıralı sorun listesi.

**Sağlık skoru formülü:**
```python
def health_score(issues: list[Issue]) -> dict:
    severity_weights = {"high": 10, "medium": 5, "low": 2}

    def cat_penalty(cat: str) -> int:
        return sum(
            severity_weights[i.severity]
            for i in issues
            if i.category == cat
        )

    perf_penalty = cat_penalty("performance") + cat_penalty("memory")
    sec_penalty  = cat_penalty("security") + cat_penalty("reliability")
    qual_penalty = cat_penalty("quality")

    total_penalty = perf_penalty + sec_penalty + qual_penalty

    return {
        "overall": max(0, 100 - total_penalty),
        "performance": max(0, 100 - perf_penalty * 2),  # ağırlıklı
        "security":    max(0, 100 - sec_penalty  * 3),  # daha sert
        "quality":     max(0, 100 - qual_penalty * 1),
    }
```

**Top 3 öncelik (ROI):**
```python
def top_priorities(items):
    scored = [
        (iss, iss.impact_score / max(0.25, iss.remediation_effort_hours))
        for iss in items
    ]
    return sorted(scored, key=lambda x: -x[1])[:3]
```

---

## 5. Tespit Edilen Örüntüler (22 örüntü — Python, JS, TS)

Kategoriler: **Performans (8)**, **RAM/Bellek (5)**, **Güvenilirlik (4)**, **Güvenlik (1, ayrı UI bölümü)**, **Kalite (5)**.

Her örüntü `StaticRule.languages` ile hangi dillerde aktif olduğunu belirtir. Tree-sitter ve `ast` parser'ları üç dilde de aynı plugin arayüzünü kullanır.

### 5.1 Performans (8)

#### `N1_QUERY` — N+1 veritabanı sorgusu (yüksek)
- **Tespit:** Loop içinde DB call (`.query`, `.filter`, `.objects.get`, `.find`).
- **Dil:** Python (SQLAlchemy/Django ORM), JS/TS (Sequelize/Prisma/TypeORM).

#### `SYNC_IN_ASYNC` — Async fonksiyonda blocking call (yüksek)
- **Tespit:** `async def` / `async function` içinde `time.sleep`, `requests.get/post`, sync `open()`, `fs.readFileSync`.
- **Dil:** Python, JavaScript, TypeScript.

#### `MISSING_INDEX_HINT` — İndex eksik sorgu (orta)
- **Tespit:** Aynı alan üzerinde >3 yerde `.filter(field=X)` ama model'de index yok.
- **Dil:** Python ORM, JS/TS ORM.

#### `O_N_SQUARED` — İç içe O(n²) loop (düşük-orta)
- **Tespit:** İç içe iki for loop, aynı koleksiyona ref.
- **Dil:** Python, JavaScript, TypeScript.

#### `LARGE_PAYLOAD` — Pagination'sız büyük yanıt (orta)
- **Tespit:** Route handler içinde `.all()`, pagination/limit yok.
- **Dil:** Python (FastAPI/Flask + ORM), JS/TS (Express/Nest + ORM).

#### `REPEATED_COMPUTE` — Loop içinde tekrar hesaplama (düşük)
- **Tespit:** Loop içinde sabit argümanla aynı pure fonksiyon çağrısı.
- **Dil:** Python, JavaScript, TypeScript.

#### `OVERFETCH_COLUMNS` — Gereksiz kolon çekme (orta)
- **Tespit:** `SELECT *` veya `.all()` üzerinden model, sonra sadece 1-2 alan kullanımı (data-flow analizi).
- **Dil:** Python ORM, JS/TS ORM.

#### `MISSING_TIMEOUT` — Timeout'suz dış çağrı (yüksek)
- **Tespit:** `requests.get/post`, `httpx`, `urllib`; JS/TS `fetch` AbortController yok, `axios` timeout yok.
- **Dil:** Python, JavaScript, TypeScript.

### 5.2 RAM / Bellek (5)

#### `MEMORY_LEAK_LISTENER` — Event listener sızıntısı (orta)
- **Tespit:** `addEventListener` / `on('event')` kaydı var, karşılık gelen `removeListener` / `off` yok; DOM veya EventEmitter birikimi.
- **Dil:** JavaScript, TypeScript (Node.js EventEmitter dahil).

#### `UNCLOSED_RESOURCE` — Açık kalan resource (düşük)
- **Tespit:** `open()` / `socket()` var, `with` bloğu içinde değil, `.close()` yok; JS stream/handle kapatılmamış.
- **Dil:** Python, JavaScript, TypeScript.

#### `UNBOUNDED_CACHE` — Sınırsız cache (yüksek)
- **Tespit:**
  - `@lru_cache(maxsize=None)` veya `@cache` decorator
  - Modül seviyesinde `_cache = {}` + eviction yok
  - JS/TS: `Map` / object cache, TTL veya size limit yok
- **Dil:** Python, JavaScript, TypeScript.

#### `GLOBAL_ACCUMULATOR` — Global biriktirme (yüksek)
- **Tespit:** Modül seviyesinde liste/dict + handler içinde `.append()` / `[key] =`. Tahliye yok.
- **Dil:** Python, JavaScript, TypeScript.

#### `LIST_OVER_GENERATOR` — Generator yerine liste (düşük)
- **Tespit:** `[expr for x in big_iter]` veya `Array.from` / spread ile gereksiz materialize; sonuç sadece iterate ediliyor.
- **Dil:** Python, JavaScript, TypeScript.

#### `LOAD_FULL_FILE` — Dosyayı tek seferde yükleme (düşük-orta)
- **Tespit:** `f.read()` / `f.readlines()`; JS `readFileSync`, streaming yerine.
- **Dil:** Python, JavaScript, TypeScript.

### 5.3 Güvenilirlik (4)

#### `UNHANDLED_EXCEPTION` — Yakalanmayan istisna (orta)
- **Tespit:** Route handler'da try/except yok ve içeride raise edebilecek çağrı var.
- **Dil:** Python, JavaScript, TypeScript.

#### `RACE_CONDITION` — Yarış durumu (orta, dar kapsam)
- **Tespit:** Global/module-level mutable üzerinde async içinden mutate (lock yok); paylaşılan state.
- **Dil:** Python (asyncio), JavaScript, TypeScript.
- **Not:** Severity tavanı `medium`. LLM confirm kritik.

#### `DEEP_RECURSION` — Derin recursion (düşük)
- **Tespit:** Fonksiyon kendisini çağırır, base case zayıf; zincir > 3 fonksiyon.
- **Dil:** Python, JavaScript, TypeScript.

#### `MUTABLE_DEFAULT_ARG` — Mutable default argument (orta)
- **Tespit:** Python `def f(x=[])` veya `def f(x={})`.
- **Dil:** Python.

### 5.4 Güvenlik (1, ayrı UI bölümü)

#### `HARDCODED_SECRET` — Hardcoded gizli anahtar (yüksek)
- **Tespit:** AST'den string literalleri çıkar, regex tabanlı tarama (AWS, Stripe, GitHub token, JWT secret, connection string).
- **Dil:** Python, JavaScript, TypeScript.
- **UI:** Rapor sayfasında ayrı **🔒 Güvenlik Bulguları** kart bölümünde gösterilir.

### 5.5 Kalite (5)

#### `INEFFICIENT_STRING_CONCAT` — Verimsiz string birleştirme (düşük)
- **Tespit:** Loop içinde `s += ...` veya `+` ile birleştirme; `join` / template yok.
- **Dil:** Python, JavaScript, TypeScript.

#### `CIRCULAR_IMPORT` — Döngüsel import (düşük)
- **Tespit:** Modül A → B → A import zinciri (graph traversal).
- **Dil:** Python, JavaScript, TypeScript (`import`/`require` döngüleri).

#### `SHADOW_VARIABLE` — Gölge değişken (düşük)
- **Tespit:** İç scope'ta dış scope/built-in adıyla yeniden tanımlanan değişken.
- **Dil:** Python, JavaScript, TypeScript.

#### `DEAD_CODE` — Ölü kod (düşük)
- **Tespit:** Tanımlı ama hiçbir yerden çağrılmayan fonksiyon/sınıf (referans grafı boş). Test exclude.
- **Dil:** Python, JavaScript, TypeScript.

### 5.6 Plugin sistemi

Statik kural motoru plugin yapısı:

```python
# backend/analysis/static_rules/base.py
from typing import Literal

class StaticRule(ABC):
    code: str                # ör. "N1_QUERY"
    category: Literal["performance", "memory", "reliability", "security", "quality"]
    severity: Literal["high", "medium", "low"]
    severity_cap: Optional[str] = None   # ör. RACE_CONDITION için "medium"
    languages: list[str]   # ["python"] | ["javascript", "typescript"] | hepsi

    @abstractmethod
    def scan(self, ast_tree, file_path: str, source: str, language: str) -> list[IssueCandidate]: ...
```

Her örüntü ayrı dosya: `backend/analysis/static_rules/n1_query.py`, `unbounded_cache.py`, vb. (toplam 23 dosya).

---

## 6. Frontend (Next.js)

### 6.1 Sayfalar

| Route | İçerik |
|---|---|
| `/` | Landing: URL input + mod seçici + provider/model seçici |
| `/analyze/[jobId]` | Canlı analiz ekranı (4 ajan kartı + SSE log feed) |
| `/report/[jobId]` | Tam tanı raporu — yazdırılabilir |

### 6.2 Anahtar UX

**Landing (`/`):**
- Hero: "Repo'nun kod sağlığını ölç. Sunucunu yoran örüntüleri bul."
- URL input + "Tanı Başlat".
- 3 segment toggle: **Mod** (Statik / Hibrit / Derin).
  - **Tooltip (hover / focus):** Kullanıcı imleci bir mod düğmesinin üzerine getirdiğinde (veya klavye ile odakladığında), o modun ne işe yaradığını özetleyen bilgi kutucuğu görünür. Bileşen: `frontend/components/mode-tooltip.tsx` — Tailwind `group-hover` + `group-focus-within`; ek bağımlılık yok.
  - Tooltip, mod adının altında kısa özet + dört satırlık karşılaştırma tablosu gösterir: **Hız**, **Token**, **Kapsam**, **Doğruluk**.
  - Düğme üzerindeki kısa `hint` satırı (ör. "Hızlı · LLM yok") kalır; tooltip detaylı açıklamayı taşır.
  - Erişilebilirlik: `role="tooltip"`, `aria-describedby` ile düğmeye bağlı; okuyucu dostu özet metin.

| Mod | Tooltip özeti | Hız | Token | Kapsam | Doğruluk |
|---|---|---|---|---|---|
| **Statik** | Yalnızca kural motoru. En hızlı yol; LLM token tüketimi sıfır. CI/CD ve hızlı tarama için ideal. | ⚡⚡⚡ (< 5 sn / ~50 dosya) | 0 | 22 statik örüntü · Python, JS, TS | Orta — beklenmedik örüntüleri kaçırabilir |
| **Hibrit** *(varsayılan)* | Kural motoru aday bulguları üretir; LLM doğrulama ve etki analizi yapar. Dengeli hız ve doğruluk. | ⚡⚡ (~30–90 sn) | ~110K | Statik kurallar + LLM confirm · 4 ajan | Yüksek — genel kullanım için önerilen |
| **Derin** | Kaynak kod ve AST doğrudan LLM'e gider. En geniş kapsam; en yavaş ve en pahalı mod. | ⚡ (1–3 dk) | ~500K–900K | Tam kod + AST · beklenmedik örüntü avı | En yüksek bağlam — küçük-orta repolar için |
- 2 segment toggle: **Sağlayıcı** (Cerebras / Gemini).
- "Gelişmiş" panel: ajan başına model seçimi (Profiler, Etki, Cerrah, Hekimbaşı).
- 3 örnek repo butonu ("Hemen dene").
- **Sayfa altı — GitHub yönlendirmesi:** Footer'da GitHub ikonu ve **"GitHub — Kaynak kod"** butonu. Tıklandığında kullanıcı **doğrudan KodHekim proje deposuna** yönlendirilir: `https://github.com/MaNga-003/KodHekim` (`NEXT_PUBLIC_GITHUB_REPO_URL` env ile yapılandırılır; `.git` soneki opsiyonel). Yeni sekmede açılır (`target="_blank" rel="noopener noreferrer"`). Bileşen: `components/site-footer.tsx`.

**Analyze (`/analyze/[jobId]`):**
- 4 ajan kartı (Profiler, Etki Analisti, Cerrah, Hekimbaşı) — durum: `Pending → Running → Done`.
  - Statik mod'da Cerrah ve Hekimbaşı LLM bölümleri "skip" durumunda gösterilir.
- Sağ panel: canlı log feed (her SSE event).
- Üstte mod rozeti ("Mod: Hibrit") + provider rozeti ("Cerebras / gpt-oss-120b").
- Timer.
- Bitince otomatik `/report/[jobId]`.

**Report (`/report/[jobId]`):**
- Üstte: büyük sağlık skoru gauge (0–100, renkli) + **Kod Sağlığı Isı Haritası** (`components/report/code-heatmap.tsx`) — gauge'ın yanında / altında, GitHub katkı grafiği tarzı dosya matrisi.
  - Her hücre bir kaynak dosyayı temsil eder (`.py`, `.js`, `.jsx`, `.ts`, `.tsx`).
  - Renkler: **koyu yeşil** = sorunsuz · **sarı/amber** = düşük/orta verimsizlik · **turuncu/kırmızı** = kritik (yüksek severity, güvenlik veya `UNBOUNDED_CACHE` / `GLOBAL_ACCUMULATOR` / `HARDCODED_SECRET` vb.).
  - Hover tooltip: dosya yolu, kritik/orta/düşük sayıları, tahmini kaynak israfı özeti (ör. "Tahmini RAM İsrafı: Yüksek").
  - Veri: `issues` + `impacts` + backend `scanned_files` (temiz dosyalar yeşil hücre).
  - Teknoloji: saf Tailwind CSS grid (`repeat(auto-fill, minmax(11px, 11px))`) — ek chart kütüphanesi yok.
- Yanında 3 alt-rozet: Performans, Güvenlik, Kalite (mini gauge).
- "🖨️ Yazdır" butonu (`components/print-button.tsx` → otomatik PDF indirme).
- Sorun sayısı özeti.
- **🔒 Güvenlik Bulguları** kart bölümü (varsa) — kırmızı çerçeve, ayrı UI bandı.
- Top 3 öncelik kartı.
- Sorun listesi (performans/RAM/güvenilirlik/kalite — kategori başlığıyla gruplu):
  - Severity rengi, `code` rozeti, dosya:satır.
  - Açıklama + etki skoru rozeti + `impact_score`.
  - Etki boyutları (`impact_dimensions`) genişletilebilir detay.
  - **🩺 Dr. Cerrah'ın Çözüm Reçetesi** — sorun kartının altında genişletilebilir Markdown/metin alanı (`components/fix-recipe-panel.tsx`); numaralı adımlar, risk ve test önerisi. Statik modda "Çözüm reçetesi bu modda devre dışı" mesajı.
  - ~~"Düzeltmeyi göster" butonu~~ ve ~~Diff Viewer~~ kaldırıldı (unified diff üretimi yok).
- Yönetici özeti (3 paragraf, Hibrit/Derin'de LLM yazar).
- "Roadmap" — önceliklendirilmiş sorun listesi (düzeltme kodu yok; tanı odaklı).

### 6.3 Yazdırma desteği

```css
/* app/globals.css */
@media print {
  .no-print { display: none !important; }
  .issue-card { break-inside: avoid; }
  body { background: white; color: black; }
}
```

Rapor header'ına `components/print-button.tsx` ekle (`className="no-print"`). Butona basıldığında `lib/print-report.ts` tam rapor HTML'ini üretir; `lib/download-pdf.ts` (html2canvas + jsPDF) ile **`KodHekim-Tani-{jobId}.pdf`** otomatik indirilir — yazdırma diyaloğu açılmaz.

Yedek rota: `/report/[jobId]/print` aynı indirme akışını tetikler.

### 6.4 Tasarım

- **Dark mode default** (yazdırırken light).
- Renkler: Slate base + yeşil/sarı/kırmızı/mavi accent.
- Tipografi: Inter (UI) + JetBrains Mono (kod).
- Animasyon: ajan çalışırken pulsing dot.
- Mobile responsive.

### 6.5 Hız hedefi
- Landing < 1s
- SSE bağlantı kurulumu < 200ms
- Report tam render < 1.5s

---

## 7. Backend API

### 7.1 Endpoint'ler

```
POST /api/analyze
  Body: {
    "repo_url": "...",
    "mode": "static" | "hybrid" | "deep",
    "provider": "cerebras" | "gemini",
    "model_overrides": { ... }
  }
  Response: { "job_id": "abc123" }

GET /api/analyze/:job_id/stream    (SSE)
GET /api/report/:job_id            (JSON — issues, impacts, fixes, scanned_files[], report)
GET /api/models                    (mevcut sağlayıcı + model listesi)
```

> Web rapor sayfası tarayıcı print desteğiyle PDF üretir.

### 7.2 SSE Event Şeması

```json
{
  "event": "issue_found",
  "data": {
    "agent": "profiler",
    "issue": { ... },
    "timestamp": "2026-05-18T14:23:45Z"
  }
}
```

Event tipleri: `agent_started`, `agent_progress`, `agent_done`, `issue_found`, `impact_calculated`, `fix_generated`, `all_done`, `error`.

### 7.3 Job Yaşam Döngüsü

1. `POST /api/analyze` gelir.
2. Job ID üret (UUID).
3. Async task başlat (FastAPI `BackgroundTasks` + asyncio).
4. Repo'yu **sistem geçici dizinine** shallow clone et (`%TEMP%/kodhekim/{job_id}` — `MAX_REPO_SIZE_MB`). `backend/` altına klonlama yapma.
5. LangGraph orchestrator çalışır:
   - **Statik mod:** profiler_static → impact_heuristic → chief_heuristic (Cerrah skip).
   - **Hibrit:** profiler → impact_llm → fan_out_surgeon → chief.
   - **Derin:** profiler_deep → impact_llm → fan_out_surgeon → chief.
6. Her step SSE event yayar.
7. `result.json` kaydedilir.
8. Repo silinir.
9. SSE'ye `all_done`.

### 7.4 LangGraph State

```python
class AnalysisState(TypedDict):
    job_id: str
    repo_path: str
    language: Literal["python", "javascript", "typescript", "mixed"]
    mode: Literal["static", "hybrid", "deep"]
    provider: str
    model_overrides: dict[str, str]
    issues: list[Issue]
    impacts: dict[str, ImpactBreakdown]
    fix_recipes: dict[str, FixRecipe]
    report: Optional[FinalReport]
    events: list[Event]
```

Graph (Hibrit):
```
START → clone_repo → profiler → fan_out_impact → fan_out_surgeon → chief → END
```

Graph (Statik):
```
START → clone_repo → profiler_static → fan_out_impact_heuristic → chief_heuristic → END
```

Graph (Derin):
```
START → clone_repo → profiler_deep → fan_out_impact → fan_out_surgeon → chief → END
```

`fan_out_impact` ve `fan_out_surgeon` LangGraph `Send` API ile paralel (`MAX_CONCURRENT_AGENTS=5`).

---

## 8. Prompt Stratejisi

### 8.1 Genel kurallar
- Tüm prompt'lar `backend/prompts/` altında `.md` dosyaları.
- Sıcaklık: Profiler 0.1, Etki 0.2, Cerrah 0.3, Hekimbaşı 0.5, Derin 0.4.
- Structured output her zaman JSON schema.
- Her ajan için 2-3 few-shot örnek.

### 8.2 Token bütçesi (50 dosyalı orta repo)
| Mod | Total tokens (in+out) |
|---|---|
| Statik | 0 |
| Hibrit | ~110K |
| Derin | ~500K-900K |

### 8.3 Dosya listesi
```
prompts/
├── profiler_confirm.md
├── deep_mode.md
├── impact_analyst.md
├── surgeon.md              # Sözel çözüm reçetesi (fix_instruction_tr)
├── chief.md
├── examples/
│   ├── n1_query_confirm.json
│   ├── unbounded_cache_confirm.json
│   ├── surgeon_n1_query.json       # fix_instruction_tr örneği
│   ├── surgeon_missing_timeout.json
│   └── ...
└── system/
    └── safety.md
```

---

## 9. Geliştirici Roadmap'i (Tek seferde, sırayla)

> **Felsefe:** Sprint yok, gün yok. Bu roadmap baştan sona, kesintisiz takip edilir. Her faz öncekinin tamamlandığını varsayar; her fazın çıkış kriteri test edilebilir.

### Faz A — Foundation

**Yapılacaklar:**
1. Repo klasör yapısını oluştur (§11).
2. `.env.example` (§10).
3. `README.md` taslağı.
4. `frontend/`: `pnpm create next-app@latest` (App Router, TS, Tailwind).
5. `backend/`: `pyproject.toml`, bağımlılıklar:
   - `fastapi`, `uvicorn[standard]`, `sse-starlette`, `gitpython`
   - `tree-sitter`, `tree-sitter-python`, `tree-sitter-javascript`, `tree-sitter-typescript`
   - `pydantic`, `langgraph`
   - `cerebras-cloud-sdk`, `google-generativeai`
   - `python-dotenv`
6. `.gitignore`, ilk commit.

**Çıkış:** `pnpm dev` ve `uvicorn main:app --reload` çalışıyor.

### Faz B — Repo cloning + file walking

**Yapılacaklar:**
1. `backend/analysis/repo_cloner.py` — shallow clone, size limit, hata yönetimi.
2. `backend/analysis/file_walker.py` — `*.py`, `*.js`, `*.ts`, `*.tsx`, `*.jsx`; exclude list.
3. Birim test: Flask (Python), Express (JS), Nest (TS) örnek repolar.

**Çıkış:** CLI test doğru sayıda dosya indiriyor.

### Faz C — AST Parser ve Statik Kural Motoru

**Yapılacaklar:**
1. `backend/analysis/ast_parser.py` — Python `ast` + Tree-sitter (`tree-sitter-javascript`, `tree-sitter-typescript`); üç dil için birleşik arayüz.
2. `backend/analysis/static_rules/base.py` — `StaticRule` + `languages`.
3. **22 örüntü dosyasını** üç dil kapsamına göre yaz (dil-spesifik kurallar `languages` ile filtrelenir).
4. Her kural için unit test (pozitif + negatif; Python, JS, TS fixture'ları).
5. `ALL_RULES` registry.

**Çıkış:** `python -m backend.analysis.scan <repo_path>` aday sorun listesi döndürüyor.

### Faz D — LLM Provider Soyutlaması

**Yapılacaklar:**
1. `backend/llm/base.py`, Cerebras, Gemini, registry, `safe_json.py`.
2. `scripts/test_llm.py`.

**Çıkış:** Her iki sağlayıcı JSON döndürüyor.

### Faz E — Profiler (Hibrit mod)

**Yapılacaklar:**
1. `backend/agents/profiler.py` — `profiler_agent_hybrid(...)`.
2. `prompts/profiler_confirm.md` + few-shot.

**Çıkış:** 50 dosyalı repo'da < 60s, FP oranı < %20.

### Faz F — Statik mod yolu

**Yapılacaklar:**
1. `profiler_agent_static(...)`.
2. `impact_heuristic.py`, `chief_heuristic.py`.

**Çıkış:** Statik mod end-to-end < 5s.

### Faz G — Etki Analisti (LLM versiyon)

**Yapılacaklar:**
1. `backend/agents/impact_analyst.py`.
2. `backend/analysis/impact_heuristics.py`.
3. `prompts/impact_analyst.md`.

**Çıkış:** Her sorun için `impact_score` + Türkçe açıklama. Parasal alan yok.

### Faz H — Cerrah (Sözel Reçete Altyapısı)

**Yapılacaklar:**
1. `backend/agents/surgeon.py` — `fix_instruction_tr` üretimi.
2. `prompts/surgeon.md` + 3+ few-shot örnek (sözel reçete formatı).
3. Test: 5 farklı sorun tipi için LLM'in anlamlı, adımsal Türkçe yönergeler üretmesi (diff/patch doğrulaması yok).

**Çıkış:** >%80 oranında yapılandırılmış, uygulanabilir Türkçe reçete. Kod derleme/patch testi yok.

### Faz I — Hekimbaşı

**Yapılacaklar:**
1. `backend/agents/chief.py` — sağlık skoru, top 3, yönetici özeti.
2. `prompts/chief.md`.

**Çıkış:** `/api/report/:job_id` tam JSON döndürüyor.

### Faz J — Derin mod

**Yapılacaklar:**
1. `backend/analysis/ast_summary.py`.
2. `profiler_agent_deep(...)`.
3. `prompts/deep_mode.md` + token bütçesi.

**Çıkış:** Derin mod orta repo'da < 3 dakika.

### Faz K — LangGraph Orchestrator

**Yapılacaklar:**
1. `backend/agents/orchestrator.py` — 3 graph (statik/hibrit/derin), 4 ajan.
2. `Send` API ile fan-out.
3. Event emitter.

**Çıkış:** CLI tam pipeline çalışıyor.

### Faz L — FastAPI Endpoint'leri + SSE

**Yapılacaklar:**
1. `main.py`, `api/analyze.py`, `api/stream.py`, `api/report.py`, `api/models.py`.

**Çıkış:** `curl` ile endpoint'ler test edilebilir.

### Faz M — Frontend Sayfaları

**Yapılacaklar:**
1. **Landing:** URL + mod toggle + **mode tooltip'leri** + provider + gelişmiş panel + **footer GitHub linki** (`NEXT_PUBLIC_GITHUB_REPO_URL`).
2. `lib/api-client.ts`, `lib/sse-client.ts`.
3. **Analyze:** 4 ajan kartı + log feed.
4. **Report:** gauge, alt-rozetler, güvenlik kartı, sorun listesi (etki skorları), **🩺 Dr. Cerrah'ın Çözüm Reçetesi** panelleri, önce/sonra simülasyonu, yazdır.
5. Tailwind dark mode + print CSS.

**Çıkış:** Browser end-to-end: URL → analiz → rapor → yazdır.

### Faz N — Sertleştirme

**Yapılacaklar:**
1. Hatalı URL, private repo, boyut limiti.
2. LLM rate limit retry, bozuk JSON fallback.
3. SSE reconnect.
4. Derin mod token tavanı → dosya kırpma.

**Çıkış:** Düşman testi — sistem çökmüyor.

### Faz O — Demo & Pazarlama Özellikleri

**Yapılacaklar:**
1. `simulation.py` + simulate endpoint.
2. `agent-persona.tsx` (4 ajan).
3. `mode-comparison-card.tsx`, badge endpoint.
4. LLM düşünme stream'i, repo ön-tarama, auto scroll.
5. `cached_demos/` + "Hemen Dene" butonları.

**Çıkış:** Tüm demo özellikleri canlıda.

### Faz P — Pazarlama Materyalleri

**Yapılacaklar:**
1. `README.md`, `docs/pitch.md`, ekran görüntüleri, mimari diyagram.

**Çıkış:** Repo public için materyaller hazır.

### Faz Q — Deploy

**Yapılacaklar:**
1. Vercel + Render/Railway, env, CORS, smoke test.

**Çıkış:** Public URL çalışıyor.

---

## 10. Çevresel Değişkenler

`.env.example`:
```
# LLM Providers
CEREBRAS_API_KEY=
GEMINI_API_KEY=

# Defaults
DEFAULT_PROVIDER=cerebras
DEFAULT_MODE=hybrid

# Cerebras model defaults
CEREBRAS_DEFAULT_PROFILER=gpt-oss-120b
CEREBRAS_DEFAULT_IMPACT=gpt-oss-120b
CEREBRAS_DEFAULT_CHIEF=qwen-3-235b-a22b-instruct-2507
CEREBRAS_DEFAULT_DEEP=qwen-3-235b-a22b-instruct-2507

# Gemini model defaults
GEMINI_DEFAULT_PROFILER=gemini-2.5-flash
GEMINI_DEFAULT_IMPACT=gemini-2.5-flash
GEMINI_DEFAULT_CHIEF=gemini-2.5-pro
GEMINI_DEFAULT_DEEP=gemini-2.5-pro

# Limits
TMP_DIR=/tmp/kodhekim
MAX_REPO_SIZE_MB=100
MAX_FILES_TO_SCAN=200
MAX_CONCURRENT_AGENTS=5
MAX_DEEP_TOKENS=800000
SSE_HEARTBEAT_SEC=15

# Frontend (.env.local)
NEXT_PUBLIC_API_BASE=http://localhost:8000
NEXT_PUBLIC_GITHUB_REPO_URL=https://github.com/MaNga-003/KodHekim
```

---

## 11. Repo Yapısı

```
Kod-Hekim/
├── README.md
├── developer.md
├── .gitignore
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx
│   │   ├── analyze/[jobId]/page.tsx
│   │   └── report/[jobId]/page.tsx
│   ├── components/
│   │   ├── agent-persona.tsx
│   │   ├── agent-card.tsx
│   │   ├── issue-card.tsx
│   │   ├── fix-recipe-panel.tsx    # 🩺 Dr. Cerrah sözel reçete (§6.2)
│   │   ├── report/
│   │   │   └── code-heatmap.tsx    # 📋 Kod sağlığı ısı haritası (§6.2)
│   │   ├── health-gauge.tsx
│   │   ├── before-after-gauge.tsx
│   │   ├── sub-score-badge.tsx
│   │   ├── security-section.tsx
│   │   ├── mode-comparison-card.tsx
│   │   ├── mode-selector.tsx
│   │   ├── mode-tooltip.tsx          # Analiz modu hover açıklamaları
│   │   ├── site-footer.tsx           # GitHub repo linki
│   │   ├── provider-selector.tsx
│   │   └── print-button.tsx
│   └── lib/
│
├── backend/
│   ├── agents/
│   │   ├── orchestrator.py
│   │   ├── profiler.py
│   │   ├── impact_analyst.py
│   │   ├── impact_heuristic.py
│   │   ├── surgeon.py              # Sözel fix_instruction_tr
│   │   ├── chief.py
│   │   └── chief_heuristic.py
│   ├── analysis/
│   │   ├── ast_parser.py             # Python + JS + TS
│   │   ├── static_rules/             # 23 plugin
│   │   └── ...
│   └── prompts/
│       ├── profiler_confirm.md
│       ├── deep_mode.md
│       ├── impact_analyst.md
│       ├── surgeon.md                # Sözel reçete prompt'u
│       └── chief.md
│
└── docs/
```

---

## 12. Test ve Doğrulama Stratejisi

### Unit testler
- Her statik kural için pozitif + negatif örnek (Python, JS, TS fixture'ları).
- AST parser için 3 dilde örnek.
- `safe_json_parse` için LLM artefaktları.

### Entegrasyon testleri
- **Fixture repo'lar:**
  1. `fixtures/python_flask_bad/`
  2. `fixtures/javascript_express_bad/`
  3. `fixtures/typescript_nest_bad/`
  4. `fixtures/clean_repo/`
- Her fixture için: 3 mod'da çalıştır, beklenen sonuçla karşılaştır.

### Manuel test seti
- 5 farklı public GitHub repo (Flask, Django, Express, Next.js, TS util).

---

## 13. Karar Verilenler ✓

1. **İsim:** **KodHekim** ✓
2. **Ürün kapsamı:** **Tanı, etki analizi ve sözel çözüm reçetesi** — otomatik kod patch / unified diff üretimi yok ✓
3. **Ajan sayısı:** **4** (Profiler, Etki Analisti, Cerrah, Hekimbaşı) ✓
4. **Cerrah rolü:** Sözel, adımsal Türkçe reçete (`fix_instruction_tr`); diff/patch yok ✓
5. **Dil Desteği:** Python, JavaScript ve TypeScript ilk sürümden itibaren tam desteklenmektedir. ✓
6. **UI dili:** **Türkçe** ✓
7. **Landing GitHub linki:** Footer ikonu → `NEXT_PUBLIC_GITHUB_REPO_URL` ✓
8. **Analiz modu tooltip'leri:** Hover ile hız / token / doğruluk özeti ✓

---

## 14. Başarı Kriterleri

### Minimum (mutlaka)
- Public GitHub linkinden Python, JavaScript ve TypeScript repo analizleri yapılıyor.
- 22 örüntüden en az 12'si gerçek bir repo'da tespit ediliyor.
- Etki Analisti her sorun için somut teknik metrik üretiyor.
- Hekimbaşı: ana sağlık skoru + 3 alt-skor + top 3 öncelik.
- 3 analiz modu çalışıyor.
- Hem Cerebras hem Gemini seçilebiliyor.
- **🔒 Güvenlik Bulguları** ayrı UI bölümünde.
- **🎯 Önce/Sonra simülasyonu** çalışıyor.
- **👨‍⚕️ 4 ajan karakteri** görünüyor.
- **🩺 Dr. Cerrah'ın Çözüm Reçetesi** raporda sorun kartlarında görünüyor (Hibrit/Derin).
- Landing footer GitHub linki doğru repoya gidiyor.
- Mod tooltip'leri hover'da görünüyor.
- Canlı deploy erişilebilir.

### İdeal
- 22 örüntünün tamamı üç dilde tespit ediliyor.
- Tarayıcı "Yazdır" → temiz PDF.
- 200+ dosyalı repo 2 dakikada tamamlanıyor.
- Derin mod anlamlı bulgu üretiyor.
- Mod karşılaştırma kartı + badge endpoint canlıda.

### Stretch
- GitHub OAuth ile private repo.
- GitHub Action wrapper.
- Go/Rust/Java genişlemesi.

---

## 15. Risk Yönetimi

| Risk | Olasılık | Etki | Azaltma |
|---|---|---|---|
| LangGraph öğrenme eğrisi | Orta | Yüksek | Faz J'de basit POC; gerekirse manuel asyncio. |
| LLM rate limit | Düşük | Orta | İki sağlayıcı fallback. |
| Statik yanlış pozitif | Yüksek | Orta | LLM confirm; negatif test fixture'ları. |
| Repo çok büyük → timeout | Orta | Orta | `MAX_FILES_TO_SCAN`, dosya önceliklendirme. |
| SSE bağlantı kopması | Orta | Orta | Reconnect + polling fallback. |
| Tree-sitter Windows build | Düşük | Yüksek | Linux container tercih. |
| JS/TS AST farkları | Orta | Orta | Dil başına fixture testleri. |
| Derin mod token aşımı | Orta | Orta | Token tavanı + dosya kırpma. |
| Cerebras model deprecation | Orta | Düşük | Güncel model ID planı (Ek A). |

---

## 16. Demo, Simülasyon ve Pazarlama Özellikleri

### 16.1 Önce/Sonra Simülasyonu

Kullanıcı raporda sorunları seçer; sağlık skorunun giderilince nereye çıkacağını canlı görür (diff veya patch üretimi yok — salt skor simülasyonu).

```python
def simulate_post_fix_score(all_issues, accepted_issue_ids):
    remaining = [i for i in all_issues if i.id not in accepted_issue_ids]
    return health_score(remaining)
```

### 16.2 Hemen Dene — Önbelleklenmiş Demo Analizleri

- `backend/data/cached_demos/<slug>.json`
- Landing'de 3 örnek repo butonu
- `scripts/build_cached_demos.py`

### 16.3 Mod Karşılaştırma Metriği

Analiz sonunda Statik/Hibrit/Derin süre, token, bulgu sayısı karşılaştırması.

### 16.4 GitHub Badge

`GET /api/badge/:owner/:repo.svg` → `kodhekim score: 78/100`

### 16.5 1-Pager Pitch

`docs/pitch.md` — 4 ajan, 22 örüntü, 3 dil, 3 mod.

### 16.6 README.md

```markdown
# KodHekim 🩺

- 4 AI ajan (Dr. Müfettiş, Dr. Ölçücü, Dr. Cerrah, Dr. Hekimbaşı)
- 23 kod örüntüsü · Python, JavaScript, TypeScript
- 3 analiz modu · 2 LLM sağlayıcı
```

### 16.7 Ucuz Kazançlar

- **LLM düşünme stream'i** — analyze log feed
- **Repo ön-tarama** — `GET /api/inspect?url=...`
- **Auto scroll + highlight** — top 3 → issue kartı

### 16.8 Demo Guard

Bilinen demo repolar için cache önceliği; bilinmeyen repolarda sıkı limitler.

---

## 17. Son Söz

Bu döküman tek bir geliştiricinin baştan sona ilerlemesi için yazıldı. KodHekim **tanı ve etki analizi** ürünüdür; düzeltme kodu üretmez.

Kod yazarken hedef: **her ajan kendi başına çalışabilir**, **provider değiştirilebilir**, **örüntü eklenebilir**, **mod ayrılabilir**, **üç dil aktif analiz edilir**.

---

## Ek A — Cerebras model referansı (19 Mayıs 2026 itibarıyla)

| Model ID | Tür | Not |
|---|---|---|
| `gpt-oss-120b` | 120B genel amaçlı | En sağlam seçim |
| `llama3.1-8b` | 8B hızlı | ⚠️ Deprecate: 27 Mayıs 2026 |
| `qwen-3-235b-a22b-instruct-2507` | 235B reasoning | ⚠️ Deprecate: 27 Mayıs 2026 |
| `zai-glm-4.7` | Kod odaklı | GLM-4 ailesi |

**Güncelleme planı:** Deprecate modeller yerine güncel ID'ler (`llama-3.3-70b`, `qwen-3-32b` vb.) konacak. `scripts/check_cerebras_models.py` ile doğrulama.

**Hackathon submit penceresi:** 19 Mayıs 23:59 — bu tarihte tüm 4 model çalışır.
