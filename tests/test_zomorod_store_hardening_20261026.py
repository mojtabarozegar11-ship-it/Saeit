"""Isolated native Zomorod public storefront security + usability regression checks."""
from pathlib import Path
import shutil
import subprocess
import unittest

INDEX = Path(__file__).resolve().parents[1] / "content/zomorod-v11/store_index.php"

class StoreHardening(unittest.TestCase):
    def test_security_headers_fail_closed(self):
        page = INDEX.read_text(encoding="utf-8")
        for header in ("X-Content-Type-Options: nosniff", "X-Frame-Options: DENY", "Referrer-Policy: strict-origin-when-cross-origin", "Permissions-Policy:", "Content-Security-Policy:"):
            self.assertIn(header, page)
        self.assertIn("form-action 'none'", page)
        self.assertIn("frame-ancestors 'none'", page)

    def test_navigation_seo_and_scope(self):
        page = INDEX.read_text(encoding="utf-8")
        self.assertIn('rel="canonical" href="https://zomorodmelal.ir/store/"', page)
        self.assertIn('href="#main-content"', page)
        self.assertIn('<main id="main-content">', page)
        self.assertIn("a:focus-visible", page)
        self.assertIn("فروشگاه زمرد ملل", page)

    def test_payment_stays_disabled_until_real_psp_is_proven(self):
        page = INDEX.read_text(encoding="utf-8")
        self.assertIn("پرداخت آنلاین تا راه‌اندازی و اعتبارسنجی رسمی درگاه غیرفعال است", page)
        self.assertIn("دریافت وجه از طریق سایت غیرفعال است", page)
        self.assertNotIn("payment_intent", page.lower())
        self.assertNotIn("curl_exec(", page.lower())
        self.assertNotIn("gateway/start", page.lower())
        self.assertIn("free_digital_products WHERE enabled=1", page)

    @unittest.skipUnless(shutil.which("php"), "Requires php CLI")
    def test_php_lint(self):
        p=subprocess.run(["php","-l",str(INDEX)],capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)

if __name__ == "__main__":
    unittest.main()
