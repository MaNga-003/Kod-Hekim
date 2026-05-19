# KodHekim — Developer Spesifikasyonu (v3)

> **BTK Akademi Hackathon 2026 — Finans Teması**
> "Çoklu AI ajan ekibiyle repoyu kazıyıp performans, RAM israfı, güvenlik ve kalite sorunlarını tespit eden, somut tanı raporu çıkaran **kod sağlığı tanı sistemi**."

**Son güncelleme:** 18 Mayıs 2026
**Geliştirici sayısı:** 1
**Çalışma modeli:** Sprintsiz, kesintisiz tek bir roadmap üzerinden baştan sona ilerleme. Geliştirici kendi ritmini kendi belirler; her faz tamamlandıktan sonra bir sonrakine geçilir.

---

## 0. Yönetici Özeti

### Problem
Kötü yazılmış bir döngü, gereksiz veritabanı sorgusu, sınırsız büyüyen cache, bellek sızıntısı, timeout'suz HTTP çağrısı — bunlar görünmez. Kod çalıştıkça sunucuyu yorar, RAM'i şişirir, latency'yi yükseltir, instance'ı upgrade etmeye iter. CTO "faturalar şişiyor" diye yakınır, kimse asıl suçluyu (kodu) bulamaz. Geleneksel linterlar style, güvenlik tarayıcıları CVE, APM araçları runtime'a bakar — kimse **kod örüntüsü → kaynak baskısı** bağlantısını kuran tanı çıkaramaz.

### Çözüm
Kullanıcı GitHub repo URL'sini yapıştırır. KodHekim'in 4 AI ajanı işbaşı yapar:

1. **Profiler** — Statik kural motoru + LLM ile **23 farklı pahalı/riskli kod örüntüsü** tespit eder (performans, RAM, güvenilirlik, güvenlik, kalite).
2. **Etki Analisti** — Her sorunun teknik etkisini ölçer (ekstra DB çağrısı sayısı, bellek sızıntı hızı, latency etkisi, restart riski). Parasal değil, somut teknik veri.
3. **Cerrah** — Her sorun için **sözel, mantıksal ve adımsal mimari çözüm önerisi** üretir (Türkçe reçete metni; unified diff / kod patch üretmez) + yan etki riski ve test önerisi.
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

▸ Önce/Sonra simülasyonu: tüm fix'ler uygulansa skor 62 → 91
```

### Ek özellikler (jüri için kritik)
- **🎯 Önce/Sonra simülasyonu** — Kullanıcı raporda fix'leri tick'ler, sağlık skorunun nereye çıkacağını canlı görür.
- **👨‍⚕️ Ajan karakterleri** — 4 ajanın her biri kişilik olarak konumlandırılır (avatar + Türkçe doktor unvanı + uzmanlık).
- **📊 Mod karşılaştırma** — Analiz sonunda Statik/Hibrit/Derin için süre + token + bulgu karşılaştırması.
- **🏷️ GitHub badge** — README'ye eklenebilen `kodhekim score: 78/100` SVG rozeti.
- **🧠 LLM düşünme stream'i, 🔎 repo ön-tarama, 🎯 auto-scroll** — polish dokunuşları.

> **MVP kapsamı:**
> - Python, JavaScript ve TypeScript dilleri tam olarak desteklenmektedir.
> - **UI sadece Türkçe**. İngilizce toggle yok.
> - **Demo cache (Hemen Dene) MVP sonrası** — Kullanıcı doğrudan kendi repo URL'sini yapıştırarak başlar.

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
│  │ Mod seç  │   │                 │   │  Düzeltmeler         │ │
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
│  │(gitpython) │  │(ast, tree-  │  │ (23 örüntü plugin)       │ │
│  │            │  │ sitter)     │  │                          │ │
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
| Static Analysis | `ast` (Python) + `tree-sitter-python`, `tree-sitter-javascript`, `tree-sitter-typescript` | AST düzeyinde precision; Python, JavaScript, TypeScript |
| Live Updates | Server-Sent Events (SSE) | WebSocket'ten basit, yeterli |
| Repo Cloning | `gitpython` + shallow clone (depth=1) | Hız |
| State/Cache | In-memory dict (job_id → state) | MVP için yeterli, Redis opsiyonel |
| Rapor formatı | **Web rapor + tarayıcı "Yazdır"** | PDF üretimi yok; CSS `@media print` yeterli |
| Deploy | Vercel (frontend) + Render (backend) | Ücretsiz tier |

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
| `zai-glm-4.7` | Kod analizi & üretimi | GLM-4 ailesi, kod için güçlü |

> ⚠️ **Hackathon teslim tarihi 19 Mayıs**, deprecate tarihi 27 Mayıs. Submit anında 4'ü de çalışır. MVP sonrası `llama3.1-8b` ve `qwen-3-235b-a22b-instruct-2507` yerine güncel ID'leri (`llama-3.3-70b`, `qwen-3-32b` veya benzeri) koymak gerekir. Doc Ek A'da detay.

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
│                                              │
│  Sağlayıcı:                                  │
│  ⦿ Cerebras    ○ Gemini                      │
│                                              │
│  ▸ Gelişmiş: Ajan başına model               │
│    Profiler:     [gpt-oss-120b ▾]            │
│    Etki:         [gpt-oss-120b ▾]            │
│    Cerrah:       [zai-glm-4.7 ▾]             │
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
    "surgeon": "zai-glm-4.7",
    "chief": "qwen-3-235b-a22b-instruct-2507",
    "deep_mode": "gemini-2.5-pro"
  }
}
```

---

## 3. Üç Analiz Modu

### 3.1 Statik mod
Yalnızca kural motoru, LLM yok. Hız: 50 dosyalı repo < 5 saniye. Token tüketimi: 0.

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

Token tüketimi: ~100K (~50 dosyalı orta boy Python repo).

### 3.3 Derin mod (LLM-Direct)

**Amaç:** Statik kural motorunun yakalayamadığı **beklenmedik örüntüleri** keşfetmek. LLM kendi bilgisiyle analiz eder.

**Akış:**
1. Repo dosyalarını yürü (tıpkı diğer modlarda).
2. Her dosya için **özetlenmiş AST + ham kod** çıkar.
   - "Özetlenmiş AST": fonksiyon imzaları + class yapısı + import grafiği + kontrol akışı outline (`backend/analysis/ast_summary.py` tarafından üretilir).
3. **Tek bir büyük prompt** halinde LLM'e gönder:
   - Sistem mesajı: "Aşağıdaki repo'da kaynak (CPU/RAM/I/O/güvenlik) tüketen örüntüleri bul. Bilinen 23 örüntü dışında da arayabilirsin."
   - Eklenecek: 23 örüntü listesi (referans), repo özet AST, *seçilmiş* tam kod dosyaları (en büyük 10 + entry point).
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

