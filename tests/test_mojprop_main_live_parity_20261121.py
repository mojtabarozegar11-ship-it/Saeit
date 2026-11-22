"""Pin the updated English MOJ PROP marketing source, not live deployment."""
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
PAGE=ROOT/"templates"/"moj-prop-v4"/"index.html"
PRODUCT=ROOT/"templates"/"moj-prop-v4"/"starter-30-trx"/"index.html"
MAIN_SHA256="d45923374c148f7a0e4df5406bea77f38963e8ee18dc5fb49f3a88b2256fcfac"
MAIN_GIT_BLOB="b31de0e17e626f712f586d269674edd133652a21"
PRODUCT_SHA256="dfdc657b17b52da5fc1fe4be46aa1231794ac5286c717f6ae394f1e8fca5742b"
PRODUCT_GIT_BLOB="b2e2633be69c7731f78b20a3457455ccd4feba1a"
LEVELS=("$1,000","$1,500","$2,000","$3,000","$5,000","$7,500",
        "$10,000","$15,000","$20,000","$35,000","$50,000",
        "$70,000","$85,000","$100,000")

def blob_hash(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

class Scan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta={}
        self.scripts=[]
        self.links=[]
        self.canonicals=[]
        self.headings=0
        self.ids=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=="meta":
            key=d.get("name") or d.get("property")
            self.meta.setdefault(key,[]).append(d.get("content"))
        elif tag=="script":
            self.scripts.append(d.get("src"))
        elif tag=="link" and d.get("rel")=="canonical":
            self.canonicals.append(d.get("href"))
        elif tag=="a":
            self.links.append(d.get("href"))
        elif tag=="h1":
            self.headings+=1
        if "id" in d:
            self.ids.append(d["id"])

class OfficialMojPropLiveParityTests(unittest.TestCase):
    def test_both_pinned_reviewed_source_blobs(self):
        for path,sha,blob in (
            (PAGE,MAIN_SHA256,MAIN_GIT_BLOB),
            (PRODUCT,PRODUCT_SHA256,PRODUCT_GIT_BLOB),
        ):
            with self.subTest(path=path):
                b=path.read_bytes()
                self.assertEqual(hashlib.sha256(b).hexdigest(),sha)
                self.assertEqual(blob_hash(b),blob)

    def test_free_plan_removed_and_paid_entry_disclosed(self):
        html=PAGE.read_text(encoding="utf-8")
        self.assertNotIn("Plan 1",html)
        self.assertNotIn("MOJ-PROP-01",html)
        self.assertNotIn("Contact MOJ PROP about Plan 1 (free)",html)
        self.assertIn("30 TRX INITIAL ENTRY",html)
        self.assertIn("$100,000 virtual",html)
        self.assertIn("14 SIMULATED LEVELS",html)
        self.assertIn("Payment and new enrollment are currently unavailable",html)
        self.assertIn('href="/moj-prop/starter-30-trx/"',html)

    def test_fourteen_conditional_levels_and_no_false_capital(self):
        html=PRODUCT.read_text(encoding="utf-8")
        self.assertEqual(html.count("<li><strong>Level "),14)
        for i,amount in enumerate(LEVELS,1):
            self.assertIn(f"<li><strong>Level {i}</strong> — {amount}</li>",html)
        self.assertIn("These dollar amounts represent virtual trading capacity",html)
        self.assertIn("a pass at one stage does not automatically grant the next",html)
        self.assertIn("Payment is currently unavailable",html)
        self.assertNotIn('href="/mojprop-starter30-checkout/"',html)

    def test_analytics_canonical_and_layout_preserved(self):
        page=Scan();page.feed(PAGE.read_text(encoding="utf-8"))
        product=Scan();product.feed(PRODUCT.read_text(encoding="utf-8"))
        self.assertEqual(page.scripts.count("/mpw-measure/tracker.js"),1)
        self.assertEqual(page.canonicals,["https://mojplaywin.com/moj-prop/"])
        self.assertEqual(len(page.meta.get("og:image",[])),1)
        self.assertEqual(page.meta.get("twitter:card"),["summary_large_image"])
        self.assertEqual(page.headings,1)
        self.assertEqual(product.headings,1)
        self.assertEqual(len(page.ids),len(set(page.ids)))
        self.assertEqual(len(product.ids),len(set(product.ids)))
        self.assertIn("/moj-prop/languages/",page.links)

if __name__=="__main__":
    unittest.main()
