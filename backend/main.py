"""KodHekim backend — FastAPI entry point.

Faz A: minimal scaffold; gerçek endpoint'ler Faz L'de eklenecek.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

app = FastAPI(
    title="KodHekim API",
    description="Çoklu AI ajan ekibiyle kod sağlığı tanı sistemi",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    return {
        "status": "ok",
        "providers_configured": {
            "cerebras": bool(os.getenv("CEREBRAS_API_KEY")),
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
        },
    }
