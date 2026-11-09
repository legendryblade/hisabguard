"""Diagnose one synthetic vision proposal without printing credentials or real documents."""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError
from app import demo, providers
from app.schemas import Extraction
from app.store import Store
from scripts.provider_env import configure_openrouter


def main():
    configure_openrouter("nvidia/nemotron-3.5-super-vl:free", "off")
    captured = []
    original = providers._assistant

    def capture(payload):
        message = original(payload)
        captured.append(message.get("content"))
        return message

    providers._assistant = capture
    with tempfile.TemporaryDirectory(prefix="hisabguard-vision-check-") as folder:
        store = Store(folder)
        demo.seed(store)
        image = store.original_path(store.detail(1)["evidence"][0]["id"])[0].read_bytes()
        try:
            result = providers.extract_image(image, "image/png")
            print("Valid synthetic invoice proposal:", {key: result.get(key) for key in ("kind", "amount_bdt", "transaction_id", "trip_ref")})
        except providers.ProviderError as exc:
            print("Safe provider error:", str(exc))
            if captured:
                try:
                    parsed = json.loads(captured[-1])
                    print("Output field types:", {key: type(value).__name__ for key, value in parsed.items()})
                    try:
                        Extraction.model_validate(parsed)
                    except ValidationError as error:
                        print("Validation diagnostics:", [{"field": item["loc"], "type": item["type"]} for item in error.errors(include_input=False)])
                except (ValueError, TypeError):
                    print("Output is not one JSON object; fenced or commentary text is not accepted.")
    providers._assistant = original


if __name__ == "__main__":
    main()
