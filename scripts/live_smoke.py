"""Read-only browser inspection of the running HisabGuard application."""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright, expect

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8834"
ROOT = Path(__file__).resolve().parents[1]


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="msedge", headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        for path, heading in [("/", "Trip settlements"), ("/trips/1", "TRIP-104"),
                              ("/trips/new", "New trip"), ("/settings", "Settings"), ("/activity", "Activity")]:
            response = await page.goto(BASE + path)
            assert response and response.ok, path
            await expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()
            assert await page.locator("#root > *").count() > 0
            print("PASS live " + path + " renders " + heading)
        assert not errors, errors
        await page.goto(BASE + "/trips/1")
        await expect(page.get_by_role("heading", name="TRIP-104", exact=True)).to_be_visible()
        await page.locator(".desk-tabs a[href='#investigation']").click()
        output = ROOT / "artifacts"
        output.mkdir(exist_ok=True)
        await page.screenshot(path=str(output / "live-investigation.png"))
        status = await (await page.request.get(BASE + "/api/status")).json()
        print("Live provider mode: " + status["mode"] + ". Zero uncaught JavaScript exceptions. No records changed.")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
