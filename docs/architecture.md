# KodHekim — Mimari

Bu döküman ürünün kuş bakışı mimarisini özetler. Tam teknik detay için
[developer.md](../developer.md).

## Sistem Akışı

```mermaid
flowchart TB
    User([👤 Geliştirici])
    subgraph Frontend["FRONTEND · Next.js 14"]
        Landing["/<br/>Landing<br/>URL + mod"]
        Analyze["/analyze/[jobId]<br/>Canlı log + 4 ajan kartı"]
        Report["/report/[jobId]<br/>Sağlık skoru + bulgular"]
    end

    subgraph Backend["BACKEND · FastAPI + LangGraph"]
        API["api/<br/>analyze · stream (SSE) · report · models · badge"]
        subgraph Orchestrator["Orchestrator (LangGraph)"]
            P["🔍 Profiler<br/>Dr. Müfettiş"]
            I["📊 Impact<br/>Dr. Ölçücü"]
            S["🩹 Surgeon<br/>Dr. Cerrah"]
            C["⚕️ Chief<br/>Dr. Hekimbaşı"]
            P --> I --> S --> C
        end
        subgraph Analysis["Analiz Katmanı"]
            Clone["repo_cloner<br/>shallow clone"]
            Walk["file_walker"]
            AST["ast_parser"]
            Rules["22 statik kural<br/>(plugin)"]
        end
        subgraph LLM["LLM Provider Soyutlaması"]
            Cerebras["Cerebras<br/>gpt-oss-120b · llama · qwen · glm"]
            Gemini["Gemini<br/>2.5 Pro · 2.5 Flash"]
        end
    end

    User -->|"URL + mod"| Landing
    Landing -->|"POST /api/analyze"| API
    API -->|"SSE"| Analyze
    Analyze -->|"all_done"| Report
    API --> Orchestrator
    Orchestrator --> Analysis
    Orchestrator --> LLM
```

## 4 Ajan Pipeline

```mermaid
sequenceDiagram
    participant U as Kullanıcı
    participant API as FastAPI
    participant SE as Statik Motor
    participant Pf as Dr. Müfettiş
    participant Im as Dr. Ölçücü
    participant Su as Dr. Cerrah
    participant Hk as Dr. Hekimbaşı

    U->>API: POST /api/analyze {url, mode}
    API->>API: Repo clone (depth=1)
    API->>SE: 22 kural × N dosya
    SE-->>Pf: Aday sorunlar
    Pf->>Pf: LLM confirm (Hibrit)
    Pf-->>Im: Doğrulanmış issue'lar
    Im->>Im: Sayısal etki + LLM açıklama
    Im-->>Su: Issue + impact
    Su->>Su: LLM unified diff + risk
    Su-->>Hk: Issue + impact + fix
    Hk->>Hk: Sağlık skoru + yönetici özeti
    Hk-->>API: FinalReport
    API-->>U: SSE all_done → /report/[jobId]
```

## Üç Analiz Modu

| Mod | Akış | LLM çağrısı | Tipik süre (50 dosya) |
|---|---|---|---|
| **Statik** | Yalnızca kural motoru + heuristic etki/rapor | 0 | < 5 sn |
| **Hibrit** *(default)* | Kural + LLM confirm + LLM impact/surgeon/chief | ~10–30 | 30–90 sn |
| **Derin** | AST özeti + tam kod LLM'e direkt + pipeline | ~5–15 | 1–3 dk |

## Bileşen Sözlüğü

| Modül | Sorumluluk |
|---|---|
| `backend/analysis/repo_cloner.py` | Shallow clone, boyut/private guard |
| `backend/analysis/file_walker.py` | Uzantı filtresi, exclude dizinler |
| `backend/analysis/ast_parser.py` | `ast.parse` sarıcısı |
| `backend/analysis/static_rules/` | 22 örüntü plugin (her biri ayrı dosya) |
| `backend/analysis/scan.py` | Tüm kuralları sıraya sok, IssueCandidate listesi |
| `backend/llm/` | Cerebras + Gemini soyutlaması (TypedDict response) |
| `backend/agents/` | 4 ajan + orchestrator (LangGraph) |
| `backend/api/` | FastAPI router'ları (analyze, stream, report, models, badge) |
| `frontend/app/` | 3 rota — landing, analyze, report |
| `frontend/lib/` | `api-client.ts`, `sse-client.ts` |

## Veri Tipleri Akışı

```
IssueCandidate (statik)  →  Issue (LLM-confirmed)
                                 ↓
                           ImpactBreakdown
                                 ↓
                            FixSuggestion
                                 ↓
                          FinalReport (health + summary)
```
