"""MojPlayWin main-only adaptation of the 11 Zomorod V11 site-audit agents.

Original Zomorod PHP runtime is kept byte-for-byte in heritage/ for provenance,
but never imported or run. This module has no Django, factory or child site use.
Run only in the private stage, outside all public document roots.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import ssl
import sys
import time
from datetime import datetime, timezone
from urllib import error, request

BASE="https://mojplaywin.com"
AGENT_PATHS={
    "master":("/", "هماهنگی پایش سلامت سایت اصلی"),
    "content":("/knowledge/", "پایش صفحات دانش و محتوای سایت"),
    "seo":("/search/", "پایش دسترس‌پذیری جست‌وجو"),
    "commerce":("/store/", "پایش صفحه فروشگاه، نه انجام تراکنش"),
    "agriculture":("/agriculture/", "پایش حوزه کشاورزی سایت اصلی"),
    "research":("/research/", "پایش پژوهش و محتوای مستند"),
    "economic":("/economy/", "پایش صفحات اقتصاد"),
    "weather":("/weather/", "پایش مسیر عمومی آب‌وهوا؛ بدون تولید پیش‌بینی"),
    "quality":("/company/", "بررسی سلامت صفحه معرفی و شرکت"),
    "media":("/newsletter/", "پایش رسانه و خبرنامه"),
    "security":("/staff/command-center/", "پایش فقط کد پاسخ صفحه ورود مدیریت، بدون ورود"),
}
ALLOWED_PUBLIC={200}
ALLOWED_LOGIN={200,301,302,303,307,308,401,403}
TIMEOUT_SECONDS=7
STAGE=Path("/home/zomorod2/.private_mojplaywin_main_agents/site_health_v11_port_20261018")
AGENTS=set(AGENT_PATHS)

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def response_code(path, opener=None):
    """Never follow redirects. Only hardcoded main-site HTTPS paths permitted."""
    if path not in {x[0] for x in AGENT_PATHS.values()}:
        raise ValueError("unapproved_main_site_path")
    client=opener or request.build_opener(NoRedirect(), request.HTTPSHandler(context=ssl.create_default_context()))
    req=request.Request(BASE+path,headers={"User-Agent":"MojPlayWin-MainSiteAudit/1.0"},
                        method="HEAD")
    try:
        with client.open(req,timeout=TIMEOUT_SECONDS) as result:
            return int(result.status)
    except error.HTTPError as exc:
        # A private login redirect is expected and must never be followed.
        return int(exc.code)

def check_path(agent_code,probe=response_code):
    if agent_code not in AGENTS:
        raise ValueError("unknown_agent")
    path=AGENT_PATHS[agent_code][0]
    started=time.monotonic()
    try:
        status=probe(path)
        allowed=ALLOWED_LOGIN if agent_code=="security" else ALLOWED_PUBLIC
        quality="ok" if status in allowed else "warning"
        return {"code":agent_code,"path":path,"status":quality,"http":status,
                "duration_ms":int((time.monotonic()-started)*1000)}
    except (error.URLError,OSError,TimeoutError,ValueError) as exc:
        return {"code":agent_code,"path":path,"status":"error","http":0,
                "duration_ms":int((time.monotonic()-started)*1000),
                "reason":type(exc).__name__}

def atomic_json(path,obj):
    import tempfile
    data=json.dumps(obj,ensure_ascii=False,sort_keys=True).encode("utf-8")
    fd,temp=tempfile.mkstemp(prefix=".tmp-mpw-v11-",dir=str(path.parent))
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def audit_once(state=STAGE,probe=response_code):
    if state.is_symlink() or not state.is_dir() or (state.stat().st_mode & 0o077):
        raise PermissionError("private_agent_directory_required")
    results=[check_path(name,probe) for name in sorted(AGENTS)]
    now=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record={"tenant":"mojplaywin-main","origin":"Zomorod V11 site-auditor adapted",
            "observed_utc":now,"total_agents":len(results),"runs":results,
            "automatic_publishing":False,"factory_connected":False,
            "writes_to_public_site":False}
    atomic_json(state/"last_scan.json",record)
    log=state/"history.jsonl"
    if log.is_symlink():raise PermissionError("unsafe_history")
    # Bound daily telemetry storage: 11 small results; never store page content.
    if log.exists() and log.stat().st_size>150000:
        log.rename(state/"history.previous.jsonl")
    fd=os.open(str(log),os.O_CREAT|os.O_WRONLY|os.O_APPEND|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"a",encoding="utf-8") as out:
        out.write(json.dumps(record,ensure_ascii=False,sort_keys=True)+"\n")
    return record

def main(argv=None):
    parser=argparse.ArgumentParser(description="11 MojPlayWin main-only site health roles")
    commands=parser.add_mutually_exclusive_group(required=True)
    commands.add_argument("--check",action="store_true")
    commands.add_argument("--once",action="store_true")
    opts=parser.parse_args(argv)
    os.umask(0o077)
    if opts.check:
        print(json.dumps({"site":"mojplaywin-main","role_count":len(AGENTS),
                          "roles":list(sorted(AGENTS)),
                          "source":"Zomorod V11 adapted",
                          "original_source_never_executed":True,
                          "factory_connected":False,"site_modified":False},ensure_ascii=False))
    else:
        result=audit_once()
        print(json.dumps({"site":"mojplaywin-main","roles":result["total_agents"],
                          "ok":sum(x["status"]=="ok" for x in result["runs"]),
                          "warning":sum(x["status"]=="warning" for x in result["runs"]),
                          "error":sum(x["status"]=="error" for x in result["runs"]),
                          "site_modified":False,"factory_connected":False,
                          "codes":{x["code"]:x["status"] for x in result["runs"]}},ensure_ascii=False))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
