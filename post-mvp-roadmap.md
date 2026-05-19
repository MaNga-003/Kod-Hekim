# KodHekim — MVP Sonrası Roadmap (v1)

> Bu döküman MVP teslim edildikten sonra eklenmesi planlanan özelliklerin ayrıntılı tasarım belgesidir. Her özellik için: amaç, KodHekim için neden gerektiği, teknik tasarım, API/UI etkisi, bağımlılıklar, efor tahmini ve ROI değerlendirmesi yazılır.
>
> Hedef kitle: MVP sonrasında ürünün gelişimini sürdürecek geliştirici (muhtemelen yine tek kişi).

**Son güncelleme:** 18 Mayıs 2026
**MVP referansı:** [developer.md](developer.md)

---

## 0. Genel Felsefe

MVP, 22 Python örüntüsünü tespit eden, 3 modlu, 2 sağlayıcılı bir kod sağlığı tanı sistemi sunar. Üründen aldığımız geri bildirim üç eksende artırılabilir:

1. **Analiz kalitesi** — tespitlerin daha doğru, bağlamsal, derin olması.
2. **Jüri/satış etkisi** — demo'da ve pazarlamada güçlü "wow" anları.
3. **Operasyonel olgunluk** — üretim ortamı için gerekli altyapı.

MVP'nin tezi şuydu: *"Repo'nu tarat, ne kadar kaynak yediğini görelim."* MVP sonrası hedef bu tezi katmanlamak — **bağlam**, **etkileşim**, **otomasyon** eklemek.

---

## 1. Önceliklendirme

