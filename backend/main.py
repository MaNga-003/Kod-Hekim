"""KodHekim backend — FastAPI entry point."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

from api.analyze import router as analyze_router  # noqa: E402
from api.badge import router as badge_router  # noqa: E402
from api.models import router as models_router  # noqa: E402
from api.report import router as report_router  # noqa: E402
from api.stream import router as stream_router  # noqa: E402


app = FastAPI(
    title="KodHekim API",
    description="Çoklu AI ajan ekibiyle kod sağlığı tanı sistemi",
    version="0.1.0",
)


def _allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://frontend-production-5646.up.railway.app",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(analyze_router)
app.include_router(stream_router)
app.include_router(report_router)
app.include_router(models_router)
app.include_router(badge_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "KodHekim",
        "version": "0.1.0",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health")
async def health() -> dict[str, object]:
    from analysis.ast_parser import tree_sitter_status  # noqa: WPS433

    ts = tree_sitter_status()
    langs = ts.get("languages", {})
    all_ok = all(langs.get(k) for k in ("python", "javascript", "typescript"))
    return {
        "status": "ok" if all_ok else "degraded",
        "providers_configured": {
            "cerebras": bool(os.getenv("CEREBRAS_API_KEY")),
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
        },
        "parser": {
            "tree_sitter": ts.get("available"),
            "languages": langs,
            "ready": all_ok,
        },
    }
