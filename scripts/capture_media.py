"""Capture final media (desktop + mobile) for the hackathon."""
import asyncio, sys
from pathlib import Path
ROOT = Path(r'E:\hisabguard')
ARTIFACTS = ROOT / 'artifacts'
ARTIFACTS.mkdir(exist_ok=True)
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(channel='msedge', headless=True)
        ctx = await browser.new_context(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1.5)
        page = await ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.goto('http://127.0.0.1:8834/', wait_until='networkidle')
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(ARTIFACTS / 'hisabguard-queue-desktop.png'))
        print('desktop queue captured')
        await page.click('role=link[name="Open trip TRIP-104"]')
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(ARTIFACTS / 'hisabguard-trip104-desktop.png'))
        print('trip 104 captured')
        await page.click('text=Follow-ups')
        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(ARTIFACTS / 'hisabguard-followups-desktop.png'))
        print('followups section captured')
        await page.click('text=Activity')
        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(ARTIFACTS / 'hisabguard-activity-desktop.png'))
        print('activity captured')
        # settings page
        await page.goto('http://127.0.0.1:8834/settings', wait_until='networkidle')
        await page.wait_for_timeout(1200)
        await page.screenshot(path=str(ARTIFACTS / 'hisabguard-settings-desktop.png'))
        print('settings captured')
        await ctx.close()

        mob = await browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        page = await mob.new_page()
        await page.goto('http://127.0.0.1:8834/', wait_until='networkidle')
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(ARTIFACTS / 'hisabguard-queue-mobile.png'))
        print('mobile queue captured')
        await page.click('role=link[name="Open trip TRIP-104"]')
        await page.wait_for_timeout(1200)
        await page.screenshot(path=str(ARTIFACTS / 'hisabguard-trip104-mobile.png'))
        print('mobile trip captured')
        await mob.close()
        await browser.close()
        print('page errors:', errors)

asyncio.run(main())