**Görev:** 23 örüntüyü tespit etmek (mod'a göre LLM confirm var/yok).

**Girdi:** Repo klasör yolu, dil(ler), analiz modu.

**İşlem akışı (Hibrit):**
1. Dosyaları yürü (`*.py`, `*.js`, `*.ts` — `node_modules`, `venv`, `.git`, `dist`, `build`, `.next`, `__pycache__` hariç).
2. Her dosya için AST çıkar.
3. **Statik kural motoru** ile aday sorunları işaretle.
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

**Tasarım kararı:** Cerrah unified diff veya otomatik kod patch'i üretmez. Riskli otomatik kod değişikliği yerine geliştiriciye **mimari yönlendirme** sunar — güvenli ve esnek bir "sözel danışman" modeli.

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
  "fix_instruction_tr": "1. Döngü içindeki tekil sorguları kaldır.\n2. Tüm user_id'leri topla.\n3. Tek batch sorgu ile Post'ları çek.\n4. Sonuçları bellekte user_id'ye göre grupla.",
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
- **Top 3 öncelik** (en yüksek ROI'li düzeltmeler).
- **3 paragraf yönetici özeti** — LLM ile yazılır (Hibrit/Derin modda).
- **Geliştirici roadmap'i** — öncelik sıralı düzeltme listesi.

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
        (iss, iss.impact_score / max(0.25, fix.remediation_effort_hours))
        for iss, fix in items
    ]
    return sorted(scored, key=lambda x: -x[1])[:3]
```

---

## 5. Tespit Edilen Örüntüler (23 örüntü — Python, JS, TS)

Kategoriler: **Performans (8)**, **RAM/Bellek (5)**, **Güvenilirlik (4)**, **Güvenlik (1, ayrı UI bölümü)**, **Kalite (5)**.

Her örüntü `StaticRule.languages` ile hangi dillerde aktif olduğunu belirtir. Tree-sitter ve `ast` parser'ları üç dilde de aynı plugin arayüzünü kullanır.

### 5.1 Performans (8)

#### `N1_QUERY` — N+1 veritabanı sorgusu (yüksek)
- **Tespit:** Loop içinde DB call (`.query`, `.filter`, `.objects.get`, `.find`).
- **Dil:** Python (SQLAlchemy/Django ORM), JS (Sequelize/Prisma).
- **Düzeltme yönü:** `select_related` / `joinedload` / batch fetch.

#### `SYNC_IN_ASYNC` — Async fonksiyonda blocking call (yüksek)
- **Tespit:** `async def` içinde `time.sleep`, `requests.get/post`, sync `open()`.
- **Dil:** Python, JS (`async function` + senkron `fs.readFileSync`).

#### `MISSING_INDEX_HINT` — İndex eksik sorgu (orta)
- **Tespit:** Aynı alan üzerinde >3 yerde `.filter(field=X)` ama model'de index yok.
- **Dil:** Python ORM.

#### `O_N_SQUARED` — İç içe O(n²) loop (düşük-orta)
- **Tespit:** İç içe iki for loop, aynı koleksiyona ref.
- **Dil:** Tüm.

#### `LARGE_PAYLOAD` — Pagination'sız büyük yanıt (orta)
- **Tespit:** Route handler içinde `.all()`, pagination/limit yok.
- **Dil:** Python (FastAPI/Flask + ORM), JS (Express + ORM).

#### `REPEATED_COMPUTE` — Loop içinde tekrar hesaplama (düşük)
- **Tespit:** Loop içinde sabit argümanla aynı pure fonksiyon çağrısı.
- **Dil:** Tüm.

#### `OVERFETCH_COLUMNS` — Gereksiz kolon çekme (orta)
- **Tespit:** `SELECT *` veya `.all()` üzerinden model, sonra sadece 1-2 alan kullanımı (data-flow analizi).
- **Dil:** Python ORM.

#### `MISSING_TIMEOUT` — Timeout'suz dış çağrı (yüksek)
- **Tespit:** `requests.get/post`, `httpx.get/post`, `urllib.request.urlopen` çağrısı timeout kwarg'ı olmadan; JS `fetch` AbortController yok.
- **Dil:** Python öncelik, JS.

### 5.2 RAM / Bellek (5)

#### `MEMORY_LEAK_LISTENER` — Event listener sızıntısı (orta)
- **Tespit:** `addEventListener` / `on('event')` kaydı var, karşılık gelen `removeListener` / `off` yok; DOM veya EventEmitter birikimi.
- **Dil:** JavaScript, TypeScript (Node.js EventEmitter dahil).

#### `UNCLOSED_RESOURCE` — Açık kalan resource (düşük)
- **Tespit:** `open()` / `socket()` var, `with` bloğu içinde değil, `.close()` yok.
- **Dil:** Python öncelik.

#### `UNBOUNDED_CACHE` — Sınırsız cache (yüksek) ⭐ YENİ
- **Tespit:**
  - `@lru_cache(maxsize=None)` veya `@lru_cache()` (default unbounded değil ama hatırlatma)
  - `@cache` decorator (`functools.cache`) — kalıcı sınırsız
  - Modül seviyesinde `_cache = {}` + içinde `_cache[key] = value` ama silme/eviction yok
- **Dil:** Python öncelik, JS (Map kullanımı + eviction yok).
- **Etki:** Süresiz RAM büyümesi → OOM.

#### `GLOBAL_ACCUMULATOR` — Global biriktirme (yüksek) ⭐ YENİ
- **Tespit:** Modül seviyesinde liste/dict tanımı + handler/fonksiyon içinde `.append()` / `[key] =`. Tahliye yok.
- **Dil:** Python, JS.
- **Etki:** Klasik bellek sızıntısı, sunucu zamanla şişer.

#### `LIST_OVER_GENERATOR` — Generator yerine liste (düşük) ⭐ YENİ
- **Tespit:** `[expr for x in big_iter]` ama sonuç sadece `for ... in result:` ile iter ediliyor (yani liste tutmaya gerek yok).
- **Dil:** Python.
- **Etki:** Peak RAM kullanımı 2-10x artar (büyük koleksiyonlarda).

#### `LOAD_FULL_FILE` — Dosyayı tek seferde yükleme (düşük-orta) ⭐ YENİ
- **Tespit:** `f.read()` veya `f.readlines()` — streaming (`for line in f:`) yerine.
- **Dil:** Python öncelik, JS (`readFileSync`).
- **Etki:** Büyük dosyada peak RAM dosya boyutuna eşitlenir.

### 5.3 Güvenilirlik (4)

#### `UNHANDLED_EXCEPTION` — Yakalanmayan istisna (orta)
- **Tespit:** Route handler'da try/except yok ve içeride raise edebilecek çağrı var (`requests`, `json.loads`, DB call).
- **Dil:** Python öncelik.

#### `RACE_CONDITION` — Yarış durumu (orta, dar kapsam)
- **Tespit:** Sadece şu iki dar pattern:
  1. Global/module-level mutable üzerinde async fonksiyon içinden mutate (lock/`asyncio.Lock` yok).
  2. Class attribute üzerinde `+=`, `.append()` eşzamanlı erişim ipucu.
- **Dil:** Python (asyncio).
- **Not:** Severity tavanı `medium`. LLM confirm kritik. Statik mod'da Profiler bu örüntüyü `low` severity ile işaretler (yanlış pozitif maliyetini düşürmek için).

#### `DEEP_RECURSION` — Derin recursion (düşük)
- **Tespit:** Fonksiyon kendisini çağırır, base case yok veya input'a göre garantili değil; veya zincir > 3 fonksiyon.
- **Dil:** Tüm.

#### `MUTABLE_DEFAULT_ARG` — Mutable default argument (orta)
- **Tespit:** Python `def f(x=[])` veya `def f(x={})`.
- **Dil:** Python.

### 5.4 Güvenlik (1, ayrı UI bölümü)

#### `HARDCODED_SECRET` — Hardcoded gizli anahtar (yüksek)
- **Tespit:** AST'den string literalleri çıkar, regex tabanlı tarama:
  - AWS access key (`AKIA[0-9A-Z]{16}`)
  - AWS secret (`[A-Za-z0-9/+=]{40}` + context anahtarı)
  - Stripe key (`sk_live_[0-9a-zA-Z]{24,}`)
  - GitHub token (`ghp_[0-9a-zA-Z]{36}`)
  - JWT secret atama (`SECRET_KEY = "..."` 8+ karakter)
  - Generic API key atama (`API_KEY|api_key|TOKEN|password = "..."`)
  - Connection string (`postgres://user:pass@`, `mongodb://user:pass@`)
- **Dil:** Tüm.
- **Etki:** Etki Analisti git geçmişini kontrol eder (commit'e işlenmiş mi → kalıcı sızıntı vs. sadece çalışma dizininde mi).
- **UI:** Rapor sayfasında ayrı **🔒 Güvenlik Bulguları** kart bölümünde gösterilir. Sağlık skorunda **güvenlik alt-skoru** etkilenir.

### 5.5 Kalite (5)

#### `INEFFICIENT_STRING_CONCAT` — Verimsiz string birleştirme (düşük)
- **Tespit:** Loop içinde `s += ...`; `"".join()` veya StringBuilder yok.
- **Dil:** Python, JS.

#### `CIRCULAR_IMPORT` — Döngüsel import (düşük)
- **Tespit:** Modül A → B → A import zinciri (graph traversal).
- **Dil:** Python.

#### `SHADOW_VARIABLE` — Gölge değişken (düşük)
- **Tespit:** İç scope'ta dış scope/built-in adıyla yeniden tanımlanan değişken.
- **Dil:** Python, JS.

#### `DEAD_CODE` — Ölü kod (düşük)
- **Tespit:** Tanımlı ama hiçbir yerden çağrılmayan fonksiyon/sınıf (referans grafı boş). Test ve `__init__.py` exclude.
- **Dil:** Python öncelik.

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
    languages: list[str]

    @abstractmethod
    def scan(self, ast_tree, file_path: str, source: str) -> list[IssueCandidate]: ...
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
  - **Tooltip (hover / focus):** Kullanıcı imleci bir mod düğmesinin üzerine getirdiğinde, o modun ne işe yaradığını özetleyen bilgi kutucuğu görünür. Bileşen: `frontend/components/mode-tooltip.tsx` (Tailwind `group-hover` + `group-focus-within`).
  - Tooltip içeriği: kısa özet paragraf + **Hız**, **Token**, **Kapsam**, **Doğruluk** satırları.
  - **Statik:** Yalnızca kural motoru · ⚡⚡⚡ · 0 token · 23 örüntü · orta doğruluk.
  - **Hibrit** *(varsayılan):* Kural + LLM confirm · ⚡⚡ · ~80K token · 3 ajan · yüksek doğruluk.
  - **Derin:** Kod + AST → LLM · ⚡ · ~500K–900K token · en geniş kapsam · küçük-orta repo.
- 2 segment toggle: **Sağlayıcı** (Cerebras / Gemini).
- "Gelişmiş" panel: ajan başına model seçimi.
- 3 örnek repo butonu ("Hemen dene").
- **Sayfa altı — GitHub yönlendirmesi:** Footer'da GitHub ikonu ve **"GitHub — Kaynak kod"** butonu. Tıklandığında kullanıcı **doğrudan KodHekim proje deposuna** yönlendirilir: `https://github.com/MaNga-003/KodHekim` (`NEXT_PUBLIC_GITHUB_REPO_URL` env ile yapılandırılır). Yeni sekmede açılır (`target="_blank" rel="noopener noreferrer"`). Bileşen: `components/site-footer.tsx`.

**Analyze (`/analyze/[jobId]`):**
- 4 ajan kartı (Profiler, Etki Analisti, Cerrah, Hekimbaşı) — durum: `Pending → Running → Done`.
  - Statik mod'da Cerrah ve Hekimbaşı LLM bölümleri "skip" durumunda gösterilir.
- Sağ panel: canlı log feed (her SSE event).
- Üstte mod rozeti ("Mod: Hibrit") + provider rozeti ("Cerebras / gpt-oss-120b").
- Timer.
- Bitince otomatik `/report/[jobId]`.

**Report (`/report/[jobId]`):**
- Üstte: büyük sağlık skoru gauge (0–100, renkli).
- Yanında 3 alt-rozet: Performans, Güvenlik, Kalite (mini gauge).
- "🖨️ Yazdır" butonu (`window.print()`).
- Sorun sayısı özeti.
- **🔒 Güvenlik Bulguları** kart bölümü (varsa) — kırmızı çerçeve, ayrı UI bandı.
- Top 3 öncelik kartı.
- Sorun listesi (performans/RAM/güvenilirlik/kalite — kategori başlığıyla gruplu):
  - Severity rengi, `code` rozeti, dosya:satır.
  - Açıklama + etki rozeti.
  - **🩺 Dr. Cerrah'ın Çözüm Reçetesi** — sorun kartının altında genişletilebilir Markdown/metin alanı (`components/fix-recipe-panel.tsx`); numaralı adımlar, risk ve test önerisi. Statik modda "Çözüm reçetesi bu modda devre dışı" mesajı.
- Yönetici özeti (3 paragraf, Hibrit/Derin'de LLM yazar).
- "Roadmap" — önceliklendirilmiş yapılacaklar listesi.

### 6.3 Yazdırma desteği

```css
/* app/globals.css */
@media print {
  .no-print { display: none !important; }
  .issue-card { break-inside: avoid; }
  body { background: white; color: black; }
  /* Dark mode kapanır, kontrast optimize edilir */
}
```

Header'a `<button class="no-print">🖨️ Yazdır</button>` ekle, `onClick={() => window.print()}`.

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
GET /api/report/:job_id            (JSON)
GET /api/models                    (mevcut sağlayıcı + model listesi)
```

> ⚠️ Önceki spec'teki `GET /api/report/:job_id/pdf` **kaldırıldı**. Web rapor sayfası tarayıcı print desteğiyle PDF üretir.

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
4. Repo'yu `/tmp/jobs/{job_id}` altına shallow clone et (`MAX_REPO_SIZE_MB`).
5. LangGraph orchestrator çalışır:
   - **Statik mod:** profiler_static → impact_heuristic → chief_heuristic (Cerrah skip).
   - **Hibrit:** profiler → impact_llm → surgeon → chief.
   - **Derin:** profiler_deep → impact_llm → surgeon → chief.
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
    fixes: dict[str, FixSuggestion]
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

`fan_out_*` LangGraph `Send` API ile paralel (`MAX_CONCURRENT_AGENTS=5`).

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
├── deep_mode.md            # Derin mod için
├── impact_analyst.md
├── surgeon.md
├── chief.md
├── examples/
│   ├── n1_query_confirm.json
│   ├── unbounded_cache_confirm.json
│   ├── n1_query_surgeon.json
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
3. `README.md` taslağı — ürünün ne yaptığını anlatan 1-2 paragraf + "geliştiriliyor" notu. Faz P'de şişirilecek.
4. `frontend/`: `pnpm create next-app@latest` (App Router, TS, Tailwind).
5. `backend/`: `pyproject.toml`, sanal ortam, bağımlılıklar:
   - `fastapi`, `uvicorn[standard]`, `sse-starlette`, `gitpython`
   - `tree-sitter`, `tree-sitter-python`, `tree-sitter-javascript`, `tree-sitter-typescript`
   - `pydantic`, `langgraph`
   - `cerebras-cloud-sdk`, `google-generativeai`
   - `python-dotenv`
6. `.gitignore`, ilk commit.

**Çıkış:** `pnpm dev` ve `uvicorn main:app --reload` çalışıyor; `README.md` placeholder ile mevcut.

### Faz B — Repo cloning + file walking

**Yapılacaklar:**
1. `backend/analysis/repo_cloner.py` — shallow clone, size limit, hata yönetimi (private/404).
2. `backend/analysis/file_walker.py` — extension filter, exclude list, file count limit.
3. Birim test: 3 örnek repo (public Flask, public Express, kasıtlı kötü repo).

**Çıkış:** CLI test: `python -m backend.analysis.repo_cloner <url>` doğru sayıda dosya iniyor.

### Faz C — AST Parser ve Statik Kural Motoru

**Yapılacaklar:**
1. `backend/analysis/ast_parser.py` — Python `ast` + Tree-sitter (`tree-sitter-javascript`, `tree-sitter-typescript`); üç dil için birleşik arayüz.
2. `backend/analysis/static_rules/base.py` — `StaticRule` arayüzü.
3. **23 örüntü dosyasını** üç dil kapsamına göre yaz:
   - Performans (8): `n1_query`, `sync_in_async`, `missing_index_hint`, `o_n_squared`, `large_payload`, `repeated_compute`, `overfetch_columns`, `missing_timeout`
   - RAM (4): `unclosed_resource`, `unbounded_cache`, `global_accumulator`, `list_over_generator`, `load_full_file` *(toplam 5)*
   - Güvenilirlik (4): `unhandled_exception`, `race_condition`, `deep_recursion`, `mutable_default_arg`
   - Güvenlik (1): `hardcoded_secret`
   - Kalite (4): `inefficient_string_concat`, `circular_import`, `shadow_variable`, `dead_code`
4. Her kural için unit test (pozitif + negatif örnek).
5. `__init__.py` — `ALL_RULES` registry.

**Çıkış:** `python -m backend.analysis.scan <repo_path>` aday sorun listesi döndürüyor; testler yeşil.

> **İpucu:** Her kuralı yazarken önce **negatif örnek** (false positive) yazın → precision'ı erken kalibre edersiniz.

### Faz D — LLM Provider Soyutlaması

**Yapılacaklar:**
1. `backend/llm/base.py` — ABC + TypedDict.
2. `backend/llm/cerebras_provider.py` — modeller, `complete()`, JSON schema, rate-limit retry.
3. `backend/llm/gemini_provider.py` — aynı.
4. `backend/llm/registry.py`, `backend/llm/safe_json.py`.
5. Manuel test script: `scripts/test_llm.py`.

**Çıkış:** Her iki sağlayıcı JSON çağrısına dönüş veriyor; `tokens_used`, `latency_ms` doğru.

### Faz E — Profiler (Hibrit mod)

**Yapılacaklar:**
1. `backend/agents/profiler.py` — `profiler_agent_hybrid(...)`.
2. `prompts/profiler_confirm.md`.
3. JSON schema: `{"confirmed_issues": [...]}`.
4. Few-shot örnekler.
5. Manuel test: kasıtlı kötü repo'da çalıştır, false-positive oranını gözle ölç.

**Çıkış:** 50 dosyalı repo'da < 60s, FP oranı < %20.

### Faz F — Statik mod yolu

**Yapılacaklar:**
1. `backend/agents/profiler.py` içinde `profiler_agent_static(...)` — LLM atlanır.
2. `backend/agents/impact_heuristic.py` — heuristic-only impact, sabit Türkçe template.
3. `backend/agents/chief_heuristic.py` — heuristic-only rapor (LLM özet yok).

**Çıkış:** Statik mod end-to-end < 5s, çıktı şeması Hibrit ile aynı.

### Faz G — Etki Analisti (LLM versiyon)

**Yapılacaklar:**
1. `backend/agents/impact_analyst.py`.
2. `backend/analysis/impact_heuristics.py` — örüntü tipine göre sayısal metrik üretimi (AST'den).
3. `prompts/impact_analyst.md` — Türkçe somut etki cümlesi.
4. JSON schema (§4.2).

**Çıkış:** Her sorun için `impact_score` + Türkçe açıklama. **Parasal alan yok** (kod taramayla doğrula).

### Faz H — Cerrah (Sözel Reçete Altyapısı)

**Yapılacaklar:**
1. `backend/agents/surgeon.py` — `fix_instruction_tr` üretimi.
2. `prompts/surgeon.md` + 3+ few-shot örnek (sözel reçete formatı).
3. Test: 5 farklı sorun tipi için LLM'in anlamlı, adımsal Türkçe yönergeler üretmesi (diff/patch doğrulaması yok).

**Çıkış:** >%80 oranında yapılandırılmış, uygulanabilir Türkçe reçete. Kod derleme/patch testi yok.

### Faz I — Hekimbaşı

**Yapılacaklar:**
1. `backend/agents/chief.py` — sağlık skoru (3 alt skor dahil), top 3, yönetici özeti.
2. `prompts/chief.md`.

**Çıkış:** `/api/report/:job_id` tam yapılandırılmış JSON döndürüyor.

### Faz J — Derin mod

**Yapılacaklar:**
1. `backend/analysis/ast_summary.py` — repo özetlenmiş AST üretici.
2. `backend/agents/profiler.py` içinde `profiler_agent_deep(...)`.
3. `prompts/deep_mode.md`.
4. Token bütçesi kontrolü (`MAX_DEEP_TOKENS`); aşılırsa dosya kırpma.
5. Test: küçük bir kötü repo üzerinde Derin mod çalıştır, gözle değerlendir.

**Çıkış:** Derin mod orta repo'da < 3 dakika, anlamlı bulgu üretiyor.

### Faz K — LangGraph Orchestrator

**Yapılacaklar:**
1. `backend/agents/orchestrator.py` — 3 graph (statik/hibrit/derin).
2. `Send` API ile fan-out.
3. Event emitter (in-memory `asyncio.Queue` per job_id).

**Çıkış:** CLI: `python -m backend.agents.orchestrator <url> --mode hybrid` tam pipeline çalışıyor.

### Faz L — FastAPI Endpoint'leri + SSE

**Yapılacaklar:**
1. `main.py` — FastAPI + CORS.
2. `api/analyze.py` — POST, BackgroundTasks.
3. `api/stream.py` — SSE (`sse-starlette`).
4. `api/report.py`, `api/models.py`.
5. Heartbeat, env config.

**Çıkış:** `curl` ile her endpoint test edilebilir; SSE 5 dakika düşmüyor.

### Faz M — Frontend Sayfaları

**Yapılacaklar:**
1. **Landing:** URL input + mod toggle (Statik/Hibrit/Derin) + provider toggle + "Gelişmiş" panel.
2. `lib/api-client.ts`, `lib/sse-client.ts`.
3. **Analyze:** 4 ajan kartı + log feed + mod rozeti.
4. **Report:**
   - Ana sağlık skoru gauge + 3 alt-rozet (Performans/Güvenlik/Kalite).
   - 🔒 Güvenlik Bulguları kartı.
   - Sorun listesi (kategoriye göre gruplu).
   - **🩺 Dr. Cerrah'ın Çözüm Reçetesi** panelleri (`fix-recipe-panel.tsx`).
   - **"🖨️ Yazdır" butonu** + `@media print` CSS.
5. Tailwind dark mode + print override.

**Çıkış:** Browser end-to-end: URL → analiz → rapor → yazdır.

### Faz N — Sertleştirme

**Yapılacaklar:**
1. Hatalı URL → 400 friendly mesaj.
2. Private/404 repo → "Public repo gerekli".
3. Repo > MAX_SIZE → 413.
4. Dosya > MAX_FILES → en büyükleri öncelikle al + uyarı.
5. LLM rate limit → exponential backoff (3 retry).
6. LLM bozuk JSON → `safe_json_parse` + 1 retry + fallback.
7. SSE kopması → reconnect + polling fallback.
8. Cerrah boş veya kısa reçete → frontend'de "Reçete üretilemedi" graceful mesajı.
9. Derin mod token tavanı aşılırsa → uyar + dosya kırp.

**Çıkış:** "Düşman" testi: bozuk URL, büyük repo, ağ kesinti simülasyonu — sistem çökmüyor.

### Faz O — Demo & Pazarlama Özellikleri

**Yapılacaklar:**
1. `backend/analysis/simulation.py` — `simulate_post_fix_score()` (§16.1).
2. `POST /api/report/:job_id/simulate` endpoint.
3. Frontend: `components/before-after-gauge.tsx` + her issue card'a checkbox + debounce'lu fetch.
4. `components/agent-persona.tsx` — Dr. Müfettiş, Dr. Ölçücü, Dr. Cerrah, Dr. Hekimbaşı avatarları (§4.0).
5. Analyze ve Report sayfalarındaki ajan referanslarını persona bileşeniyle değiştir.
6. `backend/analysis/mode_comparison.py` + `components/mode-comparison-card.tsx` (§16.3).
7. `backend/api/badge.py` — `GET /api/badge/:owner/:repo.svg` (§16.4).
8. Ucuz kazançlar (§16.7): LLM düşünme stream'i, repo ön-tarama, auto scroll + highlight.

> Demo cache (§16.2) MVP sonrasına bırakıldı, bu fazda yok.

**Çıkış:** Rapor sayfasında checkbox'lar skor güncelliyor; ajan karakterleri görünüyor; badge endpoint geçerli SVG dönüyor; mod karşılaştırma kartı raporda var.

### Faz P — Pazarlama Materyalleri

**Yapılacaklar:**
1. `README.md` (§16.6) — repo public olduğunda ilk görülecek satış belgesi.
2. `docs/pitch.md` 1-pager (§16.5) — submit'e ek materyal.
3. 3 ekran görüntüsü çek (landing, analyze, report) — `docs/screenshots/`.
4. Basit mermaid mimari diyagramını `docs/architecture.md` içine.
5. Basit logo (emoji 🩺 yeterli, ya da hızlı SVG).

**Çıkış:** Repo public yapıldığında README + pitch.md + screenshots hazır.

### Faz Q — Deploy

**Yapılacaklar:**
1. Frontend → Vercel; env: `NEXT_PUBLIC_API_BASE`.
2. Backend → Render/Railway; `Dockerfile` (Python 3.11-slim + `build-essential`).
3. Env: API key'ler, limitler, demo guard.
4. CORS whitelist.
5. Production smoke test:
   - 3 demo butonu çalışıyor mu?
   - Gerçek bir public repo analiz olabiliyor mu?
   - Badge endpoint SVG dönüyor mu?
   - Önce/sonra simülasyonu canlıda mı?

**Çıkış:** Public URL gerçek repo analizi yapıyor; tüm demo özellikleri canlıda.

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
CEREBRAS_DEFAULT_SURGEON=zai-glm-4.7
CEREBRAS_DEFAULT_CHIEF=qwen-3-235b-a22b-instruct-2507
CEREBRAS_DEFAULT_DEEP=qwen-3-235b-a22b-instruct-2507

# Gemini model defaults
GEMINI_DEFAULT_PROFILER=gemini-2.5-flash
GEMINI_DEFAULT_IMPACT=gemini-2.5-flash
GEMINI_DEFAULT_SURGEON=gemini-2.5-pro
GEMINI_DEFAULT_CHIEF=gemini-2.5-pro
GEMINI_DEFAULT_DEEP=gemini-2.5-pro

# Limits
TMP_DIR=/tmp/kodhekim
MAX_REPO_SIZE_MB=100
MAX_FILES_TO_SCAN=200
MAX_CONCURRENT_AGENTS=5
MAX_DEEP_TOKENS=800000
SSE_HEARTBEAT_SEC=15

# Frontend (separate .env.local)
NEXT_PUBLIC_API_BASE=http://localhost:8000
NEXT_PUBLIC_GITHUB_REPO_URL=https://github.com/MaNga-003/KodHekim
```

---

## 11. Repo Yapısı

```
Kod-Hekim/
├── README.md
├── developer.md                    # bu döküman
├── .gitignore
├── docker-compose.yml              # opsiyonel
│
├── frontend/                       # Next.js 14
│   ├── package.json
│   ├── app/
│   │   ├── page.tsx                # Landing
│   │   ├── analyze/[jobId]/page.tsx
│   │   ├── report/[jobId]/page.tsx
│   │   └── globals.css             # @media print dahil
│   ├── components/
│   │   ├── agent-persona.tsx       # Dr. Müfettiş/Ölçücü/Cerrah/Hekimbaşı (§4.0)
│   │   ├── agent-card.tsx          # persona wrapper + durum
│   │   ├── issue-card.tsx          # checkbox dahil (önce/sonra)
│   │   ├── fix-recipe-panel.tsx    # 🩺 Dr. Cerrah sözel reçete (§6.2)
│   │   ├── health-gauge.tsx
│   │   ├── before-after-gauge.tsx  # önce/sonra ikili gösterim (§16.1)
│   │   ├── sub-score-badge.tsx     # Performans/Güvenlik/Kalite
│   │   ├── security-section.tsx    # 🔒 Güvenlik Bulguları
│   │   ├── mode-comparison-card.tsx # mod karşılaştırma (§16.3)
│   │   ├── mode-selector.tsx
│   │   ├── provider-selector.tsx
│   │   ├── model-advanced.tsx
│   │   └── print-button.tsx
│   ├── lib/
│   │   ├── sse-client.ts
│   │   └── api-client.ts
│   └── public/
│
├── backend/                        # FastAPI
│   ├── pyproject.toml
│   ├── main.py
│   ├── api/
│   │   ├── analyze.py              # demo guard dahil (§16.7)
│   │   ├── report.py               # simulate endpoint dahil (§16.1)
│   │   ├── stream.py
│   │   ├── models.py
│   │   └── badge.py                # SVG badge (§16.4)
│   ├── agents/
│   │   ├── orchestrator.py
│   │   ├── profiler.py             # hybrid + static + deep
│   │   ├── impact_analyst.py
│   │   ├── impact_heuristic.py     # static mod
│   │   ├── surgeon.py
│   │   ├── chief.py
│   │   └── chief_heuristic.py      # static mod
│   ├── llm/
│   │   ├── base.py
│   │   ├── cerebras_provider.py
│   │   ├── gemini_provider.py
│   │   ├── registry.py
│   │   └── safe_json.py
│   ├── analysis/
│   │   ├── ast_parser.py
│   │   ├── ast_summary.py          # Derin mod için
│   │   ├── file_walker.py
│   │   ├── repo_cloner.py
│   │   ├── impact_heuristics.py
│   │   ├── simulation.py           # önce/sonra hesabı (§16.1)
│   │   ├── mode_comparison.py      # mod tahminleri (§16.3)
│   │   └── static_rules/
│   │       ├── base.py
│   │       ├── __init__.py         # ALL_RULES registry
│   │       │
│   │       ├── n1_query.py
│   │       ├── sync_in_async.py
│   │       ├── missing_index_hint.py
│   │       ├── o_n_squared.py
│   │       ├── large_payload.py
│   │       ├── repeated_compute.py
│   │       ├── overfetch_columns.py
│   │       ├── missing_timeout.py
│   │       │
│   │       ├── memory_leak_listener.py
│   │       ├── unclosed_resource.py
│   │       ├── unbounded_cache.py
│   │       ├── global_accumulator.py
│   │       ├── list_over_generator.py
│   │       ├── load_full_file.py
│   │       │
│   │       ├── unhandled_exception.py
│   │       ├── race_condition.py
│   │       ├── deep_recursion.py
│   │       ├── mutable_default_arg.py
│   │       │
│   │       ├── hardcoded_secret.py
│   │       │
│   │       ├── inefficient_string_concat.py
│   │       ├── circular_import.py
│   │       ├── shadow_variable.py
│   │       └── dead_code.py
│   ├── prompts/
│   │   ├── profiler_confirm.md
│   │   ├── deep_mode.md
│   │   ├── impact_analyst.md
│   │   ├── surgeon.md
│   │   ├── chief.md
│   │   └── examples/
│   └── tests/
│       ├── static_rules/
│       │   └── test_<rule>.py
│       └── fixtures/
│           └── bad_code_examples/
│
├── docs/
│   ├── pitch.md                    # 1-pager (§16.5)
│   ├── architecture.md
│   └── screenshots/
│
└── scripts/
    ├── test_llm.py
    └── scan_local_repo.py
    # build_cached_demos.py — MVP sonrası eklenecek (§16.2)
```

---

## 12. Test ve Doğrulama Stratejisi

### Unit testler
- Her statik kural için pozitif + negatif örnek.
- AST parser için 3 dilde örnek.
- Reçete kalitesi için zayıf few-shot örnekleri.
- `safe_json_parse` için tipik LLM artefaktları (code fence, trailing comma).

### Entegrasyon testleri
- **Fixture repo'lar:**
  1. `fixtures/python_flask_bad/` — kasıtlı 5+ örüntü
  2. `fixtures/javascript_express_bad/` — kasıtlı 3+ örüntü
  3. `fixtures/clean_repo/` — yanlış pozitif testi
- Her fixture için: 3 mod'da çalıştır, beklenen sonuç dosyasıyla karşılaştır.

### LLM testleri
- Snapshot testing: sabit input → JSON çıktı schema'ya uyuyor mu (içerik değil).
- Provider farkı: aynı input hem Cerebras hem Gemini'de aynı şemayı veriyor mu?

### Manuel test seti
- 5 farklı public GitHub repo (küçük Flask, Django blog, Express API, Next.js app, TS util kütüphanesi).

---

## 13. Karar Verilenler ✓

1. **İsim:** **KodHekim** ✓
2. **Demo repo:** **MVP'de yok** — kullanıcı doğrudan kendi repo URL'sini yapıştırır. Demo cache (§16.2) MVP sonrasına bırakıldı.
3. **UI dili:** **Sadece Türkçe.** İngilizce toggle yok.
4. **Dil Desteği:** Python, JavaScript ve TypeScript ilk sürümden itibaren tam desteklenmektedir. ✓
5. **Cerebras model güncellemesi:** Submit anında (19 Mayıs) tüm 4 model çalışır. 27 Mayıs sonrası deprecate olan ID'ler MVP sonrası güncellenecek (bkz. Ek A).

---

## 14. Başarı Kriterleri

### Minimum (mutlaka)
- Public GitHub linkinden Python, JavaScript ve TypeScript repo analizleri yapılıyor.
- 23 örüntüden en az 12'si gerçek bir repo'da tespit ediliyor.
- Etki Analisti her sorun için somut teknik metrik üretiyor (parasal yok).
- Cerrah en az 1 sorun için anlamlı Türkçe reçete üretiyor.
- Hekimbaşı: ana sağlık skoru + 3 alt-skor + top 3 öncelik.
- 3 analiz modu (Statik/Hibrit/Derin) çalışıyor.
- Hem Cerebras hem Gemini UI'dan seçilebiliyor.
- **🔒 Güvenlik Bulguları** ayrı UI bölümünde gösteriliyor.
- **🎯 Önce/Sonra simülasyonu** çalışıyor.
- **👨‍⚕️ Ajan karakterleri** (4 ajan persona) görünüyor.
- Canlı deploy public URL erişilebilir.
- Repo public, README + pitch.md dolu.

### İdeal
- 22 Python örüntünün tamamı tespit ediliyor.
- Tarayıcı "Yazdır" → temiz PDF çıktısı.
- 200+ dosyalı repo 2 dakikada tamamlanıyor.
- Derin mod orta boy repo'da anlamlı bulgu üretiyor.
- 📊 Mod karşılaştırma kartı raporda görünüyor.
- 🏷️ Badge endpoint canlıda, demo repolar için badge üretiyor.

### Stretch
- Roadmap çıktısı önceliklendirilmiş yapılacaklar listesi.
- GitHub PR oluşturma (auth ile).
- Provider/mod karşılaştırma sayfası ayrı yan-yana çalıştırma ile.
- 3 dilden fazla genişleme (Go/Rust/Java).

---

## 15. Risk Yönetimi

| Risk | Olasılık | Etki | Azaltma |
|---|---|---|---|
| LangGraph öğrenme eğrisi | Orta | Yüksek | Faz K'de basit POC; gerekirse manuel asyncio. |
| LLM rate limit | Düşük | Orta | İki sağlayıcı fallback. Concurrency limit. |
| Statik yanlış pozitif | Yüksek | Orta | LLM confirm kritik; negatif test fixture'ları erken. |
| Repo çok büyük → timeout | Orta | Orta | `MAX_FILES_TO_SCAN`, büyük dosyalar öncelikle. |
| SSE bağlantı kopması | Orta | Orta | Reconnect + polling fallback. |
| Cerrah zayıf reçete | Orta | Düşük | Few-shot örnekler + minimum adım sayısı doğrulaması. |
| Tree-sitter Windows build | Düşük | Yüksek | Linux container tercih. |
| Race condition false positive | Yüksek | Orta | LLM confirm zorunlu; severity tavanı `medium`. |
| Derin mod token aşımı | Orta | Orta | Token tavanı + dosya kırpma. |
| Cerebras model deprecation | Orta | Düşük | 27 Mayıs sonrası ID güncellemesi planda. |

---

## 16. Demo, Simülasyon ve Pazarlama Özellikleri

Hackathon başarı şansını artırmak için ürüne eklenen özelliklerin teknik tanımı.

### 16.1 Önce/Sonra Simülasyonu

**Amaç:** Kullanıcı raporda fix'leri seçer, sağlık skorunun nereye çıkacağını canlı görür. "Bu çalışmanın değeri" anını parmakla gösterir.

**UI:**
- Rapor sayfasında her sorun kartının yanında bir checkbox: "Bu fix'i uygula".
- Sayfanın üstündeki ana sağlık skoru gauge'ı **iki sayı** gösterir:
  - **Mevcut:** 62/100 (gri)
  - **Tahmini (fix'ler sonrası):** 91/100 (yeşil, animasyonlu)
- Bir "Tümünü seç" / "Hiçbirini seçme" butonu.
- Her bir alt-skor (Performans/Güvenlik/Kalite) de aynı şekilde iki değer gösterir.

**Backend:**
```python
# backend/analysis/simulation.py
def simulate_post_fix_score(
    all_issues: list[Issue],
    accepted_fix_ids: set[str],
) -> dict:
    remaining_issues = [i for i in all_issues if i.id not in accepted_fix_ids]
    return health_score(remaining_issues)
```

**Endpoint:**
```
POST /api/report/:job_id/simulate
  Body: { "accepted_fix_ids": ["issue-001", "issue-003"] }
  Response: {
    "current_score": { "overall": 62, "performance": 58, ... },
    "simulated_score": { "overall": 91, "performance": 88, ... },
    "delta": { "overall": +29, "performance": +30, ... }
  }
```

> Frontend tüm checkbox değişiminde debounce'lu (300ms) bu endpoint'i çağırır. Hesaplama saf Python, 1ms altında — backend'de cache'lemeye gerek yok.

### 16.2 Hemen Dene — Önbelleklenmiş Demo Analizleri (MVP sonrası)

> ⏳ **MVP'de yok.** MVP'de kullanıcı doğrudan kendi repo URL'sini yapıştırarak başlar. Demo repo seçimi ve önbellek altyapısı MVP sonrasında eklenecek (örneğin: jüri demo'su, marketing demo'su, "Hemen Dene" hızlı landing CTR'si için).
>
> MVP sonrası eklendiğinde uygulanacak iskelet:
> - `backend/data/cached_demos/<slug>.json` (pre-rendered raporlar)
> - `GET /api/report/demo-<slug>` endpoint
> - `components/demo-buttons.tsx` (landing'de 3 buton)
> - `scripts/build_cached_demos.py` (pre-render scripti)

### 16.3 Mod Karşılaştırma Metriği

**Amaç:** Analiz sonunda kullanıcı 3 modu yan yana görsün — Derin modu "demek bu varmış" hissi ile satar.

**UI:** Rapor sayfasının alt kısmında kart:
```
┌─────────────────────────────────────────────────────────┐
│  Bu repo için mod karşılaştırması                       │
├──────────┬──────────┬──────────┬─────────┬──────────────┤
│  Mod     │  Süre    │  Token   │ Bulgu # │  Kalite      │
├──────────┼──────────┼──────────┼─────────┼──────────────┤
│  Statik  │  2.3s    │  0       │  12     │  ⚡ Hızlı     │
│  Hibrit ✓│  47s     │  87K     │  18     │  🎯 Dengeli  │
│  Derin   │  2m18s   │  612K    │  21     │  🔬 Derin    │
└──────────┴──────────┴──────────┴─────────┴──────────────┘
```

**Mekanik (hafif):**
- Her analiz sonunda backend mevcut mod'un metriklerini `result.json`'a kaydeder.
- Diğer iki mod için **tahmin** yapılır (örn. statik mod tahmini = statik kuralla bulduklarını LLM confirm'den geçirmeden say; Derin mod tahmini = "~%15 daha fazla bulgu, ~5x süre, ~7x token" gibi sabit çarpanlar).
- "Diğer modları gerçekten çalıştır" linkı opsiyonel (yeni job tetikler) — stretch.

```python
# backend/analysis/mode_comparison.py
def estimate_other_modes(actual_mode: str, actual_metrics: dict) -> dict:
    """
    Gerçek mod metriklerinden diğer iki modun tahminini üretir.
    Sabit çarpanlar (kalibrasyon: 5 örnek repo üzerinde ölçülmüş).
    """
    ...
```

### 16.4 GitHub Badge

**Amaç:** Repo sahipleri kendi README'lerine sağlık skoru rozeti ekleyebilsin. Viral mekanizma + profesyonel ürün hissi.

**Endpoint:**
```
GET /api/badge/:owner/:repo.svg
  → SVG (shields.io tarzı)
  Önce cache'i kontrol et: cached_demos/badge_<owner>_<repo>.svg
  Yoksa: analiz yoksa "kodhekim: unscored" döndür
        analiz varsa: "kodhekim score: 78/100" (renk skor'a göre)
```

**Markdown kullanımı:**
```markdown
![KodHekim Score](https://kodhekim.app/api/badge/owner/repo.svg)
```

**Renk paleti:**
- 90+ → yeşil (`#4c1`)
- 70-89 → açık yeşil (`#97CA00`)
- 50-69 → sarı (`#dfb317`)
- 30-49 → turuncu (`#fe7d37`)
- 0-29 → kırmızı (`#e05d44`)

**SVG üretimi:** `backend/api/badge.py` — küçük string template, dependency yok.

### 16.5 1-Pager Pitch Dökümanı

**Amaç:** Hackathon jürisine submit sırasında ek materyal — repo'ya ek olarak okunabilen, ürünün tek sayfalık özet pazarlama dökümanı.

**Format:** `docs/pitch.md` (markdown, GitHub'da render edilir).

**İçerik iskeleti:**
```markdown
# KodHekim — Tek Sayfada

## Problem
Kötü kod sunucuyu yorar, fatura şişer, kimse asıl suçluyu bulamaz.

## Çözüm
4 AI ajan, 23 kod örüntüsü, 3 analiz modu — repo'nu kazıyıp tanı koyar.

## 3 Ekran
[screenshot: landing]  [screenshot: live analyze]  [screenshot: report]

## Mimari (mini diyagram)
[mermaid 4 ajan akışı]

## Neden Farklıyız
1. **Hibrit analiz:** Linter hızı + LLM bağlam anlayışı.
2. **3 mod:** Statik (ücretsiz CI/CD), Hibrit (default), Derin (LLM-direct).
3. **Çoklu sağlayıcı:** Cerebras (hız) ve Gemini (kalite) — kullanıcı seçer.
4. **Türkçe açıklama:** Yerel pazara doğrudan hitap.

## Hackathon Sonrası Roadmap
GitHub OAuth, monorepo, multi-language (Go/Java/Rust), GitHub Action.

## Linkler
🎬 Demo · 🌐 Canlı URL · 💻 GitHub
```

### 16.6 README.md (canlı belge)

**Amaç:** Repo public olduğunda jüri ilk açar. Buradan ürünü anında anlamalı.

**İskelet (`README.md`):**
```markdown
# KodHekim 🩺

> Reponuzu çoklu AI ajan ekibi ile tarayıp performans, RAM, güvenlik ve kalite sorunlarını
> tespit eden, somut tanı raporu çıkaran kod sağlığı sistemi.

**BTK Akademi Hackathon 2026 — Finans Teması**

🎬 [Tanıtım Videosu](youtube-link)
🌐 [Canlı Demo](deploy-link)
📄 [Pitch Dökümanı](docs/pitch.md)

## Hızlı Başlangıç

[3 örnek repo butonu] [kendi repo'nu dene URL]

## Ne Yapar

- 4 AI ajan ekibi (Dr. Müfettiş, Dr. Ölçücü, Dr. Cerrah, Dr. Hekimbaşı)
- 23 kod örüntüsü tespit
- 3 analiz modu (Statik / Hibrit / Derin)
- 2 LLM sağlayıcı (Cerebras / Gemini)
- Önce/Sonra simülasyonu
- GitHub badge

## Teknolojiler
Next.js 14 · FastAPI · LangGraph · Cerebras · Gemini · Tree-sitter · Tailwind

## Mimari
![mimari diyagram]

## Yerel Kurulum
[komutlar]

## Geliştirici Dökümanı
Detay için: [developer.md](developer.md)
```

### 16.7 Ucuz Kazançlar (Polish)

Demo'da fark yaratan, düşük efor yüksek etki dokunuşları.

#### 16.7.1 🧠 LLM Düşünme Stream'i
Analyze sayfasındaki canlı log feed'e LLM çağrılarının ham çıktısının ilk satırlarını yansıt. "AI gerçekten düşünüyor" hissi.

```python
# Profiler confirm sırasında, LLM cevabının ilk 80 karakterini event'e ekle
yield_event("agent_thinking", {
    "agent": "profiler",
    "thought": llm_response.text[:80] + "...",
    "issue_id": current_candidate.id,
})
```

Frontend log feed: `🧠 [Profiler düşünüyor] "Bu N+1 query gerçek bir sorun çünkü..."`

#### 16.7.2 📋 Reçete Kopyala Butonu
Her sorun kartındaki reçete panelinde küçük 📋 butonu. `navigator.clipboard.writeText(fix_instruction_tr)` + "Kopyalandı ✓" toast (1.5s).

#### 16.7.3 🔎 Repo Ön-Tarama
URL input alanına URL yapıştırılınca (`onBlur` veya 500ms debounce), backend'e ön-tarama isteği at:

```
GET /api/inspect?url=https://github.com/owner/repo
  Response: {
    "language": "python",
    "estimated_files": 47,
    "size_mb": 2.3,
    "last_commit": "3 days ago",
    "stars": 142
  }
```

Backend GitHub REST API ile tek istek (`GET /repos/:owner/:repo` + `GET /repos/:owner/:repo/languages`). 1-2 saniye.

UI: input altında küçük rozet — `🐍 Python · 47 dosya · 2.3 MB · son commit 3 gün önce`. Kullanıcı "Tanı Başlat"a basmadan önce bağlam alır.

#### 16.7.4 🎯 Auto Scroll + Highlight
Top 3 öncelik kartında her bir öğeye tıklanınca:
- Sayfa o sorunun bulunduğu issue kartına smooth scroll.
- Issue kartı 1.5 saniye sarı flash highlight (CSS animation).

```tsx
// components/issue-card.tsx
useEffect(() => {
  if (window.location.hash === `#issue-${issue.id}`) {
    cardRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    setHighlight(true);
    setTimeout(() => setHighlight(false), 1500);
  }
}, []);
```

Top 3 kartında: `<a href="#issue-001">` link.

### 16.8 Demo Guard'ı (jüri canlı denerse)

**Mekanik:**
- `backend/api/analyze.py` içine **bilinen demo repo whitelist'i** koy. Bu repo'lar geldiğinde:
  - `cached_demos/` cache'ini öncelikle kontrol et — varsa anında dön.
- Bilinmeyen repo geldiğinde:
  - Boyut kontrolü daha sıkı (`MAX_REPO_SIZE_MB`'ı geçici olarak 30'a düşür demo guard altında).
  - `MAX_FILES_TO_SCAN`'ı 80'e düşür.
- Frontend'de cevap > 90 saniyeyse "Demo'ya geç" butonu görünür: kullanıcı önbellekli demoya yönlenir.

**Env:**
```
DEMO_GUARD_ENABLED=true
DEMO_MAX_REPO_SIZE_MB=30
DEMO_MAX_FILES=80
DEMO_TIMEOUT_SEC=90
```

---

## 17. MVP Sonrası Roadmap

MVP submit edildikten sonra ekleneceği değerlendirilen güçlü özellikler. Burada listeleniyor ki kaybolmasın.

### 17.1 Analiz kalitesini katlayacak
- **Repo Karakterizasyonu** — Repo'nun ne tür uygulama (REST API / CLI / data pipeline / SPA / library) olduğunu LLM ile sınıflandır. Örüntü şiddetlerini bu bağlama göre kalibre et (örn. CLI tool'da `MISSING_TIMEOUT` düşük, API'de kritik).
- **Cross-File Call Graph + Hot Path** — AST'lerden global call graph + entry point BFS. Hot path'teki örüntülerin etki skoru 1.5x. `DEAD_CODE`, `CIRCULAR_IMPORT`, `N1_QUERY` isabet oranı ciddi yükselir.
- **Compound Pattern Detection** — Örüntü çakışmalarında risk çarpanı. Örn. `N1_QUERY` + `OVERFETCH_COLUMNS` aynı endpoint'te → "⚡ Birleşik Risk" özel kart.
- **Git Geçmişi Sinyali** — `git log --numstat` ile son 3 ay değişim sıklığı; sık değişen dosyalardaki sorunlar yüksek öncelik.
- **Embedding-Based Pattern Discovery** — Bilinen kötü kod örnekleri vektör DB'sinde; repo kod parçaları similarity match. Statik kural yazmadan yeni örüntü öğrenme.
- **Multi-Language Genişleme** — Go, Java, Rust, C# için tree-sitter parser + örüntü uyarlamaları.

### 17.2 Jüri/satış etkisini katlayacak
- **AI Hekim Konsültasyonu (Chat)** — Rapor üzerinde "Soru Sor" — context'inde tüm rapor + ilgili kod. "Bu N+1 neden riskli?" gibi sorular cevaplanır.
- **Cerebras vs Gemini Paralel Koşu** — Aynı repo iki sağlayıcı ile aynı anda analiz, sonuçlar yan yana. "Çoklu sağlayıcı" tezini gerçek veriyle satar.
- **AI-Generated Test Cases** — Cerrah'ın reçetesiyle birlikte unit test önerisi üretir.
- **Otomatik GitHub PR Oluşturma (OAuth)** — gelecek sürüm; şu an sözel reçete modeli PR üretmez.
- **GitHub Action Wrapper** — `kodhekim/action@v1` ile PR'lara otomatik review yorumu.

### 17.3 Operasyonel / üretim hazırlığı
- GitHub OAuth ile private repo desteği
- Kullanıcı hesabı + analiz geçmişi dashboard'u
- Rate limit + abuse protection
- Webhook bildirimleri (Slack/Discord/email)
- Tiered pricing (free / pro / enterprise)
- Monorepo desteği
- Repo karşılaştırma (iki repo arasında sağlık skoru benchmark)

---

## 18. Son Söz

Bu döküman tek bir geliştiricinin baştan sona, geri dönüş yapmadan ilerleyebilmesi için yazıldı. Her faz bir öncekinin tamamlandığını varsayar; her fazın çıkış kriteri test edilebilir.

Tıkanıldığında: §15 risk tablosuna bakın, fallback'i uygulayın. Yeni karar/öğrenme: bu dökümana satır ekleyin — `developer.md` canlı belge.

Kod yazarken hedef: **her ajan kendi başına çalışabilir**, **provider değiştirilebilir**, **örüntü eklenebilir**, **mod ayrılabilir**. Plugin mimarisi her seviyede.

İyi şanslar.

---

## Ek A — Cerebras model referansı (18 Mayıs 2026 itibarıyla)

Doğrulama: [Cerebras Inference Model Catalog](https://inference-docs.cerebras.ai/models/overview)

Aktif olarak destekleyeceğimiz modeller:

| Model ID | Tür | Not |
|---|---|---|
| `gpt-oss-120b` | 120B genel amaçlı | En sağlam seçim, deprecate riski yok |
| `llama3.1-8b` | 8B hızlı | ⚠️ Deprecate: 27 Mayıs 2026 |
| `qwen-3-235b-a22b-instruct-2507` | 235B reasoning | ⚠️ Deprecate: 27 Mayıs 2026 |
| `zai-glm-4.7` | Kod odaklı | GLM-4 ailesi |

**MVP sonrası güncelleme planı (27 Mayıs sonrası):** Deprecate olacak iki model yerine güncel ID'ler (`llama-3.3-70b`, `qwen-3-32b` vb.) konacak. Faz D'de SDK ile `client.models.list()` çağrısı (mümkünse) veya doc'tan canlı doğrulama scripti (`scripts/check_cerebras_models.py`) eklenecek.

**Hackathon submit penceresi:** 19 Mayıs 23:59 — bu tarihte tüm 4 model çalışır.
