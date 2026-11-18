"""Source-only checks for usable mail-only B2B fallback regardless of Django availability."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "public" / "index.html"
TRADE = ROOT / "public" / "b2b" / "index.html"
PRIVACY = ROOT / "public" / "b2b" / "privacy" / "index.html"

class StaticB2BFallbackTests(unittest.TestCase):
    def test_pages_exist_nonempty_and_self_contained(self):
        for f in (HOME,TRADE,PRIVACY):
            self.assertTrue(f.is_file())
            self.assertGreater(f.stat().st_size, 500)
    def test_official_email_only_no_dead_form(self):
        t=TRADE.read_text(encoding="utf-8")
        self.assertIn("mailto:zomorodmelal@gmail.com",t)
        self.assertNotIn("<form",t)
        self.assertNotIn("action=",t)
        self.assertNotIn('src="https://',t)
        self.assertNotIn("checkout",t.lower())
    def test_seo_and_mobile(self):
        t=TRADE.read_text(encoding="utf-8")
        self.assertIn('lang="en"',t)
        self.assertIn('width=device-width',t)
        self.assertIn('https://zomorodmelal.ir/b2b/',t)
        self.assertIn('application/ld+json',t)
    def test_company_identity_clear_but_verifiable(self):
        t=TRADE.read_text(encoding="utf-8")
        for s in ("1400879024","3110","Mojtaba Roozegar","independently checked"):
            self.assertIn(s,t)
    def test_home_links_to_static_fallback(self):
        self.assertIn('href="/b2b/"',HOME.read_text(encoding="utf-8"))
    def test_privacy_and_restrict_sensitive_documents(self):
        t=TRADE.read_text(encoding="utf-8")
        self.assertIn('href="/b2b/privacy/"',t)
        self.assertIn("Do not send passports",t)
        self.assertIn("zomorodmelal@gmail.com",PRIVACY.read_text(encoding="utf-8"))
    def test_distinguishes_email_from_crm(self):
        self.assertIn("email-only contact page does not create",TRADE.read_text(encoding="utf-8"))

if __name__ == "__main__": unittest.main()