İlk **iki ay** için önerilen sıralama (en yüksek ROI'den başlar):

| # | Özellik | Kategori | Efor | Etki |
|---|---|---|---|---|
| 1 | Repo Karakterizasyonu | Analiz | M | 🔴 Çok yüksek |
| 2 | AI Hekim Konsültasyonu (Chat) | Jüri | M | 🔴 Çok yüksek |
| 3 | Cross-File Call Graph + Hot Path | Analiz | L | 🔴 Çok yüksek |
| 4 | Compound Pattern Detection | Analiz | S | 🟠 Yüksek |
| 5 | AI-Generated Test Cases | Jüri | S | 🟠 Yüksek |
| 6 | Git Geçmişi Sinyali | Analiz | S | 🟠 Yüksek |
| 7 | Cerebras vs Gemini Paralel Koşu | Jüri | M | 🟡 Orta |
| 8 | GitHub PR Oluşturma (OAuth) | Jüri | L | 🟡 Orta |
| 9 | Sağlık Skoru Zaman Çizelgesi | Jüri | M | 🟡 Orta |
| 10 | OWASP / Well-Architected Uyum | Jüri | M | 🟡 Orta |
| 11 | Multi-Language Genişleme | Analiz | XL | 🔴 Çok yüksek (uzun vade) |
| 12 | Embedding-Based Pattern Discovery | Analiz | XL | 🟠 Yüksek (araştırma) |
| 13 | GitHub Action Wrapper | Üretim | M | 🟡 Orta |
| 14 | Demo Cache / Hemen Dene | Pazarlama | S | 🟡 Orta |

**Efor ölçeği:** S = 0.5-1 gün, M = 2-3 gün, L = 1 hafta, XL = 2+ hafta.

---

# Bölüm 1 — Analiz Kalitesi

## 1.1 Repo Karakterizasyonu

### Amaç
Repo'nun **ne tür uygulama** olduğunu önce anla, sonra örüntü skorlarını ona göre kalibre et.

### KodHekim için neden gerekli?
MVP'de her örüntü her repo'da aynı şiddetle puanlanır. Ama bir CLI tool'da `MISSING_TIMEOUT` neredeyse önemsizdir (üst süreç zaten sınırlandırır); bir REST API'de kritiktir (downstream blocking → cascade failure). Aynı şekilde `MEMORY_LEAK_LISTENER` bir kısa ömürlü script için yok hükmündedir, bir long-running daemon için felakettir.

Sonuç: Aynı 18 sorun, aynı sağlık skoru, ama **kullanıcının uygulamasına özel ağırlandırma** eksik. Bu, raporu "linter çıktısı" hissinden "uzman tanısı" hissine taşır.

### Teknik tasarım

#### A. Sınıflandırma sinyalleri
Backend `backend/analysis/repo_characterizer.py`:

```python
from typing import TypedDict, Literal

class RepoCharacterization(TypedDict):
    app_type: Literal[
        "rest_api", "graphql_api", "cli_tool", "data_pipeline",
        "etl_job", "ml_training", "frontend_spa", "library",
        "web_full_stack", "daemon_service", "lambda_function", "unknown"
    ]
    framework: Optional[str]   # "flask" | "fastapi" | "django" | "click" | None
    runtime: Literal["short_lived", "long_running", "request_response"]
    scale: Literal["small", "medium", "large"]  # dosya sayısı / LOC
    has_tests: bool
    has_ci: bool
    deployment_hint: Optional[str]  # Dockerfile, fly.toml, vercel.json varlığı
```

Toplama yöntemleri (öncelik sırasıyla):
1. **Dosya varlık taraması:**
   - `Dockerfile`, `docker-compose.yml` → daemon ihtimali
   - `serverless.yml`, `template.yaml`, `wrangler.toml` → lambda
   - `manage.py` → Django
   - `pyproject.toml` `[project.scripts]` → CLI tool
   - `airflow/`, `dagster/`, `prefect/` → data pipeline
2. **Bağımlılık analizi:** `requirements.txt`, `pyproject.toml`, `Pipfile` içinde fastapi/flask/django/click/airflow tespiti.
3. **Entry point AST analizi:**
   - `if __name__ == "__main__":` + `argparse`/`click` import → CLI
   - `FastAPI()` veya `Flask(__name__)` construct → API
4. **LLM sınıflandırma (son adım):** Yukarıdakileri özet halinde LLM'e ver, son kararı LLM verir (özellikle `unknown` ve `multi-tool` durumları).

```python
def characterize_repo(repo_path: str, llm: LLMProvider, model: str) -> RepoCharacterization:
    static_signals = collect_static_signals(repo_path)
    if static_signals.confidence > 0.8:
        return static_signals.result
    return llm_classify(static_signals, llm, model)
```

#### B. Etki Analisti entegrasyonu
Karakterizasyonun çıktısı `AnalysisState`'e eklenir:

```python
class AnalysisState(TypedDict):
    ...
    repo_characterization: RepoCharacterization
```

Etki Analisti çağrılırken bu bilgi prompt'a girer:

```
[Bağlam]
Bu repo türü: REST API (FastAPI, orta ölçek, long-running, deployment: Render)
[/Bağlam]

[Sorun]
MISSING_TIMEOUT - src/services/payment_client.py:42
[/Sorun]

Bağlamı dikkate alarak etki metriğini ve şiddeti güncelle.
```

#### C. Şiddet kalibrasyon matrisi
Sabit JSON `backend/data/severity_calibration.json`:

```json
{
  "MISSING_TIMEOUT": {
    "rest_api": "high",
    "cli_tool": "low",
    "data_pipeline": "medium",
    "library": "medium",
    "lambda_function": "high",
    "default": "high"
  },
  "DEEP_RECURSION": {
    "data_pipeline": "high",
    "default": "low"
  }
  // ...
}
```

Sınıflandırmadan sonra Profiler'ın çıktısı bu matrisle çarpılır.

#### D. UI etkisi
Rapor sayfasının üstüne bağlam rozeti:

```
🔎 Bu repo: REST API (FastAPI · orta ölçek · long-running)
   Sorunlar bu bağlama göre değerlendirildi.
```

### Bağımlılıklar
- MVP'nin LLM provider katmanı yeterli.
- Yeni statik kural motoru gerekmez.

### Efor: **M** (2-3 gün)
- Sinyal toplayıcılar: 1 gün.
- LLM sınıflandırıcı + prompt: 0.5 gün.
- Kalibrasyon matrisi + entegrasyon: 1 gün.
- Test + ince ayar: 0.5 gün.

### ROI
**Çok yüksek** — Tek özellik tüm pipeline'ın anlam derinliğini katlar. Aynı zamanda ileride **özelleştirilebilir profiller** (kullanıcı "ben Lambda yazıyorum" der → matris değişir) için temel oluşturur.

---

## 1.2 Cross-File Call Graph + Hot Path Tespiti

### Amaç
Repo'daki tüm fonksiyon çağrılarını birleştirilmiş bir **call graph** olarak modelle. Sonra entry point'lerden (route handler, `__main__`, scheduler tick) BFS ile her fonksiyonun "hot path mesafesini" çıkar.

### KodHekim için neden gerekli?
MVP'de her örüntü dosya-içi taranır. Bu üç ciddi sınırlama yaratır:

1. **DEAD_CODE yanlış pozitif çok yüksek** — fonksiyon dosya içinde çağrılmasa bile başka dosyada import edilip kullanılıyor olabilir.
2. **N1_QUERY etkisi yetersiz** — Loop'taki DB call'un asıl etkisi o loop'un kaç defa çağrıldığına bağlı. Bir helper fonksiyondaki N+1, request handler'dan 5 adım uzaktaysa düşük etki; doğrudan handler'daysa kritik.
3. **CIRCULAR_IMPORT zaten cross-file** — MVP'de basit graph traversal yapılıyor ama kapsamlı değil.

Hot path tespiti, Etki Analisti'nin **gerçek üretimde ne kadar tetiklendiğini** tahmin etmesini sağlar.

### Teknik tasarım

#### A. Call graph yapısı

```python
# backend/analysis/call_graph.py
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Symbol:
    module: str            # ör. "src.api.users"
    name: str              # ör. "get_user_posts"
    file: str
    line: int

@dataclass
class CallGraph:
    nodes: dict[Symbol, NodeInfo]
    edges: dict[Symbol, set[Symbol]]   # caller → callees
    reverse_edges: dict[Symbol, set[Symbol]]  # callee → callers
    entry_points: set[Symbol]
```

#### B. Entry point tespit kuralları
- `if __name__ == "__main__":` bloğu içinde çağrılan fonksiyonlar.
- FastAPI/Flask route decorator'lı fonksiyonlar (`@app.get`, `@router.post`, `@app.route`).
- Click/Typer command'ları (`@click.command`).
- Celery/RQ task'ları (`@app.task`, `@job`).
- Module-level top-level expressions (script tarzı).
- Test fonksiyonları (`test_*` — ayrı kategori, hot path sayılmaz).

#### C. Graph kurulumu
İki geçişli:
1. **İlk geçiş** — her dosyada tanımlı sembolleri topla (`def`, `class`, `async def`).
2. **İkinci geçiş** — her dosyada çağrıları çöz: `name lookup → symbol resolution`.
   - Import çözümü: `from src.api.users import get_user_posts` → `users.get_user_posts`.
   - Attribute call'lar: `user_service.get_posts()` — heuristik (tam çözüm zor, en yakın eşleşmeyi seç).
   - Dynamic call'lar (`getattr`, `globals()`): atla (zaten örüntü olabilir).

#### D. Hot path mesafesi (BFS)
```python
def compute_hot_distance(graph: CallGraph) -> dict[Symbol, int]:
    distances = {ep: 0 for ep in graph.entry_points}
    queue = list(graph.entry_points)
    while queue:
        current = queue.pop(0)
        for callee in graph.edges.get(current, ()):
            if callee not in distances:
                distances[callee] = distances[current] + 1
                queue.append(callee)
    return distances
```

#### E. Etki Analisti entegrasyonu
Her sorun için `hot_distance` lookup yapılır:

```python
def adjust_impact_for_hot_path(impact_score: int, hot_distance: int) -> int:
    if hot_distance <= 1:
        return int(impact_score * 1.5)   # hot path'in başında
    if hot_distance <= 3:
        return int(impact_score * 1.2)   # hot path yakınında
    if hot_distance >= 10 or hot_distance == float("inf"):
        return int(impact_score * 0.6)   # cold/dead code
    return impact_score
```

#### F. DEAD_CODE'un yenilenmesi
Sadece dosya-içi referans yerine global graph'ta `reverse_edges[symbol]` boş ise dead:

```python
def detect_dead_code(graph: CallGraph) -> list[Symbol]:
    return [
        sym for sym, info in graph.nodes.items()
        if not graph.reverse_edges.get(sym)
        and not info.is_entry_point
        and not info.is_test
        and not info.is_dunder
        and not info.is_decorator_arg
    ]
```

### UI etkisi
- Issue card'a "hot path mesafesi" rozeti: `🔥 1 adım uzakta` veya `❄️ cold path (8 adım)`.
- Rapor sayfasında küçük graph görselleştirme (opsiyonel, stretch).

### Bağımlılıklar
- MVP AST parser'ı yeterli.
- Yeni: import resolver mantığı.

### Efor: **L** (5-7 gün)
- Sembol tanımı + ilk geçiş: 1 gün.
- Çağrı çözümü + import resolver: 2 gün (zor kısım, attribute calls heuristik).
- BFS + entegrasyon: 1 gün.
- DEAD_CODE yenileme: 0.5 gün.
- Etki ayarlamaları + test: 1.5 gün.

### ROI
**Çok yüksek** — Pek çok örüntünün doğruluğu birden artar; ürünün "linter+" konumlanmasını "kod anlayan asistan"a taşır.

---

## 1.3 Compound Pattern Detection

### Amaç
Birbirini güçlendiren örüntü çiftlerini tespit et, etkilerini çarp.

### KodHekim için neden gerekli?
Gerçek dünyada en kötü performans/güvenilirlik sorunları nadiren tek bir örüntüden gelir. Tipik kombinasyonlar:

- `N1_QUERY` + `OVERFETCH_COLUMNS` → her sorgu zaten çok kolon, üstüne 1000 kere yapılıyor.
- `SYNC_IN_ASYNC` + `MISSING_TIMEOUT` → event loop bloke + sınırsız bekleme → tek bir downstream yavaşlığı sunucuyu tamamen kilitler.
- `UNBOUNDED_CACHE` + `LARGE_PAYLOAD` → cache key'leri ağır objelerse RAM hızla şişer.
- `GLOBAL_ACCUMULATOR` + `MISSING_TIMEOUT` → connection pool'da hata bekleyen istekleri toplar, sonsuza kadar büyür.

MVP'de bu çiftlemeler raporda görünmez. Compound detection bunları "**⚡ Birleşik Risk**" kartlarıyla öne çıkarır.

### Teknik tasarım

#### A. Compound matchers
Sabit kurallar — `backend/analysis/compound_rules.py`:

```python
from dataclasses import dataclass

@dataclass
class CompoundRule:
    name: str
    patterns: tuple[str, ...]            # ör. ("N1_QUERY", "OVERFETCH_COLUMNS")
    co_location: Literal["same_function", "same_file", "same_request_path"]
    multiplier: float                     # impact skoru çarpanı (1.5–3.0)
    explanation_tr: str                   # "Bu iki örüntü birlikte..."

COMPOUND_RULES = [
    CompoundRule(
        name="cascading_db_overhead",
        patterns=("N1_QUERY", "OVERFETCH_COLUMNS"),
        co_location="same_function",
        multiplier=2.5,
        explanation_tr=(
            "Bu fonksiyon hem N+1 query yapıyor hem de her sorguda gereksiz kolonlar çekiyor. "
            "Etki çarpanı: tek başına N+1'in 2.5x'i. Tek bir düzeltmeyle iki sorun da çözülür."
        ),
    ),
    CompoundRule(
        name="event_loop_starvation",
        patterns=("SYNC_IN_ASYNC", "MISSING_TIMEOUT"),
        co_location="same_function",
        multiplier=3.0,
        explanation_tr=(
            "Async fonksiyon hem blocking call hem timeout'suz. Tek yavaş downstream "
            "tüm event loop'u kilitler — cascade failure riski yüksek."
        ),
    ),
    CompoundRule(
        name="memory_runaway",
        patterns=("UNBOUNDED_CACHE", "LARGE_PAYLOAD"),
        co_location="same_request_path",
        multiplier=2.0,
        explanation_tr=(
            "Cache sınırsız ve cache'lenen değerler büyük. RAM dakikalar içinde tükenir."
        ),
    ),
    CompoundRule(
        name="leak_under_pressure",
        patterns=("GLOBAL_ACCUMULATOR", "MISSING_TIMEOUT"),
        co_location="same_file",
        multiplier=2.2,
        explanation_tr=(
            "Bekleyen istekler global yapıya birikiyor, bekleme süresi sınırsız. "
            "Yük altında bellek sızıntısı garantili."
        ),
    ),
    # ... 6-10 daha
]
```

#### B. Co-location tespit
Profiler tamamlandıktan sonra post-processing pass:

```python
def detect_compounds(
    issues: list[Issue],
    call_graph: Optional[CallGraph] = None,  # 1.2'den
) -> list[CompoundIssue]:
    compounds = []
    for rule in COMPOUND_RULES:
        matching_groups = group_by_co_location(
            [i for i in issues if i.code in rule.patterns],
            rule.co_location,
            call_graph=call_graph,
        )
        for group in matching_groups:
            if set(i.code for i in group) >= set(rule.patterns):
                compounds.append(
                    CompoundIssue(
                        rule_name=rule.name,
                        constituent_issues=[i.id for i in group],
                        multiplier=rule.multiplier,
                        explanation_tr=rule.explanation_tr,
                    )
                )
    return compounds
```

`group_by_co_location`:
- `same_function` — issue'lar aynı `function_scope` içinde mi?
- `same_file` — aynı `file` mı?
- `same_request_path` — call graph üzerinde aynı entry point'ten ulaşılabiliyor mu?

#### C. Etki Analisti'ne yansıma
`CompoundIssue` listesi `AnalysisState`'e eklenir. Etki Analisti, constituent issue'ların skorlarına `multiplier` uygular ve compound için ayrı bir özet yazar.

#### D. UI etkisi
Rapor sayfasında, normal sorun listesinin **üstünde** ayrı bir bölüm:

```
⚡ Birleşik Risk (3 tespit)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 Cascading DB Overhead — src/api/users.py:get_user_feed
   N+1 Query + Overfetch Columns birlikte
   Tek başlarına olsalardı: 45 + 12 puan
   Birleşik etki: 142 puan (2.5x çarpan)
   "Bu fonksiyon hem N+1 hem her sorguda gereksiz kolon..."
   ↓ Constituent issues göster
```

### Bağımlılıklar
- MVP Profiler çıktısı yeterli.
- Co-location `same_request_path` türü için §1.2 (call graph) gerekir; o olmadan sadece `same_function` ve `same_file` çalışır (yeterince güçlü başlangıç).

### Efor: **S** (1-2 gün)
- 10 kural yazımı: 1 gün.
- Co-location detector: 0.5 gün.
- Etki entegrasyonu + UI: 0.5 gün.

### ROI
**Yüksek** — Az iş, çok satılır. Demo'da "şuna bak, iki sorun ayrı ayrı küçük ama birlikte felaket" diye gösterilebilen anlamlı içgörü.

---

## 1.4 Git Geçmişi Sinyali

### Amaç
Her sorunun olduğu dosyanın değişim sıklığını ve son değişiklik tarihini kullanarak öncelikleri yeniden derecelendir.

### KodHekim için neden gerekli?
Bir kod tabanında her dosya eşit risk taşımaz:

- Sık değişen dosyalar regression riski yüksektir.
- Yeni eklenmiş (son 2 hafta) kod, oturmuş kod kadar test edilmemiştir.
- 3 yıldır dokunulmamış dosyalar genelde işliyor demektir — düzeltmek mantıklı değildir.

Bu sinyaller ROI hesabını ciddi etkiler.

### Teknik tasarım

#### A. Veri toplama
```python
# backend/analysis/git_signals.py
import subprocess
from datetime import datetime, timedelta

def collect_file_signals(repo_path: str, files: list[str]) -> dict[str, FileGitSignal]:
    cutoff_3mo = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    result = {}
    for f in files:
        log = subprocess.run(
            ["git", "-C", repo_path, "log", f"--since={cutoff_3mo}",
             "--numstat", "--pretty=format:%H|%ai|%an", "--", f],
            capture_output=True, text=True,
        )
        result[f] = parse_git_log(log.stdout)
    return result

@dataclass
class FileGitSignal:
    commits_last_90d: int
    last_commit_at: datetime
    last_commit_author: str
    lines_added_last_90d: int
    lines_deleted_last_90d: int
    is_recently_added: bool   # ilk commit < 14 gün önce
    age_days: int              # ilk commit'ten bu yana
```

#### B. Risk skorlama
```python
def compute_file_risk_score(signal: FileGitSignal) -> float:
    """Returns 0.5-2.0 multiplier."""
    score = 1.0
    if signal.commits_last_90d > 20:
        score *= 1.4   # hot file
    if signal.is_recently_added:
        score *= 1.3   # fresh, less tested
    if signal.age_days > 365 and signal.commits_last_90d == 0:
        score *= 0.6   # stable, dokunma
    return score
```

#### C. Etki Analisti entegrasyonu
Sorunun bulunduğu dosyanın signal'i her sorun için lookup edilir, ROI hesabında `multiplier` olarak girer. Açıklama metnine eklenir:

> "Bu dosya son 90 günde 24 commit aldı — yüksek değişim alanı, regression riski normalden büyük."

#### D. UI etkisi
Issue card'da küçük rozet:
- `🔥 Hot file (24 commit)`
- `🌱 Yeni dosya (8 gün önce eklendi)`
- `🪨 Stabil (son commit 6 ay önce)`

### Bağımlılıklar
- MVP'nin `gitpython` zaten var. Subprocess `git log` çağrısı da yeterli.

### Efor: **S** (1 gün)
- Git log parser: 0.5 gün.
- Risk hesabı + entegrasyon + UI: 0.5 gün.

### ROI
**Yüksek** — Çok hafif iş, somut katma değer. Demo'da "bu sorun son 2 ayda 14 kez değişmiş bir dosyada" cümlesi profesyonel hissi katar.

---

## 1.5 Embedding-Based Pattern Discovery

### Amaç
Statik kural yazmadan **yeni örüntüler öğrenmenin yolu**: bilinen "kötü kod" örneklerini vektör veritabanına gömerek, repo'daki kod parçalarını similarity ile eşleştir.

### KodHekim için neden gerekli?
- Her yeni örüntü için kural yazmak yavaş ve hata yapmaya açık.
- Endüstri sürekli yeni anti-pattern keşfediyor (örn. yeni ORM versiyonlarında yeni N+1 varyantları).
- "Bilinmeyen-bilinmeyen" örüntüleri yakalamanın tek pratik yolu LLM Direct mod ama yüksek token maliyetli.

Embedding-based discovery, **düşük token maliyetiyle** geniş örüntü kapsamı sağlar.

### Teknik tasarım

#### A. Curated bad-code corpus
`backend/data/bad_code_corpus/` altında JSONL dosyası:

```jsonl
{"id":"N1_VARIANT_DJANGO","code":"for obj in qs:\n    related = obj.children.all()","pattern_family":"N1_QUERY","language":"python","explanation":"Django ORM N+1, prefetch_related eksik"}
{"id":"BLOCKING_ASYNC_PG","code":"async def fn():\n    rows = psycopg2.connect(...).cursor().fetchall()","pattern_family":"SYNC_IN_ASYNC","language":"python","explanation":"Async fonksiyonda senkron psycopg2"}
```

Başlangıçta her örüntü için 5-10 varyant (toplam 150-200 örnek).

#### B. Embedding pipeline
```python
# backend/analysis/embedding_index.py
import google.generativeai as genai
from chromadb import PersistentClient

class EmbeddingIndex:
    def __init__(self, corpus_path: str, db_path: str = "./chroma_db"):
        self.client = PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection("bad_code")
        self._ensure_indexed(corpus_path)

    def _ensure_indexed(self, corpus_path: str):
        # corpus_path'in son güncellenme zamanını DB'de tut
        # yeni satırlar varsa embed et
        ...

    def search(self, code_snippet: str, top_k: int = 5) -> list[Match]:
        emb = genai.embed_content(
            model="models/text-embedding-004",
            content=code_snippet,
            task_type="RETRIEVAL_QUERY",
        )["embedding"]
        results = self.collection.query(
            query_embeddings=[emb],
            n_results=top_k,
            include=["distances", "documents", "metadatas"],
        )
        return [
            Match(snippet=doc, metadata=meta, similarity=1 - dist)
            for doc, meta, dist in zip(results["documents"][0],
                                       results["metadatas"][0],
                                       results["distances"][0])
        ]
```

#### C. Profiler'a yeni adım
Statik kural taramasından sonra, yakalanmayan dosya bölümleri için (function-level chunking) embedding search:

```python
for func_snippet in chunk_by_functions(file_ast):
    matches = embedding_index.search(func_snippet.source, top_k=3)
    high_matches = [m for m in matches if m.similarity > 0.78]
    for m in high_matches:
        candidates.append(IssueCandidate(
            code=m.metadata["pattern_family"],
            file=file_path,
            line_start=func_snippet.line,
            confidence=m.similarity,
            detection_source="embedding",
            similar_to=m.metadata["id"],
        ))
```

LLM confirm step yine devreye girer (statik aday değil "fuzzy aday" olduğu için precision daha düşük).

#### D. Corpus güncelleme
- Kullanıcı raporda "bu yanlış pozitifti" işaretlerse corpus'tan negatif sample eklenir.
- "İlginç bulgu, kaydet" butonu ile yeni örnek corpus'a girer (admin onayı).

### Bağımlılıklar
- ChromaDB veya benzeri lokal vector store.
- Gemini embedding API (veya open-source: `sentence-transformers/all-MiniLM-L6-v2`).
- §1.2 (call graph) opsiyonel — function-level chunking ile yeterli.

### Efor: **XL** (2-3 hafta)
- Corpus toplama + etiketleme: 1 hafta (en yavaş kısım).
- Embedding pipeline + index: 3 gün.
- Profiler entegrasyonu + LLM confirm tuning: 3 gün.
- Feedback loop + corpus update mantığı: 3 gün.

### ROI
**Yüksek (uzun vade)** — Tek seferlik yatırım, sonra kural yazmadan kapsam genişler. Ancak corpus toplama yavaş ve disiplin ister.

---

## 1.6 Multi-Language Genişleme

### Amaç
Python dışında JavaScript, TypeScript, Go, Java, Rust, C# desteği.

### KodHekim için neden gerekli?
Pazar genişliği. Pek çok production stack çoklu dildir — sadece Python işletmelerle sınırlı kalır.

### Teknik tasarım

#### A. Aşamalı yaklaşım
1. **Aşama 1 — JS/TS** (en yüksek ROI, ekosistem yakın)
2. **Aşama 2 — Go** (bulut/microservice yaygın)
3. **Aşama 3 — Java, C#** (enterprise)
4. **Aşama 4 — Rust** (sistem programlama, yavaş büyüyen niş)

#### B. Her dil için neler yapılır?

Dil ekleme şablonu:
1. **Tree-sitter parser** — `tree-sitter-<lang>` Python binding.
2. **Dil-spesifik AST adapter** — generic AST'mize çevir.
3. **Statik kural adaptasyonu** — 22 örüntünün hangileri o dilde anlamlı? Adapte et:
   - JS/TS: `MEMORY_LEAK_LISTENER` aktifleşir (DOM addEventListener, Node EventEmitter).
   - JS/TS: `MUTABLE_DEFAULT_ARG` yok (dilde böyle bir tuzak yok).
   - JS/TS: Yeni örüntüler: `PROMISE_NOT_AWAITED`, `EVENT_HANDLER_INLINE` (React perf).
   - Go: `GOROUTINE_LEAK` (channel'a yazılmıyor + alıcı yok).
   - Go: `DEFER_IN_LOOP` (loop içinde `defer` — bellek artışı).
4. **Test fixture'ları** — her dil için kasıtlı kötü repo.
5. **Frontend dil rozetleri** — sorun listesinde dil ikonu.

#### C. Repo dil tespiti
```python
def detect_languages(repo_path: str) -> list[Language]:
    # Mevcut MVP'de basit extension count
    # Genişleme: GitHub Linguist mantığı taklit et
    # veya `linguist` CLI'ı subprocess'le çağır
    ...
```

#### D. Multi-language repo
Bir repo'da hem Python backend hem JS frontend varsa her ikisini de tara, **karma rapor** üret. Kategori: "Python (16 sorun)", "JavaScript (8 sorun)".

### Bağımlılıklar
- MVP plugin sistemi zaten bu genişlemeyi destekliyor (`StaticRule.languages` field).

### Efor: **XL per dil**
- JS/TS: 2-3 hafta (en kolay, ekosistem yakın).
- Go: 3-4 hafta.
- Java/C#: 1-2 ay her biri (büyük ekosistem, çok framework).
- Rust: 2-3 hafta (daha az framework, daha açık).

### ROI
**Çok yüksek (uzun vade)** — Adresable pazarı geometrik artırır. Ama tek dil için bile büyük yatırım.

---

## 1.7 MEMORY_LEAK_LISTENER (Bekleyen MVP Örüntüsü)

JS/TS desteği geldiğinde aktifleşecek örüntü. MVP dökümanında §5.2'de bahsedilmişti.

### Genişletilmiş tespit kuralları
- DOM: `addEventListener` çağrısı + matching `removeEventListener` yok (aynı dosyada veya React component lifecycle'da).
- Node: `EventEmitter.on()` + matching `.off()`/`.removeListener()` yok.
- React: `useEffect` içinde event listener kayıt + cleanup function yok.
- Vue: `mounted` hook'unda listener + `beforeDestroy`/`onUnmounted` cleanup yok.

### Etki metriği
- Listener kayıt sıklığı (re-render başına?).
- Closure'da tutulan obje boyutu tahmini.
- Sızıntı/saat tahmini.

### Efor: **S** (1 gün, §1.6 Aşama 1 ile birlikte)

---

# Bölüm 2 — Jüri / Satış Etkisini Katlayacak

## 2.1 AI Hekim Konsültasyonu (Chat) ⭐

### Amaç
Rapor sayfasında, kullanıcının raporla ilgili soru sorabileceği bir **chat arayüzü**. Tüm rapor + ilgili kod bağlam olarak LLM'e gider. Kullanıcı:
- "Bu N+1 neden gerçekten önemli?"
- "Cerrah'ın önerdiği diff'i uygularsam ne riske girerim?"
- "Bu repo'da gözünüze takılmayan başka bir şey var mı?"
- "Hangi sorunu önce çözmeliyim, müşterim trafiği iki katına çıkacak?"

LLM bağlamla cevaplar. **Tek seferlik analiz aracını, sürekli danışmana çevirir.**

### KodHekim için neden gerekli?
- **En büyük "wow" anı.** "Yanında doktor var" hissi.
- Etki Analisti ve Cerrah'ın tek seferlik çıktılarını tartışma için açar.
- Kullanıcı yapışkanlığı artar — rapor okunur ve unutulur değil, içinde zaman geçirilir.

### Teknik tasarım

#### A. Endpoint
```
POST /api/report/:job_id/chat
  Body: {
    "messages": [
      {"role": "user", "content": "..."},
      {"role": "assistant", "content": "..."},
      {"role": "user", "content": "..."}
    ],
    "context_issue_id": "issue-001"  // opsiyonel, belirli sorun bağlamı
  }
  Response: {"role": "assistant", "content": "..."}
```

#### B. Context yönetimi
Sistem prompt'ında otomatik dahil edilenler:
- Repo karakterizasyonu (§1.1).
- Sağlık skoru + alt-skorlar.
- Tespit edilen tüm sorunların özet listesi (id, code, file, severity, açıklama).
- Compound issues (§1.3).
- `context_issue_id` belirtilmişse o sorunun:
  - Tam snippet'i + sürrounding code (±50 satır).
  - Etki metrikleri.
  - Cerrah'ın diff'i.

Context boyutu: ~30-50K token (Gemini 2.5 Pro rahat sığar).

#### C. Sistem prompt iskeleti
`prompts/consultation.md`:
```
Sen Dr. Hekimbaşı'sın — kıdemli bir kod sağlığı danışmanı. Kullanıcı raporunu okudu
ve sana danışıyor. Cevapların:
- Türkçe, profesyonel, sıcak ama net.
- Tahminlerinde kesin ol; bilmediğini "veri yetersiz" diye söyle.
- Mümkün olduğunca somut metrik kullan.
- Raporda olmayan iddia üretme.

Mevcut rapor bağlamı:
{REPORT_CONTEXT}

Konuşma:
{MESSAGE_HISTORY}
```

#### D. Sıcaklık ve model
- Default: `gemini-2.5-pro` (1M context, kalite).
- Hızlı mod: `gpt-oss-120b` (Cerebras).
- Temperature: 0.4 (yaratıcı ama disiplinli).

#### E. UI
Rapor sayfasının sağ alt köşesinde floating button: 💬 **"Dr. Hekimbaşı'na sor"**.
- Tıklayınca sağdan kayan panel (full-height drawer).
- Üstte: önceden hazırlanmış 4 "öneri sorusu" chip'i.
- Sorun kartlarındaki "Bu sorunla ilgili sor" linki, chat'i o sorun bağlamıyla açar.
- Streaming response (SSE değil ama benzer fetch streaming).

#### F. Persona koruması
Eğer Dr. Hekimbaşı'na ürün/kişi sorulursa: "Ben sadece bu repo'nun kod sağlığı hakkında konuşurum." — scope guardrail.

#### G. Token yönetimi
Mesaj history > 10 mesaj olunca eski mesajları LLM'e özetletip kısalt.

### Bağımlılıklar
- MVP'nin LLM provider katmanı yeterli.
- §1.1 (repo karakterizasyonu) bağlam zenginliğini artırır ama zorunlu değil.

### Efor: **M** (3-4 gün)
- Backend endpoint + context builder: 1.5 gün.
- Sistem prompt + persona tuning: 0.5 gün.
- Frontend chat UI + streaming: 1.5 gün.
- Token yönetimi + edge case: 0.5 gün.

### ROI
**EN YÜKSEK.** Tek özellik MVP sonrası ürünün satış hikâyesini taşıyabilir.

---

## 2.2 Cerebras vs Gemini Paralel Koşu

### Amaç
Kullanıcı "Karşılaştırmalı Analiz" seçerse aynı repo iki sağlayıcı ile **paralel** analiz edilir. Sonuçlar yan yana gösterilir.

### KodHekim için neden gerekli?
- "Çoklu sağlayıcı" tezini görselleştirir — sözden gösteriye geçer.
- Cerebras hızı **fark edilir** olur ("47s vs 2m12s").
- Kullanıcı kendi tercihini veri üzerinden yapar.
- Demo'da büyük an: "Aynı repo, iki sağlayıcı, yan yana sonuç."

### Teknik tasarım

#### A. Endpoint genişlemesi
```
POST /api/analyze
  Body: {
    ...,
    "compare_providers": true   // yeni alan
  }
  Response: { "job_id": "abc123" }
```

`compare_providers=true` durumunda backend her bir provider için ayrı sub-job başlatır. Her sub-job kendi SSE event stream'ine yayar (`stream_a`, `stream_b`).

#### B. SSE topology
```
GET /api/analyze/:job_id/stream         # mevcut, ortak event stream
GET /api/analyze/:job_id/stream/cerebras
GET /api/analyze/:job_id/stream/gemini
```

Frontend ikisini birden açıp split-view'da log akıtır.

#### C. Karşılaştırma raporu
İki rapor da bittikten sonra:
```
GET /api/report/:job_id/comparison
  Response: {
    "cerebras": { full report },
    "gemini": { full report },
    "diff": {
      "common_issues": ["issue-A", "issue-B"],
      "only_cerebras": ["issue-X"],
      "only_gemini": ["issue-Y", "issue-Z"],
      "score_difference": {"cerebras": 62, "gemini": 65},
      "timing": {"cerebras": 47, "gemini": 132},
      "tokens": {"cerebras": 87000, "gemini": 134000}
    }
  }
```

#### D. UI
Yeni route: `/report/:job_id/compare`. Split-screen:
- Sol: Cerebras sonuçları (mor accent).
- Sağ: Gemini sonuçları (mavi accent).
- Üstte özet bar: süre, token, bulgu sayısı, ortak/farklı.
- Aşağıda iki rapor paralel scroll.

### Bağımlılıklar
- MVP'nin orchestrator'ı genişletilmeli (parallel sub-jobs).
- Frontend yeni route + side-by-side layout.

### Efor: **M** (3 gün)
- Backend orchestrator parallel job: 1.5 gün.
- Comparison endpoint: 0.5 gün.
- Frontend split-view: 1 gün.

### ROI
**Yüksek.** Hackathon kalmış olsaydı `must-have` olurdu. Üretimde de "Plus" tier özelliği olabilir.

---

## 2.3 AI-Generated Test Cases

### Amaç
Cerrah'ın diff'iyle birlikte **çalışan unit test** üretir.

### KodHekim için neden gerekli?
Düzeltme önerisi sunmak yetmez — kullanıcı "uygulasam bir şey kırılır mı?" diye soruyor. Test üretmek bu kaygıyı doğrudan adresler. "Düzeltme + test" combo'su profesyonel ürün standartıdır.

### Teknik tasarım

#### A. Cerrah çıktı genişlemesi
```json
{
  "issue_id": "issue-001",
  "diff": "...",
  "risk_level": 2,
  "test_suggestion": "...",
  "improvement_estimate": "...",
  "test_code": {
    "framework": "pytest",
    "file_path": "tests/test_users_api.py",
    "code": "def test_get_user_feed_uses_eager_loading(client, db):\n    ..."
  }
}
```

#### B. Prompt değişikliği
`prompts/surgeon.md`'a ek:

```
Düzeltmenin doğruluğunu kanıtlayan **çalışır bir unit test** yaz.
Tercih sırası: pytest > unittest > custom.
Test:
- Düzeltilmiş kodu test eder (eski kodla fail eder).
- External dependencies için minimal mock kullan.
- 30 satırdan az.
- Açık assertion (örn. `assert response.json()["count"] == 10`).
```

#### C. Test framework tespiti
Repo'da `pytest` import'u veya `pytest.ini` varsa pytest. Yoksa `unittest`. Yoksa `# AŞAĞIDAKİ TESTİ UYGULAMAK İÇİN ÖNCE pytest YÜKLEYİN` notu eklenir.

#### D. UI etkisi
Issue card'daki diff viewer'ın yanına ikinci tab: **"Test"**. Aynı `react-diff-viewer` veya `Monaco Editor` ile test kodu gösterilir. Yine "📋 Kopyala" butonu.

### Bağımlılıklar
- MVP'nin Cerrah'ı yeterli.

### Efor: **S** (1-2 gün)
- Prompt eklemesi + few-shot örnekler: 0.5 gün.
- Test framework tespit: 0.5 gün.
- UI tab + kopyala: 0.5 gün.

### ROI
**Yüksek.** Düşük efor, açık değer. Demo'da "düzeltme + test" tek paket gösterilince fark yaratır.

---

## 2.4 Sağlık Skoru Zaman Çizelgesi

### Amaç
Repo'nun farklı commit'lerindeki sağlık skorunu gösteren küçük grafik. "Skor son 6 ayda 78'den 62'ye düşmüş."

### KodHekim için neden gerekli?
- Tek seferlik snapshot yerine **trend** sunar.
- "Bu repo bozulmakta mı yoksa iyileşmekte mi?" sorusunu cevaplar.
- Demo'da görselin gücü çok yüksek.

### Teknik tasarım

#### A. Sampling stratejisi
Tüm commit'leri analiz etmek pahalı. Sampling:
- Son 90 günde 6 commit (eşit aralıklı).
- HEAD ve `main`'in 30, 60, 90 gün önceki halleri.
- Toplam 6-8 nokta yeterli grafik için.

#### B. Pipeline
```python
async def compute_health_timeline(
    repo_path: str,
    analysis_state: AnalysisState,
) -> list[TimelinePoint]:
    commits = sample_commits(repo_path, count=6, span_days=90)
    points = []
    for commit in commits:
        with checkout(repo_path, commit.sha):
            mini_state = await run_lightweight_analysis(repo_path, mode="static")
            points.append(TimelinePoint(
                date=commit.date,
                sha=commit.sha[:7],
                health_score=mini_state.report["overall"],
                issue_count=len(mini_state.issues),
            ))
    return points

@dataclass
class TimelinePoint:
    date: datetime
    sha: str
    health_score: int
    issue_count: int
```

> "Lightweight" = sadece statik mod (LLM yok), hız için.

#### C. Endpoint
```
GET /api/report/:job_id/timeline
  Response: { "points": [...] }
```

Bu endpoint background'da hesaplanır (ilk rapor görüntülenirken arka planda başlar), bittiğinde SSE event yayar (`timeline_ready`).

#### D. UI
Rapor sayfasının üstünde küçük grafik (recharts veya chart.js):

```
Sağlık Skoru Trendi (son 90 gün)
┌─────────────────────────────────┐
│ 95 ┤●                            │
│ 90 ┤                             │
│ 85 ┤   ●                         │
│ 80 ┤        ●                    │
│ 75 ┤             ●               │
│ 70 ┤                  ●          │
│ 65 ┤                       ●    │
│ 60 ┤                          ● │  ← HEAD: 62
│    └────────────────────────────│
│    -90d -75d -60d -45d -30d HEAD│
└─────────────────────────────────┘
```

### Bağımlılıklar
- §1.1 (karakterizasyon) — temiz bir lightweight analiz için.

### Efor: **M** (2-3 gün)
- Sampling + checkout mantığı: 1 gün.
- Background task: 0.5 gün.
- UI grafik: 1 gün.

### Riskler
- Büyük repolarda checkout süresi uzayabilir. Shallow clone ile kontrol altına alınır.
- Eski commit'lerde lib uyumsuzluğu olabilir (bizim için sorun değil — sadece static AST tarıyoruz).

### ROI
**Orta-Yüksek.** Görsel etkisi büyük, ama büyük repo'larda performans riski var.

---

## 2.5 OWASP / Well-Architected Uyum Rozeti

### Amaç
Tespit edilen sorunları endüstri framework'lerine eşle. Rapor üstünde rozet:
- OWASP Top 10 (2025) uyum yüzdesi
- AWS Well-Architected — Performance Efficiency, Reliability, Security pillar'ları
- Google SRE Workbook prensipleri

### KodHekim için neden gerekli?
- Kurumsal jüri/müşteriler bu framework'lere aşinadır.
- "X uyumu artırır" cümlesi kurumsal satışta güçlüdür.
- Ürünü "linter+" değil "compliance araç" sınıfına taşır.

### Teknik tasarım

#### A. Mapping tablosu
`backend/data/framework_mappings.json`:

```json
{
  "owasp_top_10_2025": {
    "A03_2025_Injection": ["HARDCODED_SECRET"],
    "A04_2025_Insecure_Design": ["MISSING_TIMEOUT", "UNHANDLED_EXCEPTION"],
    "A05_2025_Security_Misconfiguration": ["HARDCODED_SECRET"],
    "A09_2025_Logging_Failures": []
  },
  "aws_well_architected": {
    "performance_efficiency": [
      "N1_QUERY", "OVERFETCH_COLUMNS", "MISSING_INDEX_HINT",
      "O_N_SQUARED", "LARGE_PAYLOAD", "REPEATED_COMPUTE"
    ],
    "reliability": [
      "MISSING_TIMEOUT", "UNHANDLED_EXCEPTION", "DEEP_RECURSION",
      "RACE_CONDITION"
    ],
    "security": ["HARDCODED_SECRET"],
    "operational_excellence": ["DEAD_CODE", "CIRCULAR_IMPORT"],
    "cost_optimization": [
      "UNBOUNDED_CACHE", "GLOBAL_ACCUMULATOR", "OVERFETCH_COLUMNS"
    ]
  }
}
```

#### B. Uyum skor hesabı
```python
def compute_framework_compliance(
    issues: list[Issue],
    framework: dict
) -> dict[str, ComplianceScore]:
    result = {}
    for pillar, pattern_codes in framework.items():
        violations = [i for i in issues if i.code in pattern_codes]
        max_score = 100
        penalty = sum({"high": 25, "medium": 10, "low": 3}[i.severity] for i in violations)
        result[pillar] = ComplianceScore(
            score=max(0, max_score - penalty),
            violations=len(violations),
            violations_breakdown=Counter(i.code for i in violations),
        )
    return result
```

#### C. UI
Sağlık skoru gauge'ının altında küçük "rozet şeridi":

```
OWASP Top 10 (2025): 8/10 ✓     AWS Well-Architected
                                  ├─ Performance Efficiency: 65 ⚠️
                                  ├─ Reliability: 80 ✓
                                  ├─ Security: 95 ✓
                                  └─ Cost Optimization: 58 ⚠️
```

#### D. Filtreleme
Sorun listesinin üstüne filter: "OWASP uyumu için kritik olanlar (5)", "Performance Efficiency (12)" gibi.

### Bağımlılıklar
- MVP yeterli.
- Mapping JSON elle hazırlanır (1 günlük curate işi).

### Efor: **M** (2 gün)
- Mapping JSON + curate: 1 gün.
- Skorlama + UI: 1 gün.

### ROI
**Orta.** Kurumsal satışta yüksek değer, geliştirici/maker pazarında orta. B2B yöneliyorsak mutlaka eklenmeli.

---

## 2.6 Otomatik GitHub PR Oluşturma (OAuth)

### Amaç
Kullanıcı raporda tick'lediği fix'leri tek butonla GitHub'da PR olarak açar.

### KodHekim için neden gerekli?
- Demo'da inanılmaz güçlü an: "Tıkla → PR açıldı."
- "Düzeltme önerisi"nden "düzeltme uygulayan asistan"a sıçrama.
- Üretimde gerçek bir iş kazanım yolu.

### Teknik tasarım

#### A. GitHub OAuth App
- KodHekim için GitHub OAuth App kayıt et.
- Scopes: `repo` (private dahil) veya `public_repo` (sadece public).
- Callback: `https://kodhekim.app/auth/github/callback`.

#### B. Auth flow
```
GET /api/auth/github/login
  → 302 redirect to github.com/login/oauth/authorize

GET /api/auth/github/callback?code=...
  → exchange code for access token
  → JWT session cookie set
  → redirect to /report/[jobId]
```

#### C. PR oluşturma endpoint
```
POST /api/report/:job_id/create-pr
  Auth: session cookie required
  Body: { "accepted_fix_ids": ["issue-001", "issue-003"] }
  Response: { "pr_url": "https://github.com/user/repo/pull/42" }
```

Backend akışı:
1. Kullanıcı access token'ı al.
2. Repo'yu fork et (kullanıcının fork'u yoksa).
3. Yeni branch oluştur: `kodhekim/fix-{job_id}`.
4. Her accepted fix için:
   - Cerrah'ın diff'ini uygula (`git apply`).
   - Test code'u varsa `tests/` altına ekle.
5. Commit: "KodHekim: fix N+1 query + missing timeout".
6. Push to fork.
7. PR aç: `gh api repos/:owner/:repo/pulls`.
8. PR body'sine rapor özet + sağlık skoru farkı + KodHekim badge.

#### D. PR template
```markdown
## 🩺 KodHekim Otomatik Düzeltme Önerisi

Bu PR, KodHekim analizinin bulduğu **3 sorun** için düzeltmeler içerir.

### Sağlık Skoru
- Önce: 62/100
- Sonra (tahmini): 89/100

### Düzeltilen Sorunlar
- ✅ [N1_QUERY] src/api/users.py:47
- ✅ [MISSING_TIMEOUT] src/services/payment.py:14
- ✅ [UNBOUNDED_CACHE] src/utils/cache.py:8

### Test Kapsamı
2 yeni unit test eklendi (`tests/test_kodhekim_fixes.py`).

### Risk Notları
- N+1 fix: orta risk (yan etki: response shape değişti)
- Timeout fix: düşük risk
- Cache fix: düşük risk

Detaylı rapor: https://kodhekim.app/report/{job_id}
```

#### E. UI
Rapor sayfasında: **"GitHub'a PR Aç"** butonu (auth gerekli, fix tick'lenmiş olmalı).
- Tıklanınca confirmation modal: "3 fix uygulanacak ve PR açılacak. Devam?"
- Loading: "Fork ediliyor... commit'leniyor... PR açılıyor..."
- Sonuç: PR linki + "PR'a Git" butonu.

### Bağımlılıklar
- MVP'nin Cerrah diff'leri.
- Kullanıcı hesabı sistemi (basit JWT yeterli).
- §2.3 (test cases) — eklemek opsiyonel.

### Efor: **L** (5-6 gün)
- OAuth app + auth flow: 1 gün.
- Fork + branch + commit mantığı: 2 gün.
- PR template + edge case: 1 gün.
- UI auth state + modal: 1 gün.
- Test edge case'leri (conflict, fork zaten var, vb.): 1 gün.

### ROI
**Yüksek.** Demo değeri büyük, üretimde bir "premium" özellik olabilir. Auth karmaşıklığı en büyük efor.

---

## 2.7 GitHub Action Wrapper

### Amaç
`kodhekim/action@v1` GitHub Action ile her PR'da otomatik tarama + comment.

### KodHekim için neden gerekli?
- GitHub Marketplace'te listelenir → discoverability.
- "CI/CD'ye entegre" hissi profesyonel kategoriye taşır.
- Recurring usage — kullanıcı bir kere kurar, her PR'da KodHekim çalışır.

### Teknik tasarım

#### A. Action repo
Ayrı repo: `kodhekim/action`.

`action.yml`:
```yaml
name: KodHekim Code Health Check
description: AI-powered code health diagnosis
inputs:
  api_key:
    description: KodHekim API key
    required: true
  mode:
    description: static | hybrid | deep
    default: hybrid
  fail_on_threshold:
    description: Fail if health score below this
    default: '70'
runs:
  using: composite
  steps:
    - uses: actions/checkout@v4
    - name: Run KodHekim
      shell: bash
      run: |
        curl -X POST https://api.kodhekim.app/api/analyze/ci \
          -H "Authorization: Bearer ${{ inputs.api_key }}" \
          -d "{\"repo_path\": \".\", \"mode\": \"${{ inputs.mode }}\"}"
```

#### B. CI-specific endpoint
```
POST /api/analyze/ci
  Auth: API key
  Body: { "diff_only": true, "base_ref": "main" }
  Response: { "report_url": "...", "summary": {...} }
```

CI modunda:
- Sadece PR'da değişen dosyaları tara.
- Hızlı statik mod default.
- Sonuçları PR comment olarak yapıştırılabilen markdown formatında dön.

#### C. PR comment template
```markdown
## 🩺 KodHekim Code Health Report

**Bu PR'ın sağlık etkisi:** ⚠️ Skoru 78 → 65 (-13)

### Yeni Sorunlar (4)
| Severity | Code | File | Issue |
|---|---|---|---|
| 🔴 | N1_QUERY | src/api/users.py:47 | ... |
| 🟡 | MISSING_TIMEOUT | src/svc.py:12 | ... |

[Detaylı rapor](https://kodhekim.app/report/...)
```

### Bağımlılıklar
- API key sistemi (basit token table).
- Hızlı statik mod (MVP'de zaten var).

### Efor: **M** (3 gün)
- Action repo + composite action: 1 gün.
- CI endpoint + diff_only mode: 1.5 gün.
- PR comment yapıştırma (Action içinde gh CLI): 0.5 gün.

### ROI
**Orta-Yüksek.** Pasif gelir / sürekli kullanıcı kanalı. Marketplace'te bulunabilirlik avantajı.

---

## 2.8 Demo Cache / Hemen Dene

### Amaç
Landing'de "🐍 Flask Todo", "🔬 ML Pipeline", "🌐 Django Blog" gibi 3 önbelleklenmiş örnek repo butonu. Tıklayınca anında rapor (canlı analiz beklemez).

### KodHekim için neden gerekli?
- Yeni kullanıcı landing'i açtığında "deneyim al" yolu.
- Demo videosu yerine geçer (kullanıcı kendi tıklar).
- Jüri/incelemeci için canlı demo riskini sıfırlar.

### Teknik tasarım

> Detaylar [developer.md §16.2](developer.md) içinde mevcut. Kısaca:
- `scripts/build_cached_demos.py` ile 3 demo repo pre-render edilir.
- `backend/data/cached_demos/<slug>.json` olarak kaydedilir.
- `GET /api/report/demo-<slug>` cache servis.
- Landing'de 3 buton.

### Bağımlılıklar
- MVP'nin tam pipeline'ı.

### Efor: **S** (1-2 gün)
- Demo repo seçimi + kötü kod ekleme: 0.5 gün.
- Build script: 0.5 gün.
- Frontend buton + route guard: 0.5 gün.

### ROI
**Orta-Yüksek.** Public site launch'tan önce mutlaka olmalı.

---

# Bölüm 3 — Operasyonel / Üretim Hazırlığı

Bu özellikler MVP sonrası "ürün şirketi" olmaya geçiş için zorunlu olanlardır. Tek tek küçük değil ama burada birleştirilmiş haliyle sunulur.

## 3.1 Kullanıcı Hesabı + Auth

- GitHub OAuth (§2.6 ile aynı altyapı).
- E-posta + sihirli link alternatifi.
- JWT session cookie + refresh token.
- Profil sayfası, hesap silme, GDPR uyumu.

**Efor:** M (3-4 gün)

## 3.2 Analiz Geçmişi / Dashboard

- Kullanıcının yaptığı tüm analizlerin listesi.
- Repo başına trend (§2.4 ile entegre).
- "Bu repo'yu tekrar analiz et" tek tık.
- Favorite/star.

**Efor:** M (3 gün)

## 3.3 Rate Limit + Abuse Protection

- Anonim kullanıcı: 3 analiz/gün/IP.
- Authenticated: 20 analiz/gün.
- Pro tier: 200/gün.
- Redis-based token bucket.
- Repo URL whitelist'i (cooperation amaçlı).

**Efor:** S (1 gün)

## 3.4 Tiered Pricing + Billing

- Free: 3 analiz/gün, hibrit mod.
- Pro ($19/ay): sınırsız analiz, Derin mod, Chat.
- Team ($99/ay): 10 kullanıcı, GitHub Action, badge.
- Enterprise: özel — SSO, on-prem.
- Stripe entegrasyon.

**Efor:** L (1 hafta)

## 3.5 Webhook Bildirimleri

- Analiz tamamlandığında Slack/Discord/email.
- Kullanıcı tanımlı endpoint'lere POST.

**Efor:** S (1 gün)

## 3.6 Monorepo Desteği

- Bir repo içinde birden fazla "logical project" (alt klasör başına).
- Her biri ayrı analiz, ayrı rapor.
- Birleşik skor opsiyonu.

**Efor:** M (3 gün)

## 3.7 Private Repo Desteği

- GitHub OAuth `repo` scope.
- Clone token'ı backend'de geçici olarak tut, analiz sonrası sil.
- Audit log.

**Efor:** S (§3.1 üzerine 1 gün)

## 3.8 Repo Karşılaştırma

- İki repo URL'si gir, sağlık skorlarını yan yana göster.
- "Açık kaynak rakiplerimizle nasıyız?" use case.

**Efor:** M (2 gün)

---

# Bölüm 4 — Önerilen 2 Aylık Ramping Plan

Tek geliştirici varsayımıyla:

### Ay 1: Analiz derinliği + en yüksek wow

| Hafta | Hedef |
|---|---|
| Hafta 1 | §1.1 Repo Karakterizasyonu (M) |
| Hafta 2 | §2.1 AI Hekim Konsültasyonu (M) |
| Hafta 3 | §1.3 Compound Pattern Detection (S) + §1.4 Git Geçmişi (S) + §2.3 AI Test Cases (S) |
| Hafta 4 | §1.2 Cross-File Call Graph (L — bu hafta başlanır, sonraki haftaya taşabilir) |

**Ay 1 sonu çıktısı:** 4 yeni "wow" özellik, analiz doğruluğu ciddi artmış, chat ile yapışkanlık eklenmiş.

### Ay 2: Pazara açılma + JS/TS

| Hafta | Hedef |
|---|---|
| Hafta 5 | §1.2 bitir + §2.5 OWASP Uyum (M) |
| Hafta 6 | §3.1 Auth + §3.2 Dashboard + §3.3 Rate Limit |
| Hafta 7-8 | §1.6 JS/TS aşaması (XL) — pazarı 2x büyüt |

**Ay 2 sonu çıktısı:** Kullanıcı hesabı + JS/TS desteği + compliance konumlanması.

### Daha sonra (önceliğe göre)
- §2.6 GitHub PR Oluşturma (L)
- §2.7 GitHub Action (M)
- §2.2 Provider Karşılaştırma (M)
- §2.4 Sağlık Zaman Çizelgesi (M)
- §3.4 Pricing + Billing (L)
- §1.5 Embedding Discovery (XL — araştırma sprint'i)

---

# Bölüm 5 — Stratejik Notlar

## Konumlandırma evrimi
- **MVP:** "Repo'nu tarat, kod sağlığını öğren." — geliştirici aracı.
- **Ay 1 sonu:** "Repo'nun kod hekimine danış." — danışman.
- **Ay 2 sonu:** "Ekibinin kod sağlığı platformu." — kurumsal araç.

## Müşteri segmentleri
- **Bireysel geliştirici / freelancer** — free tier, GitHub badge ile viral.
- **Küçük startup CTO** — Pro tier, "fatura şişiyor" duyarlı.
- **Mid-size SaaS şirketi** — Team tier, GitHub Action ile CI/CD.
- **Enterprise** — özel kontrat, on-prem opsiyonu.

## Açık kaynak vs ticari denge
- Statik kural motoru + Profiler core'u **MIT lisansı altında açık kaynak** olabilir.
- LLM-powered ajanlar (Chat, Derin mod, Cerrah'ın test üretimi) **kapalı/managed**.
- Bu hibrit model GitLab, PostHog, Sentry'nin başarılı modelidir.

## Pazar pozisyonlama
KodHekim ne **değil**:
- Linter (Pylint/ESLint daha hızlı, ücretsiz).
- Güvenlik tarayıcı (Snyk, GitGuardian daha kapsamlı).
- APM (Datadog, New Relic — runtime).

KodHekim ne **dir**:
- **Önleyici kod sağlığı tanı**: Linter'dan derin, APM'den önce, güvenlik tarayıcısından geniş.
- "AI-native" kod review eli — bağlam anlayan, soru cevaplayan.

## Risk listesi
- **LLM maliyetleri:** Chat ve Derin mod'un yaygınlaşması Gemini/Cerebras faturasını ciddi etkiler. Free tier sınırlamaları net olmalı.
- **Açık kaynak rakipleri:** Sourcery, DeepSource, Codacy — fiyat avantajı yok, **bağlam anlayışı** avantajı vurgulanmalı.
- **Yanlış pozitif yorgunluğu:** Kullanıcı 2-3 sefer yanlış sorun gördükten sonra terk eder. Profiler precision'ı sürekli izlenmeli.
- **GitHub policy:** Action'lar veya OAuth flow'ları policy değişikliklerinde etkilenebilir.

---

# Bölüm 6 — Son Söz

Bu döküman MVP'den **ürün şirketine** geçiş haritasıdır. Her özelliğin ROI'si tartışılabilir; sıralama önerimdir, sen kendi gözleminle revize edersin.

Ana öneri: **Ay 1'de §1.1 + §2.1'i** kesinlikle bitir. Bu ikisi, MVP'yi "linter+" konumundan "kod danışmanı" konumuna taşır ve geri kalan tüm özelliklerin temelini atar.

İyi şanslar.

---

## Ek: Hızlı Referans Tablosu

| ID | Özellik | Bölüm | Efor | Etki | Bağımlılık |
|---|---|---|---|---|---|
| 1.1 | Repo Karakterizasyonu | Analiz | M | 🔴 | — |
| 1.2 | Cross-File Call Graph | Analiz | L | 🔴 | — |
| 1.3 | Compound Pattern | Analiz | S | 🟠 | 1.2 (yumuşak) |
| 1.4 | Git Geçmişi | Analiz | S | 🟠 | — |
| 1.5 | Embedding Discovery | Analiz | XL | 🟠 | — |
| 1.6 | Multi-Language | Analiz | XL/dil | 🔴 | — |
| 2.1 | AI Hekim Chat | Jüri | M | 🔴 | 1.1 (yumuşak) |
| 2.2 | Provider Karşılaştırma | Jüri | M | 🟡 | — |
| 2.3 | AI Test Cases | Jüri | S | 🟠 | — |
| 2.4 | Skor Zaman Çizelgesi | Jüri | M | 🟡 | 1.1 (yumuşak) |
| 2.5 | OWASP Uyum | Jüri | M | 🟡 | — |
| 2.6 | GitHub PR | Jüri | L | 🟡 | 3.1, 3.7 |
| 2.7 | GitHub Action | Jüri | M | 🟡 | — |
| 2.8 | Demo Cache | Jüri | S | 🟡 | — |
| 3.1 | Auth | Üretim | M | — | — |
| 3.2 | Dashboard | Üretim | M | — | 3.1 |
| 3.3 | Rate Limit | Üretim | S | — | — |
| 3.4 | Pricing | Üretim | L | — | 3.1 |
| 3.5 | Webhooks | Üretim | S | — | — |
| 3.6 | Monorepo | Üretim | M | — | — |
| 3.7 | Private Repo | Üretim | S | — | 3.1 |
| 3.8 | Repo Karşılaştırma | Üretim | M | — | — |
