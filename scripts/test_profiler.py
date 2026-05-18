"""Manuel profiler ajan smoke testi — gerçek API kullanır.

Kullanım:
    python ..\\scripts\\test_profiler.py                # default cerebras
    python ..\\scripts\\test_profiler.py --provider gemini
    python ..\\scripts\\test_profiler.py --path <repo_path>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from agents.profiler import profiler_agent_hybrid, profiler_agent_static  # noqa: E402
from llm.registry import get_provider, resolve_model  # noqa: E402


DEFAULT_PATH = BACKEND / "tests" / "fixtures" / "bad_code_examples"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--provider", default="cerebras", choices=["cerebras", "gemini"])
    p.add_argument("--model", default=None)
    p.add_argument("--path", default=str(DEFAULT_PATH))
    p.add_argument("--mode", default="hybrid", choices=["hybrid", "static"])
    args = p.parse_args()

    if args.mode == "static":
        issues = profiler_agent_static(args.path)
    else:
        provider = get_provider(args.provider)  # type: ignore[arg-type]
        model = args.model or resolve_model(args.provider, "profiler")  # type: ignore[arg-type]
        print(f"[INFO] Provider: {args.provider} | Model: {model} | Path: {args.path}")
        issues = profiler_agent_hybrid(
            args.path,
            provider=provider,
            model=model,
            on_progress=lambda m: print(f"  · {m}"),
        )

    print()
    print(f"[SONUC] {len(issues)} issue (mode={args.mode})")
    by_code: dict[str, int] = {}
    by_sev = {"high": 0, "medium": 0, "low": 0}
    for i in issues:
        by_code[i.code] = by_code.get(i.code, 0) + 1
        by_sev[i.severity] += 1
    print(f"Severity: high={by_sev['high']}  medium={by_sev['medium']}  low={by_sev['low']}")
    print()
    print(f"{'ID':<10} {'SEV':<7} {'CODE':<24} {'CONF':<6} FILE:LINE")
    for i in issues:
        conf = f"{i.llm_confidence:.2f}" if i.llm_confidence is not None else "  -  "
        print(f"{i.id:<10} {i.severity:<7} {i.code:<24} {conf:<6} {i.file}:{i.line_start}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
