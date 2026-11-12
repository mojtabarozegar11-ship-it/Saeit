"""Optional real-browser buyer interaction, separate from customer ZIP tests.

Customer ZIP runs without Playwright or Chromium; CI can skip this browser-only
verification if those optional local QA dependencies are not installed.
"""
from pathlib import Path
import os
import shutil
import unittest

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


ROOT = Path(__file__).resolve().parents[1] / "product_recipes" / "farm_enterprise_economics"


@unittest.skipUnless(
    os.environ.get("FARM_QA_REAL_BROWSER") == "1" and sync_playwright and shutil.which("chromium"),
    "Real-browser runner unavailable or not explicitly enabled"
)
class RealOfflineBrowserBuyerJourney(unittest.TestCase):
    def test_mobile_input_to_liquidity_warning_without_network(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=shutil.which("chromium"), headless=True,
                args=["--no-sandbox"])
            try:
                page = browser.new_page(viewport={"width": 390, "height": 844})
                remote = []
                page.on("request", lambda req: remote.append(req.url) if req.url.startswith("http") else None)
                page.goto((ROOT / "offline_calculator.html").as_uri())
                self.assertEqual(page.locator("#cash-month-inputs tr").count(), 12)
                self.assertTrue(page.locator("#report").is_visible())
                self.assertEqual(remote, [])
                self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2"))

                page.locator("#cash-opening").fill("1000.00")
                first = page.locator("#cash-month-inputs tr").nth(0)
                first.locator('[name="cash_receipts"]').fill("500.00")
                first.locator('[name="operating_payments"]').fill("800.00")
                first.locator('[name="asset_purchases"]').fill("300.00")
                second = page.locator("#cash-month-inputs tr").nth(1)
                second.locator('[name="cash_receipts"]').fill("200.00")
                second.locator('[name="operating_payments"]').fill("700.00")
                second.locator('[name="asset_purchases"]').fill("500.00")
                page.locator("#calculate").click()
                self.assertTrue(page.locator("#report").is_visible())
                self.assertEqual(page.locator("#cash-summary strong").nth(2).inner_text(), "600.00 USD")
                self.assertIn("month 2", page.locator("#cash-summary p").inner_text())
                self.assertEqual(page.locator("#cash-results tr").nth(1).locator("td").nth(2).inner_text(), "-600.00")
                self.assertEqual(remote, [])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
