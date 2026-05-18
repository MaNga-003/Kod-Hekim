"""Manuel LLM smoke test — `.env`'deki API key'lerle gerçek çağrı yapar.

Kullanım (backend/ içinden):
    python ..\\scripts\\test_llm.py                       # default: cerebras + gpt-oss-120b
    python ..\\scripts\\test_llm.py --provider gemini --model gemini-2.5-flash
    python ..\\scripts\\test_llm.py --json                # structured output testi
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# `python scripts/test_llm.py` formunda doğrudan çalıştırıldığında backend importları çalışsın diye
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from llm.base import LLMError  # noqa: E402
from llm.registry import get_provider, list_supported  # noqa: E402


SIMPLE_PROMPT = "İki cümleyle bana N+1 query problemini açıkla."

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "problem": {"type": "string"},
        "severity": {"type": "string", "enum": ["high", "medium", "low"]},
        "fix_hint": {"type": "string"},
    },
    "required": ["problem", "severity", "fix_hint"],
}

JSON_PROMPT = (
    "Aşağıdaki kodu kısaca değerlendir ve verilen JSON şemasında dön:\n"
    "for u in users:\n"
    "    posts = Post.query.filter_by(user_id=u.id).all()"
)


def _short(text: str, n: int = 200) -> str:
    text = text.strip().replace("\n", " ")
    return text[:n] + ("…" if len(text) > n else "")


def main() -> int:
    parser = argparse.ArgumentParser(prog="test_llm")
    parser.add_argument("--provider", default="cerebras", choices=["cerebras", "gemini"])
    parser.add_argument("--model", default=None, help="Override model ID")
    parser.add_argument("--json", action="store_true", help="JSON schema modu")
    parser.add_argument("--list", action="store_true", help="Yalnız desteklenen modelleri listele")
    args = parser.parse_args()

    if args.list:
        for prov, models in list_supported().items():
            print(f"{prov}:")
            for m in models:
                print(f"  - {m}")
        return 0

    # Anahtar var mı?
    if args.provider == "cerebras" and not os.getenv("CEREBRAS_API_KEY"):
        print("[HATA] CEREBRAS_API_KEY .env içinde yok.")
        return 1
    if args.provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
        print("[HATA] GEMINI_API_KEY .env içinde yok.")
        return 1

    try:
        provider = get_provider(args.provider)  # type: ignore[arg-type]
    except LLMError as e:
        print(f"[HATA] Provider başlatılamadı: {e}")
        return 1

    model = args.model or provider.list_models()[0]
    print(f"[INFO] Provider: {args.provider} | Model: {model} | JSON: {args.json}")
    print()

    try:
        if args.json:
            resp = provider.complete(JSON_PROMPT, model=model, json_schema=JSON_SCHEMA)
        else:
            resp = provider.complete(SIMPLE_PROMPT, model=model)
    except LLMError as e:
        print(f"[HATA] Çağrı başarısız: {e}")
        return 1

    print(f"latency : {resp['latency_ms']} ms")
    print(f"tokens  : {resp['tokens_used']}")
    print(f"model   : {resp['model']}")
    print()
    print("--- text ---")
    print(_short(resp["text"], 500))
    if args.json:
        print()
        print("--- parsed json ---")
        print(resp["json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
