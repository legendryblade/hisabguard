"""Record a real synthetic browser workflow; demo mode is explicit, never a live fallback."""

import argparse
import asyncio
import json
import os
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".cache" / "playwright"))

import uvicorn
from playwright.async_api import async_playwright, expect
from app import providers
from app.main import create_app
from scripts.provider_env import configure_openrouter

BASE = "http://127.0.0.1:8865"


async def record(folder, mode, seconds):
    result = {"mode": mode, "synthetic_only": True, "successful": False,
              "model": providers.get_status().get("model_name"), "steps": [],
              "disclosure": "Demo mode does not prove live AI. Live mode performs actual provider calls; failures are not substituted."}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="msedge", headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 1000},
                                            record_video_dir=str(folder), record_video_size={"width": 1440, "height": 1000},
                                            accept_downloads=True)
        page = await context.new_page()
        page.set_default_timeout(15000)
        started = time.monotonic()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def pause(label, duration=5):
            result["steps"].append({"step": label, "seconds_from_start": round(time.monotonic() - started, 2)})
            await page.wait_for_timeout(duration * 1000)

        async def investigate():
            async with page.expect_response(lambda r: r.url.endswith("/api/trips/1/investigate"), timeout=240000) as response:
                await page.get_by_role("button", name="Investigate trip", exact=True).click()
            response = await response.value
            if not response.ok:
                raise RuntimeError(f"Actual investigation failed with HTTP {response.status}; no demo success substituted.")
            data = await response.json()
            assert data["investigations"][-1]["mode"] == ("model" if mode == "live" else "demo")
            return data

        try:
            await page.goto(BASE)
            await expect(page.get_by_role("heading", name="Trip settlements", exact=True)).to_be_visible()
            await pause("Synthetic exception queue")
            await page.get_by_role("link", name="Open trip TRIP-104").click()
            await expect(page.get_by_role("heading", name="TRIP-104", exact=True)).to_be_visible()
            await pause("Invoice, received payment and advance balance", 7)
            await page.locator("#evidence-1").get_by_role("button", name="View original").click()
            await expect(page.locator("#evidence-1 img")).to_be_visible()
            await page.locator("#evidence-1 .original-preview").scroll_into_view_if_needed()
            await pause("Actual synthetic original", 6)
            await page.locator(".desk-tabs a[href='#investigation']").click()
            initial = await investigate()
            await pause("Persisted investigation and its actual next question", 8)
            assert initial["settlement"]["outstanding_bdt"] == "7000.00"
            await page.get_by_label("Reply text", exact=False).fill("The driver says the customer handed him the remaining BDT 7000 in cash. He still has the cash, but no receipt or owner handover record is available.")
            async with page.expect_response(lambda r: r.url.endswith("/api/trips/1/reply")) as response:
                await page.get_by_role("button", name="Record reply as statement").click()
            replied = await (await response.value).json()
            assert replied["settlement"]["outstanding_bdt"] == "7000.00"
            await pause("A statement did not turn into money received", 6)
            current = await investigate()
            assert current["settlement"]["outstanding_bdt"] == "7000.00"
            result["first_question"] = initial["investigations"][-1]["question"]
            result["second_question"] = current["investigations"][-1]["question"]
            result["second_recipient"] = current["investigations"][-1]["recipient"]
            if mode == "live":
                recipient = (result["second_recipient"] or "").casefold()
                if "driver" not in recipient or "customer" in recipient:
                    raise RuntimeError("Live reassessment did not route the cash-handover request to the driver; preserve this failed recording instead of claiming adaptive success.")
            await pause("Reassessed question and evidence citations", 8)
            action = current["actions"][-1]
            await page.locator(".desk-tabs a[href='#followups']").click()
            await pause("Exact approval draft", 6)
            async with page.expect_response(lambda r: r.url.endswith(f"/api/actions/{action['id']}/decision")) as response:
                await page.locator(f"#action-{action['id']}").get_by_role("button", name="Approve draft").click()
            assert (await response.value).ok
            async with page.expect_download() as download:
                await page.locator(f"#action-{action['id']}").get_by_role("button", name="Download approved text").click()
            await (await download.value).save_as(str(folder / "approved-synthetic-followup.txt"))
            await pause("Approved text exported, not sent", 6)
            await page.locator(".closure-panel").scroll_into_view_if_needed()
            await expect(page.get_by_role("button", name="Close settlement", exact=True)).to_be_disabled()
            await pause("Settlement remains blocked by missing money/evidence", 5)
            await page.locator(".desk-tabs a[href='#trip-activity']").click()
            await pause("Actual operator and investigation audit trail", max(5, seconds - (time.monotonic() - started)))
            result["successful"] = not errors
            result["javascript_errors"] = errors
        except Exception as exc:
            result["error"] = str(exc)[:500]
            await page.wait_for_timeout(4000)
        finally:
            result["elapsed_seconds"] = round(time.monotonic() - started, 2)
            video = page.video
            await context.close()
            if video:
                result["video"] = str(Path(await video.path()).relative_to(ROOT))
            await browser.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="Record only synthetic HisabGuard data in an isolated store.")
    parser.add_argument("--mode", choices=["live", "demo"], default="live")
    parser.add_argument("--provider", choices=["configured", "openrouter"], default="configured")
    parser.add_argument("--model", default="nvidia/nemotron-3.5-super-vl:free")
    parser.add_argument("--reasoning", choices=["default", "off"], default="off")
    parser.add_argument("--seconds", type=int, default=90)
    args = parser.parse_args()
    if not 30 <= args.seconds <= 180:
        parser.error("seconds must be between 30 and 180")
    if args.mode == "live" and args.provider == "openrouter":
        configure_openrouter(args.model, args.reasoning)
    if args.mode == "live" and not providers.get_status()["model_configured"]:
        parser.error("Live mode needs configured credentials. Use explicit --mode demo for a labelled UI preview.")
    if args.mode == "demo":
        providers.get_status = lambda: {"model_configured": False, "model_name": None, "vision_configured": False, "stt_configured": False}
    os.environ.pop("HISABGUARD_ACCESS_TOKEN", None)
    os.environ["HISABGUARD_SEED_DEMO"] = "1"
    folder = ROOT / "artifacts" / ("recording-" + args.mode + "-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    folder.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="hisabguard-recording-") as data:
        server = uvicorn.Server(uvicorn.Config(create_app(data), host="127.0.0.1", port=8865, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(.1)
            if not server.started:
                raise RuntimeError("Isolated recording server did not start")
            result = asyncio.run(record(folder, args.mode, args.seconds))
        finally:
            server.should_exit = True
            thread.join(timeout=10)
    (folder / "recording.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Recording mode:", args.mode, "successful:", result["successful"], "elapsed:", result["elapsed_seconds"])
    print("Artifact:", result.get("video", str(folder)))
    if result.get("error"):
        print("Recording failed:", result["error"])
    return 0 if result["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
