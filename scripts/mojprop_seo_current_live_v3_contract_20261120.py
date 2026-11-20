"""Exact live-baseline v3 bundle validation. Pure bytes in, bytes out.

No filesystem/network, no deployment entrypoint, no authorization override.
All existing independent production attestations remain mandatory.
"""
from scripts.mojprop_seo_exact_live_candidate_20261120 import PAGES, sha
from scripts.mojprop_seo_reconcile_commercial_copy_20261120 import reconcile_candidate
import re

PINS = {
    "index.html": ("d6b5b1c0c8e1f34d627e01f1b01f6195a32de63a4d9f0eee0991ade85e5953e1", "10d064c0ffbcc9e25adfdcef9c72b43d45ae448b3f8bb47bf96710a56ce0db21"),
    "catalog/index.html": ("b0515a1a2f846e79ed330b9c6ef39b5d75ae1f5e487bf3807c051a9bbac7c21e", "dc516f86e8b1ea6fd46410dce0faac33464e1f86e1d7a1332e75f198c46c38ae"),
    "rules/index.html": ("f75f0174e6446bcb051e1f5a89ca90cb4f66fb9ab55f79ff18ad007ff1cbe760", "f75f0174e6446bcb051e1f5a89ca90cb4f66fb9ab55f79ff18ad007ff1cbe760"),
    "payment/index.html": ("6eecca5d03d391b0e882e813a1fdd52f3ffac46e27f75f5bc1b4f4a0f5acb381", "ec34a132648af2653cadbc4727c16f4e058cba350be65b497d3a329a8a03cf59"),
    "contact/index.html": ("0404200e7b680d2925156e24a7b715c77e54f4cac5110868a40815969d877d8b", "0404200e7b680d2925156e24a7b715c77e54f4cac5110868a40815969d877d8b"),
}
CHANGED = ("index.html", "catalog/index.html", "payment/index.html")
REQUIRED_ATTESTATIONS = (
    "MOJPROP_FULL_DB_APP_MEDIA_RESTORE_VERIFIED",
    "MOJPROP_PASSENGER_TENANT_ISOLATION_VERIFIED",
    "MOJPROP_STATIC_ROLLBACK_VERIFIED",
    "MOJPROP_STATIC_APPROVED_MAIN_SHA",
)

def _parts(blob):
    if type(blob) is not bytes or len(blob) > 512000 or blob.count(b"</head>") != 1:
        raise ValueError("invalid HTML boundary")
    return blob.split(b"</head>", 1)

def build_v3(historical, current):
    if set(historical) != set(PINS) or set(current) != set(PINS):
        raise ValueError("exact five-page scope required")
    output = {}
    receipts = []
    for path,(before,after) in PINS.items():
        old = historical[path]
        live = current[path]
        oh, ob = _parts(old)
        lh, lb = _parts(live)
        if sha(old) != PAGES[path][0] or sha(live) != before or ob != lb:
            raise ValueError("current or historical baseline mismatch")
        v2,_ = reconcile_candidate(path,old)
        _, nb = _parts(v2)
        result = v2 if path == "catalog/index.html" else lh+b"</head>"+nb
        _, rb = _parts(result)
        for tag in (b"script", b"form", b"style"):
            pattern = rb"<"+tag+rb"\b[^>]*>.*?</"+tag+rb">"
            if re.findall(pattern,lb,re.I|re.S) != re.findall(pattern,rb,re.I|re.S):
                raise ValueError("protected functional markup mismatch")
        if sha(result) != after or (result != live) != (path in CHANGED):
            raise ValueError("candidate differs from exact reviewed release")
        output[path] = result
        receipts.append({"path":path,"before_sha256":before,"after_sha256":after,"changed":path in CHANGED})
    return output, {"files":receipts,"write_scope":list(CHANGED),
                    "required_external_attestations":list(REQUIRED_ATTESTATIONS),
                    "deployment_authorized":False}
