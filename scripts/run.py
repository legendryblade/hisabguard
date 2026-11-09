"""Run the real application with optional explicitly selected provider setup."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import uvicorn
from app import providers
from scripts.provider_env import configure_openrouter


def main():
    parser = argparse.ArgumentParser(description="Start HisabGuard; no credentials are printed or saved.")
    parser.add_argument("--provider", choices=["configured", "openrouter"], default="configured")
    parser.add_argument("--model", default="openai/gpt-4.1-mini")
    parser.add_argument("--reasoning", choices=["default", "off"], default="default")
    parser.add_argument("--port", type=int, default=8834)
    args = parser.parse_args()
    if args.provider == "openrouter":
        configure_openrouter(args.model, args.reasoning)
    status = providers.get_status()
    print("HisabGuard provider mode: " + (status["model_name"] if status["model_configured"] else "labelled deterministic demo"))
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
