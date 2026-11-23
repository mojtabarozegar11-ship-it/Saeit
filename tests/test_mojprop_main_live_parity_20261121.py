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
# Current committed source was changed by 2026-11-22 reviewed checkout-copy
# commit bb45e12fe8a5f7477f5f9c539a07d1c45385b3a7. Independent GitHub blob
# comparison confirms this source-only update did not change pricing, links,
# payment endpoints, scripts, historical candidate, or live deployment.
# Preserve exact bytes as a pin: a source wording change is NOT an attestation
# that the corresponding checkout is ready or live.
CURRENT_SOURCE_SHA256="9b1915d0297a2242b86038be0070fb4ed5c914159432fa342c199beaee1cc351"
CURRENT_SOURCE_BLOB="8b5b625c7ef872eb0921c0975fc44c3e6b74b138"
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

    def test_server_invoice_gate_copy_is_explicit_and_simulation_is_separate(self):
        source=PAGE.read_text(encoding="utf8")
        self.assertIn("do not send TRX before a unique server-issued invoice",source)
        self.assertIn("Starter30 checkout is open after email and payer-wallet verification",source)
        self.assertIn("MOJ-PROP-01",source)
        self.assertIn("not payable today",source.lower())
        self.assertNotIn("wait until payment is explicitly reopened",source)

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
