"""Reviewed Starter30 static template source is protected from regressions.

These SHA/Git pins are offline, not a claim of current server deployment.
No deployment, live network, invoice, Django DB or TRON transfer.
"""
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "templates/moj-prop-v4/starter-30-trx/index.html"
PIN = ROOT / "scripts/mojprop_starter30_static_release.py"
APPROVED_LIVE_SHA256 = "67db137bdf38c1f23225eab08014a966081dcd2890b373a68a9252af6698f2d4"
APPROVED_LIVE_GIT_BLOB = "737e26d5b410638c9c54d8861fe342c859548698"


class Scan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ctas = []
        self.forms = []
        self.inputs = []
        self.script_srcs = []
        self.canonical = []
        self.h1_count = 0

    def handle_starttag(self, name, attrs):
        a = dict(attrs)
        if name == "a" and a.get("href"):
            self.ctas.append(a["href"])
        if name == "form":
            self.forms.append(a)
        if name == "input":
            self.inputs.append(a)
        if name == "script":
            self.script_srcs.append(a.get("src"))
        if name == "link" and a.get("rel") == "canonical":
            self.canonical.append(a.get("href"))
        if name == "h1":
            self.h1_count += 1


class OfficialStarter30LiveSourceTests(unittest.TestCase):
    def test_exact_protected_live_source_and_release_blob(self):
        data = PAGE.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), APPROVED_LIVE_SHA256)
        actual_blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\x00" + data).hexdigest()
        self.assertEqual(actual_blob, APPROVED_LIVE_GIT_BLOB)
        self.assertIn('"index.html": "' + APPROVED_LIVE_GIT_BLOB + '"', PIN.read_text())

    def test_checkout_and_lossless_status_recovery(self):
        data = PAGE.read_text(encoding="utf8")
        page = Scan()
        page.feed(data)
        self.assertEqual(page.h1_count, 1)
        self.assertEqual(page.canonical, ["https://mojplaywin.com/moj-prop/starter-30-trx/"])
        self.assertEqual(page.ctas.count("/mojprop-starter30-checkout/"), 1)
        self.assertEqual(page.ctas.count("/moj-prop-intake/?format=html&service=blueprint&package=starter-30-trx&utm_source=moj_prop&utm_medium=onsite&utm_campaign=starter30_lead&utm_content=free_terms"), 3)
        status = [x for x in page.forms if x.get("method") == "get"
                  and x.get("action") == "/mojprop-starter30-status/"]
        self.assertEqual(len(status), 1)
        refs = [x for x in page.inputs if x.get("name") == "invoice"]
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].get("pattern"), "MOJPROP30-[A-Z0-9]{20}")
        self.assertIn("required", refs[0])
        self.assertLess(data.index("How the verified 30 TRX checkout works"),
                        data.index("What you receive"))
        self.assertIn("single owner-approved receive-only wallet", data)

    def test_campaign_attribution_and_opt_in_tracker_maintained(self):
        page = Scan()
        page.feed(PAGE.read_text(encoding="utf8"))
        self.assertEqual(page.script_srcs.count(
            "/moj-prop/starter-30-trx/checkout-attribution.js"), 1)
        self.assertEqual(page.script_srcs.count("/mpw-measure/tracker.js"), 1)
        text = PAGE.read_text(encoding="utf8")
        self.assertIn("No real funded account or customer capital", text)
        self.assertIn("30 native TRX", text)
        self.assertIn("1,009.40 (illustrative example)", text)
        self.assertIn('name="twitter:card"', text)
        self.assertEqual(text.count('rel="canonical"'), 1)


if __name__ == "__main__":
    unittest.main()
