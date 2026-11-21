"""Preserve approved live official English MOJ PROP source parity.

Offline only: no network, page deployment, database, payment or customer data.
"""
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import unittest

PAGE=Path(__file__).resolve().parents[1]/"templates"/"moj-prop-v4"/"index.html"
SHA256="b1b9eaf8a0f49ffce4254d35a5a4ae0e3ed2b73ad1ccc0eaea1b499fcf1b7b71"
BLOB="169f4464107da0145fe47cbe5725a6aebbdca79a"

class Scan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta={}
        self.script=[]
        self.links=[]
        self.canonical=[]
        self.h1=0
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=="meta":
            key=d.get("name") or d.get("property")
            self.meta.setdefault(key,[]).append(d.get("content"))
        elif tag=="script":
            self.script.append(d.get("src"))
        elif tag=="link" and d.get("rel")=="canonical":
            self.canonical.append(d.get("href"))
        elif tag=="a":
            self.links.append(d.get("href"))
        elif tag=="h1":
            self.h1+=1

class OfficialMojPropLiveParityTests(unittest.TestCase):
    def test_exact_source_matches_verified_public_release(self):
        b=PAGE.read_bytes()
        self.assertEqual(hashlib.sha256(b).hexdigest(),SHA256)
        self.assertEqual(hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest(),BLOB)
    def test_official_info_and_order_policy_not_misrepresented(self):
        s=PAGE.read_text(encoding="utf8")
        self.assertTrue(s.startswith("<!-- MOJ_PROP_CATALOG_RELEASE_V4 -->"))
        self.assertIn("not payable today",s.lower())
        self.assertIn("PRELAUNCH",s)
        self.assertIn('href="/moj-prop/starter-30-trx/"',s)
        self.assertIn('href="/moj-prop/languages/"',s)
    def test_opt_in_analytics_and_social_preview_preserved(self):
        v=Scan();v.feed(PAGE.read_text(encoding="utf8"))
        self.assertEqual(v.script.count("/mpw-measure/tracker.js"),1)
        self.assertEqual(v.canonical,["https://mojplaywin.com/moj-prop/"])
        self.assertEqual(len(v.meta.get("og:image",[])),1)
        self.assertEqual(len(v.meta.get("twitter:image",[])),1)
        self.assertEqual(v.meta.get("twitter:card"),["summary_large_image"])
        self.assertIn("/moj-prop/languages/",v.links)
        self.assertIn("/moj-prop/starter-30-trx/",v.links)

if __name__=="__main__":
    unittest.main()
