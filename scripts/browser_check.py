"""Real Edge walkthrough against an isolated live server; never deletes user data."""

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import uvicorn
from PIL import Image, ImageDraw
from playwright.async_api import async_playwright, expect

from app import providers
from app.main import create_app

ARTIFACTS = ROOT / "artifacts"
BASE = "http://127.0.0.1:8864"
CHECKS = []


def check(label, condition):
    if not condition:
        raise AssertionError(label)
    CHECKS.append(label)
    print("PASS " + label)


def image_bytes():
    image = Image.new("RGB", (680, 320), "white")
    draw = ImageDraw.Draw(image)
    draw.text((30, 40), "SYNTHETIC TEST PAYMENT - NOT A REAL RECEIPT", fill="black")
    draw.text((30, 90), "TRIP-104 | Amount BDT 7000.00 | Test transaction FINAL-104", fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def detail(page, trip_id=1):
    response = await page.request.get(f"{BASE}/api/trips/{trip_id}")
    assert response.ok
    return await response.json()


async def write_click(page, locator, endpoint):
    async with page.expect_response(lambda r: r.url.endswith(endpoint) and r.request.method == "POST") as info:
        await locator.click()
    response = await info.value
    if not response.ok:
        raise AssertionError(f"{endpoint}: HTTP {response.status} {(await response.text())[:160]}")
    await expect(page.locator(".task-feedback .loading")).to_have_count(0)
    return await response.json()


async def add_typed(page, kind, amount, title, trip_id=1):
    await page.get_by_role("button", name="Add evidence", exact=True).click()
    form = page.locator(".evidence-intake")
    await form.get_by_label("Evidence title", exact=True).fill(title)
    await form.get_by_label("Evidence kind", exact=False).select_option(kind)
    await form.get_by_label("Amount (BDT)", exact=False).fill(amount)
    result = await write_click(page, form.get_by_role("button", name="Add draft record"), f"/api/trips/{trip_id}/evidence")
    return result["evidence"][-1]["id"]


async def review(page, eid, amount=None, transaction_id=None):
    ticket = page.locator(f"#evidence-{eid}")
    await ticket.get_by_role("button", name="Review evidence", exact=True).click()
    if amount is not None:
        await ticket.get_by_label("Amount (BDT)", exact=False).fill(amount)
    if transaction_id is not None:
        await ticket.locator("input[name=transaction_id]").fill(transaction_id)
    await ticket.get_by_role("checkbox").check()
    return await write_click(page, ticket.get_by_role("button", name="Confirm evidence"), f"/api/evidence/{eid}/review")


async def workflow(page):
    await page.goto(BASE + "/")
    await expect(page.get_by_role("heading", name="Trip settlements", exact=True)).to_be_visible()
    await expect(page.get_by_role("link", name="Open trip TRIP-104")).to_be_visible()
    check("Root rendered actual trip queue and synthetic disclosure", await page.locator(".demo-banner").count() == 1)
    await page.screenshot(path=str(ARTIFACTS / "queue-desktop.png"))
    await page.get_by_role("link", name="Open trip TRIP-104").click()
    await expect(page.get_by_role("heading", name="TRIP-104", exact=True)).to_be_visible()
    start = await detail(page)
    check("TRIP-104 starts with 7000 outstanding and 1500 advance balance", start["settlement"]["outstanding_bdt"] == "7000.00" and start["settlement"]["advance_balance_bdt"] == "1500.00")
    close = page.get_by_role("button", name="Close settlement", exact=True)
    await expect(close).to_be_disabled()
    first = page.locator(f"#evidence-{start['evidence'][0]['id']}")
    await first.get_by_role("button", name="View original").click()
    await expect(first.locator("img")).to_be_visible()
    check("Private synthetic original renders from authenticated blob", await first.locator("img").evaluate("img => img.complete && img.naturalWidth > 0"))

    current = await write_click(page, page.get_by_role("button", name="Investigate trip", exact=True), "/api/trips/1/investigate")
    check("Demo mode is honestly disclosed and runs persisted tools", current["investigations"][-1]["mode"] == "demo" and len(current["investigations"][-1]["steps"]) >= 4)
    await expect(page.get_by_label("Reply text", exact=False)).to_be_visible()
    aid = current["actions"][-1]["id"]
    await write_click(page, page.locator(f"#action-{aid}").get_by_role("button", name="Approve draft"), f"/api/actions/{aid}/decision")
    async with page.expect_download() as download:
        await page.locator(f"#action-{aid}").get_by_role("button", name="Download approved text").click()
    downloaded = await download.value
    content = Path(await downloaded.path()).read_text(encoding="utf-8")
    check("Approved follow-up downloads sourced outstanding without sending", "7000.00" in content and (await detail(page))["settlement"]["outstanding_bdt"] == "7000.00")

    await page.get_by_label("Reply text", exact=False).fill("Customer promises the remaining BDT 7000 tomorrow, but has supplied no receipt.")
    replied = await write_click(page, page.get_by_role("button", name="Record reply as statement"), "/api/trips/1/reply")
    check("A promise remains statement evidence and does not reduce outstanding", replied["evidence"][-1]["kind"] == "statement" and replied["settlement"]["outstanding_bdt"] == "7000.00")
    check("Evidence revision invalidates the previously approved export", replied["trip"]["revision"] > current["trip"]["revision"] and (await page.request.get(f"{BASE}/api/actions/{aid}/export")).status == 409)
    await expect(page.locator(f"#action-{aid}").get_by_role("button", name="Download approved text")).to_have_count(0)
    await write_click(page, page.get_by_role("button", name="Investigate trip", exact=True), "/api/trips/1/investigate")
    before_upload = await detail(page)

    await page.get_by_role("button", name="Add evidence", exact=True).click()
    intake = page.locator(".evidence-intake")
    await intake.get_by_role("button", name="Upload image / audio", exact=True).click()
    await intake.get_by_label("Evidence title", exact=True).fill("Synthetic final payment screenshot")
    await intake.get_by_label("Kind hint", exact=False).select_option("payment")
    binary = image_bytes()
    await intake.locator("input[type=file]").set_input_files({"name": "synthetic-payment.png", "mimeType": "image/png", "buffer": binary})
    uploaded = await write_click(page, intake.get_by_role("button", name="Upload original", exact=True), "/api/trips/1/upload")
    eid = uploaded["evidence"][-1]["id"]
    check("Unconfigured OCR retains a real original as draft, never inventing amounts", uploaded["evidence"][-1]["extraction_error"] and uploaded["evidence"][-1]["state"] == "draft" and uploaded["settlement"]["outstanding_bdt"] == "7000.00")
    check("Pending follow-up becomes stale when new evidence arrives", any(action["status"] == "stale" for action in uploaded["actions"]) and uploaded["trip"]["revision"] > before_upload["trip"]["revision"])
    ticket = page.locator(f"#evidence-{eid}")
    await ticket.get_by_role("button", name="View original").click()
    await expect(ticket.locator("img")).to_be_visible()
    await review(page, eid, "7000.00", "FINAL-104")
    paid = await detail(page)
    check("Reviewed payment changes received money but advance still blocks closure", paid["settlement"]["outstanding_bdt"] == "0.00" and not paid["settlement"]["can_settle"])

    cash = await add_typed(page, "cash_return", "1500.00", "Synthetic driver cash returned")
    balanced = await review(page, cash)
    check("Both accounts balance only after reviewed cash return", balanced["settlement"]["can_settle"] and balanced["settlement"]["advance_balance_bdt"] == "0.00")
    await expect(close).to_be_disabled()
    ready = await write_click(page, page.get_by_role("button", name="Investigate trip", exact=True), "/api/trips/1/investigate")
    check("Current-revision completed investigation enables human closure review", ready["investigations"][-1]["status"] == "completed" and ready["trip"]["status"] == "ready_for_review")
    await page.locator(".closure-panel").get_by_role("checkbox").check()
    settled = await write_click(page, close, "/api/trips/1/close")
    check("Explicit owner closure persisted; no model closed the trip", settled["trip"]["status"] == "settled" and settled["audit"][-1]["actor"] == "operator")

    async with page.expect_popup() as popup:
        await page.get_by_role("button", name="Printable report", exact=True).click()
    report = await popup.value
    await expect(report.get_by_role("heading", name="TRIP-104 evidence packet")).to_be_visible()
    check("Printable packet contains real source-linked settlement and history", "Evidence index" in await report.inner_text("body") and "settled" in await report.inner_text("body"))
    await report.close()
    async with page.expect_download() as download:
        await page.get_by_role("button", name="JSON backup", exact=True).click()
    backup = json.loads(Path(await (await download.value).path()).read_text(encoding="utf-8"))
    check("Backup exports actual versioned records without keys or binary originals", backup["version"] == "hisabguard.backup.v1" and not backup["originals_included"])

    await page.goto(BASE + "/trips/3")
    await expect(page.get_by_role("heading", name="TRIP-108", exact=True)).to_be_visible()
    duplicate = await detail(page, 3)
    check("Repeated fuel receipt counts once and remains a blocking question", duplicate["settlement"]["expense_bdt"] == "3500.00" and any(issue["code"] == "duplicate_transaction" for issue in duplicate["settlement"]["issues"]))
    last = duplicate["evidence"][-1]["id"]
    ticket = page.locator(f"#evidence-{last}")
    await ticket.get_by_role("button", name="Review / correct record", exact=True).click()
    excluded = await write_click(page, ticket.get_by_role("button", name="Exclude evidence"), f"/api/evidence/{last}/review")
    check("Excluding duplicate retains audit/original and resolves duplicate issue", excluded["evidence"][-1]["state"] == "excluded" and not any(issue["code"] == "duplicate_transaction" for issue in excluded["settlement"]["issues"]))

    await page.goto(BASE + "/trips/new")
    await expect(page.get_by_role("heading", name="New trip", exact=True)).to_be_visible()
    for label, value in [("Customer", "Synthetic browser customer"), ("Driver", "Synthetic browser driver"), ("Truck", "TEST-101"), ("Origin", "Gazipur"), ("Destination", "Dhaka")]:
        await page.get_by_label(label, exact=False).fill(value)
    async with page.expect_response(lambda r: r.url.endswith("/api/trips") and r.request.method == "POST") as response:
        await page.get_by_role("button", name="Create trip", exact=True).click()
    created = await (await response.value).json()
    await expect(page).to_have_url(BASE + f"/trips/{created['trip']['id']}")
    check("Real trip intake and deep-link routing operate", created["trip"]["customer"] == "Synthetic browser customer")


async def failure_and_access(page):
    prior_status, prior_turn = providers.get_status, providers.agent_turn
    providers.get_status = lambda: {"model_configured": True, "model_name": "mock-provider-for-failure-test", "vision_configured": False, "stt_configured": False}
    def fail(*args):
        raise providers.ProviderError("Injected provider outage for automated test")
    providers.agent_turn = fail
    try:
        await page.goto(BASE + "/trips/2")
        await expect(page.get_by_role("heading", name="TRIP-106", exact=True)).to_be_visible()
        before = await detail(page, 2)
        async with page.expect_response(lambda r: r.url.endswith("/api/trips/2/investigate")) as response:
            await page.get_by_role("button", name="Investigate trip", exact=True).click()
        check("Provider outage is an actual failed request, not fake demo success", (await response.value).status == 502)
        await expect(page.get_by_role("button", name="Retry investigation", exact=True)).to_be_visible()
        after = await detail(page, 2)
        check("Failed model run persists with unchanged money and no proposed effect", after["investigations"][-1]["status"] == "failed" and after["settlement"] == before["settlement"] and not after["actions"])
        providers.get_status = prior_status
        providers.agent_turn = prior_turn
        await page.reload()
        await expect(page.get_by_role("button", name="Retry investigation", exact=True)).to_be_visible()
        await write_click(page, page.get_by_role("button", name="Retry investigation", exact=True), "/api/trips/2/investigate")
        check("User can recover after provider outage without losing evidence", (await detail(page, 2))["investigations"][-1]["mode"] == "demo")
    finally:
        providers.get_status, providers.agent_turn = prior_status, prior_turn

    os.environ["HISABGUARD_ACCESS_TOKEN"] = "isolated-browser-test-token"
    try:
        await page.goto(BASE + "/")
        await expect(page.get_by_label("Access token", exact=True)).to_be_visible()
        await page.get_by_label("Access token", exact=True).fill("isolated-browser-test-token")
        await page.get_by_role("button", name="Connect and retry", exact=True).click()
        await expect(page.get_by_role("link", name="Open trip TRIP-106")).to_be_visible()
        check("Private API rejection recovers through actual token login", True)
    finally:
        os.environ.pop("HISABGUARD_ACCESS_TOKEN", None)


async def browser():
    ARTIFACTS.mkdir(exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="msedge", headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        page = await context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await workflow(page)
        await failure_and_access(page)
        check("Desktop workflow produced no uncaught JavaScript exceptions", not errors)
        await context.close()

        mobile = await browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page = await mobile.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(BASE + "/")
        await expect(page.get_by_role("heading", name="Trip settlements", exact=True)).to_be_visible()
        check("390px queue has no horizontal page overflow", await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
        await page.screenshot(path=str(ARTIFACTS / "queue-mobile.png"))
        await page.get_by_role("button", name="Menu", exact=True).click()
        await page.get_by_role("link", name="Settings", exact=True).click()
        await expect(page.get_by_role("heading", name="Settings", exact=True)).to_be_visible()
        check("Mobile navigation exposes provider settings", True)
        await page.goto(BASE + "/trips/2")
        await expect(page.get_by_role("heading", name="TRIP-106", exact=True)).to_be_visible()
        check("390px trip desk has no horizontal page overflow", await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
        await page.locator(".desk-tabs a[href='#investigation']").click()
        await page.screenshot(path=str(ARTIFACTS / "trip-mobile.png"))
        await page.get_by_role("button", name="Add evidence", exact=True).click()
        await expect(page.locator(".evidence-intake")).to_be_visible()
        await page.locator(".evidence-intake").get_by_label("Evidence title", exact=True).fill("Mobile draft statement")
        await page.locator(".evidence-intake").get_by_label("Evidence kind", exact=False).select_option("statement")
        await page.locator(".evidence-intake").get_by_label("Record text / transcript", exact=False).fill("Synthetic mobile operator note")
        written = await write_click(page, page.locator(".evidence-intake").get_by_role("button", name="Add draft record"), "/api/trips/2/evidence")
        check("Mobile evidence form writes a real draft, not a fake UI effect", written["evidence"][-1]["state"] == "draft")
        await page.reload()
        await expect(page.get_by_role("heading", name="Mobile draft statement", exact=True)).to_be_visible()
        check("Reload preserves new evidence and trip state", True)
        check("All browser paths have zero uncaught JavaScript exceptions", not errors)
        await mobile.close()
        await browser.close()


def main():
    os.environ.pop("HISABGUARD_ACCESS_TOKEN", None)
    providers.get_status = lambda: {"model_configured": False, "model_name": None, "vision_configured": False, "stt_configured": False}
    temp_parent = Path(r"C:\Users\abdul\AppData\Local\Temp\opencode")
    if not temp_parent.is_dir():
        raise RuntimeError("Pre-approved test directory is unavailable")
    with tempfile.TemporaryDirectory(prefix="hisabguard-browser-", dir=temp_parent) as data:
        server = uvicorn.Server(uvicorn.Config(create_app(data), host="127.0.0.1", port=8864, log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.1)
            if not server.started:
                raise RuntimeError("Isolated browser server failed to start")
            asyncio.run(browser())
        finally:
            server.should_exit = True
            thread.join(timeout=10)
    print(f"\n{len(CHECKS)} browser checks passed. Screenshots: artifacts/. Provider accuracy NOT measured; outage test uses a mock.")


if __name__ == "__main__":
    main()
