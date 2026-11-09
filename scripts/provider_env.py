"""Explicit, opt-in provider setup. The provider library itself never borrows keys."""

import os


def configure_openrouter(model="openai/gpt-4.1-mini", reasoning="default"):
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is unavailable. Configure it locally; do not paste it into the UI.")
    if not model.strip():
        raise RuntimeError("Choose a nonempty model id.")
    if reasoning not in {"default", "off"}:
        raise RuntimeError("Reasoning must be default or off.")
    os.environ.update(HISABGUARD_LLM_BASE_URL="https://openrouter.ai/api/v1",
                      HISABGUARD_LLM_API_KEY=key,
                      HISABGUARD_LLM_MODEL=model.strip(),
                      HISABGUARD_VISION_MODEL=model.strip(), HISABGUARD_REASONING_MODE=reasoning)
    return {"provider": "openrouter", "model": model.strip(), "reasoning": reasoning,
            "credential_storage": "process_environment_only"}
