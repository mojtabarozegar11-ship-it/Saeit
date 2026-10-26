"""Verified public account directory; only intentionally published profile URLs.

No private destination IDs, env variable names, credentials, approval receipts,
drafts or social-media tokens can escape via this module.
"""
from __future__ import annotations
from .catalog import BRANDS, PLATFORMS, RESTRICTED_HANDLES
from .onboarding import _valid_url
from .adapters import Blocked

LABELS = {
    "personal": "Personal research & professional",
    "zomorod": "Zomorod Melal Agro-Industry",
    "mojplaywin": "MojPlayWin games & education",
}
MAX_PER_BRAND = 45

def official_links(store):
    """Return safe public display fields only, never any private account metadata."""
    result={b:[] for b in BRANDS}
    seen=set()
    for row in store.accounts():
        brand,key,url=row["brand"],row["platform"],row["public_url"]
        if (brand not in result or key not in PLATFORMS or row["verified"]!=1
            or not url or len(result[brand])>=MAX_PER_BRAND):
            continue
        if any(term in (url+" "+row["destination"]).casefold()
               for term in RESTRICTED_HANDLES):
            continue
        try:
            url=_valid_url(url,key,row["instance"])
        except (Blocked,ValueError):
            continue
        if url in seen:
            continue
        seen.add(url)
        result[brand].append({
            "platform":PLATFORMS[key].label,
            "network":key,
            "url":url,
        })
    for brand in BRANDS:
        result[brand].sort(key=lambda x:(x["platform"].casefold(),x["url"]))
    return {"brands":[{"key":b,"title":LABELS[b],"links":result[b]}
                      for b in BRANDS],
            "total":sum(len(v) for v in result.values())}
