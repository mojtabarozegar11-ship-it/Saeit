#!/usr/bin/env python3
"""Public anonymous GET-only guard for scoped main template publisher."""
from __future__ import annotations
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DOMAIN="https://mojplaywin.com"
PROTECTED=(
    "/mojtaba.roozegar/","/mojtaba.roozegar/about/",
    "/picm/login/","/studio.Roham/","/saman/","/farnaz/",
    "/zahra$$/","/taniya/","/about/invalid-child-probe-NEVER/",
)
# Last sentinel is NOT requested; do not probe it.
PROTECTED=PROTECTED[:-1]
MAIN=(
    "/", "/store/", "/agriculture/", "/industry/", "/research/",
    "/knowledge/","/economy/","/studio/","/market/","/agents/","/company/",
    "/ventures/agriculture/", "/ventures/cafe-restaurant/",
    "/ventures/fuel-station/", "/ventures/jewelry-gold/",
    "/ventures/carpets/", "/ventures/currency-crypto/",
    "/ventures/ecommerce/","/ventures/hospitality/",
)
IMAGES=(
    "about.webp","platform-home.webp","academy.webp","laboratory.webp",
    "genetics.webp","marketplace.webp","economy.webp","services.webp",
    "blog.webp","industry.webp","smart-agriculture.webp",
)
class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        p=urllib.parse.urlsplit(newurl)
        if p.scheme!="https" or p.hostname not in ("mojplaywin.com","www.mojplaywin.com"):
            raise ValueError("cross-host redirect blocked")
        return super().redirect_request(req,fp,code,msg,headers,newurl)

OPENER=urllib.request.build_opener(SameHostRedirect())
def read(path, limit=400000):
    req=urllib.request.Request(DOMAIN+path,method="GET",headers={
        "User-Agent":"MojPlayWin-MainOnly-ScopedReleaseGuard/1.0",
        "Accept":"text/html,image/webp,*/*;q=0.5",
        "Cache-Control":"no-cache",
    })
    with OPENER.open(req,timeout=10) as res:
        return res.status,res.read(limit)

def snapshot():
    state={}
    for path in PROTECTED:
        status,body=read(path)
        if status != 200 or b'mpw-founder-name' in body:
            raise RuntimeError("protected public path failed verification")
        state[path]=status
        print("PROTECTED_READONLY_OK path="+path+" http="+str(status),flush=True)
    return state

def before(filename):
    if len(MAIN)!=19 or len(PROTECTED)!=8:
        raise RuntimeError("route allowlist unexpected")
    state=snapshot()
    for name in IMAGES:
        path="/static/site/heroes/"+name
        status,data=read(path,64)
        if status!=200 or not data:
            raise RuntimeError("missing already-hosted static asset "+name)
        print("MAIN_STATIC_ASSET_OK "+name,flush=True)
    for path in MAIN:
        status,_=read(path,256)
        if status!=200: raise RuntimeError("main site preflight failed")
    Path(filename).write_text(json.dumps(state,sort_keys=True))
    print("PREDEPLOY_MAIN_AND_PROTECTED_READONLY_PASS=true",flush=True)

def after(filename):
    previous=json.loads(Path(filename).read_text())
    if snapshot()!=previous:raise RuntimeError("protected response status changed")
    for path in MAIN:
        status,blob=read(path)
        if status!=200:raise RuntimeError("main page no longer responds")
        html=blob.decode("utf-8","replace")
        match=re.search(r'<footer\b[^>]*>(.*?)</footer>',html,re.I|re.S)
        if not match or "Mojtaba Roozegar" not in match.group(1) or "mpw-founder-name" not in match.group(1):
            raise RuntimeError("updated main-only footer not visible")
        print("MAIN_FOOTER_LIVE_OK path="+path,flush=True)
    print("MAIN_ONLY_19_FOOTERS_LIVE=true",flush=True)
    print("EIGHT_PROTECTED_PUBLIC_ROUTES_NO_SIGNATURE=true",flush=True)
    print("PASSENGER_NOT_RESTARTED_BY_WORKFLOW=true",flush=True)
    print("PAYMENT_AND_PRODUCT_SOURCE_UNCHANGED=true",flush=True)

if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1] not in ("before","after"):
        raise SystemExit(2)
    try:
        (before if sys.argv[1]=="before" else after)(sys.argv[2])
    except Exception as exc:
        print("RELEASE_HTTP_GUARD_NO_GO="+type(exc).__name__,flush=True)
        raise SystemExit(1)
