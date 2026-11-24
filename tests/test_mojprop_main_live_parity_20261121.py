"""Protect exact reviewed official English MOJ PROP source bytes.

This offline source hash is not an attestation of live server deployment.
No network, page deployment, database, payment or customer data.
"""
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
PAGE=ROOT/"templates"/"moj-prop-v4"/"index.html"
HISTORICAL_CANDIDATE=ROOT/"docs"/"mojprop"/"historical-static-evidence"/"reviewed-mojprop-home-candidate-20261121.html"
# Immutable live baseline from independently reviewed source.
LIVE_SHA256="029d2493c80480afd0b8d01683254c63a236a4d930c6cc43410def81906848e5"
LIVE_BLOB="fea39dbc409ba8c4c30a807313a20b8d4db19283"
# Separately reviewed source after the historical candidate (never proof of live host).
# Archived independently pinned source version; never treat a source hash as live-deployment evidence.
PREVIOUS_SOURCE_SHA256="24bfa25bef9876e54759ff3538ea470340b21084e50b8c01abb005e0a19f1e86"
PREVIOUS_SOURCE_BLOB="45d7fc5a5d31ecc55dba34e5efc1b9b8b23444c4"
# Source history retained; this PR additionally corrects 3 exact buyer-facing payment-open claims.
# The public cPanel homepage has a DIFFERENT SHA256; these are SOURCE-only pins.
# Earlier reviewed main source, prior to the three no-premature-checkout edits.
PRIOR_SOURCE_SHA256="9b1915d0297a2242b86038be0070fb4ed5c914159432fa342c199beaee1cc351"
PRIOR_SOURCE_BLOB="8b5b625c7ef872eb0921c0975fc44c3e6b74b138"
# Prior same-PR source before four metadata/social conditional-invoice edits.
SOURCE_BEFORE_META_SHA256="bd3eb8ab95d50f79d8803b7975a5c553a8dde16deeeadf8d7f5e67002d1b4860"
SOURCE_BEFORE_META_BLOB="b6aa56cd16ed43fafadf98e885cde4a6e913b841"
# Previous within-PR metadata revision exceeded 200-char SEO limit.
PREVIOUS_META_SOURCE_SHA256="46c6260e62e2a9fe424d7a7dd07752ad7f17342f59b63888fe8f20b7c45da842"
PREVIOUS_META_SOURCE_BLOB="8736318e3f3473987c711e51bf63b7728edaefd4"
CURRENT_SOURCE_SHA256="fe9bfa09ceb9b6df27cf0b7b8799e1ed9f0799c52b5607ada236da28041d11c3"
CURRENT_SOURCE_BLOB="cc035333d70ce0008df7d746bc35c8d290e7b7ef"
# Immutable earlier reviewed candidate (not proof of live deployment).
CANDIDATE_SHA256="4b00b000ecc971073345aa2ca7baaf6753bf83d9bb5243e4ad1276b7012c13e7"
CANDIDATE_BLOB="463ebd2dfb5d803cd20ac17f2c53422d36d65ad9"
COPY_CHANGES=(
    ("Starter 30 — 30 TRX</a>", "Starter30 — Free written terms</a>"),
    (
        "MOJ-PROP-01 (the proposed two-stage live-account route) remains prelaunch",
        "MOJ-PROP-01 (the proposed two-stage simulated evaluation route) remains prelaunch",
    ),
)

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
    def test_exact_reviewed_copy_and_preserved_original_live_source(self):
        current=PAGE.read_bytes()
        self.assertEqual(hashlib.sha256(current).hexdigest(),CURRENT_SOURCE_SHA256)
        self.assertEqual(hashlib.sha1(b"blob "+str(len(current)).encode()+b"\0"+current).hexdigest(),CURRENT_SOURCE_BLOB)
        # The original reviewed source remains an immutable, private-free fixture.
        b=HISTORICAL_CANDIDATE.read_bytes()
        self.assertEqual(hashlib.sha256(b).hexdigest(),CANDIDATE_SHA256)
        self.assertEqual(hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest(),CANDIDATE_BLOB)

        baseline=b
        for before,after in COPY_CHANGES:
            before_bytes=before.encode("utf-8")
            after_bytes=after.encode("utf-8")
            self.assertEqual(baseline.count(after_bytes),1,after)
            self.assertNotIn(before_bytes,baseline)
            baseline=baseline.replace(after_bytes,before_bytes,1)
        # Exact reverse must reproduce the independently pinned historical live
        # source; this catches any change beyond the two reviewed copy edits.
        self.assertEqual(hashlib.sha256(baseline).hexdigest(),LIVE_SHA256)
        self.assertEqual(hashlib.sha1(b"blob "+str(len(baseline)).encode()+b"\0"+baseline).hexdigest(),LIVE_BLOB)

    def test_latest_source_invoice_caution_is_explicit(self):
        page=PAGE.read_text(encoding="utf8")
        self.assertIn("do not send TRX before a unique server-issued invoice.", page)
        self.assertIn("pay only against a unique server-issued 30 TRX invoice.", page)
        self.assertNotIn("wait until payment is explicitly reopened.", page)
        # Never infer from source or GET-only evidence that finance rails are ready.
        self.assertNotIn("A new customer payment has been verified", page)
        self.assertNotIn("checkout is open after email and payer-wallet verification", page)
        self.assertIn("Any new paid enrollment depends on independent seller", page)
        self.assertIn("paid enrollment remains conditional on independent buyer", page)
        self.assertIn("payment and enrollment remain conditional on independent checks", page)
        self.assertNotIn("payment unavailable", page)
        self.assertIn("invoice eligibility is conditional", page)
        self.assertIn("No TRX before a unique invoice.", page)

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
