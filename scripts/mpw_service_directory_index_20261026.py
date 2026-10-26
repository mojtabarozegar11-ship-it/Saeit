#!/usr/bin/env python3
"""Scoped directory-index repair for the 13 existing MojPlayWin service pages.

Adds only /mpw-editorial/revenue/.htaccess with DirectoryIndex index.html.
Does not move, rename, rewrite, replace or delete any site content.
"""
from pathlib import Path
import hashlib
import os
import re
import sys

ROOT=Path("/home/zomorod2/mojplaywin.com")
REV=ROOT/"mpw-editorial/revenue"
CONFIG=REV/".htaccess"
SLUGS=("website-doctor","landing-page-studio","ai-automation",
       "business-spreadsheets","website-templates","social-media-kits",
       "resume-builder","logo-studio","browser-games","marketing-ai",
       "business-calculators","website-care")

def payload(run):
    if not re.fullmatch(r"[0-9]{8,20}",run):
        raise RuntimeError("Invalid run ID")
    return ("# MAIN MojPlayWin service directory-index only; run "+run+"\n"
            "DirectoryIndex index.html\n").encode("ascii")

def verify():
    if ROOT.is_symlink() or ROOT.resolve()!=ROOT or ROOT.name!="mojplaywin.com":
        raise RuntimeError("Wrong document root")
    if not REV.is_dir() or REV.is_symlink():
        raise RuntimeError("Revenue directory unavailable or unsafe")
    root_ht=ROOT/".htaccess"
    if not root_ht.is_file() or root_ht.is_symlink():
        raise RuntimeError("No main-site routing")
    routing=root_ht.read_text("utf-8","replace")
    if "production-home-20261017.html" not in routing:
        raise RuntimeError("Main-site root changed")
    for slug in ("",*SLUGS):
        folder=REV/slug if slug else REV
        page=folder/"index.html"
        if (not folder.is_dir() or folder.is_symlink()
             or not page.is_file() or page.is_symlink()):
            raise RuntimeError("Unexpected standalone service "+str(page))
        doc=page.read_text("utf-8","replace")
        if ('<link rel="canonical"' not in doc or
             'mpw-one-shell-20261026.css' not in doc):
            raise RuntimeError("Service HTML differs from approved shell "+str(page))

def publish(run):
    expected=payload(run)
    verify()
    if CONFIG.exists() or CONFIG.is_symlink():
        raise RuntimeError("An existing local .htaccess must never be overwritten")
    try:
        with CONFIG.open("xb") as f:
            os.fchmod(f.fileno(),0o644)
            f.write(expected)
            f.flush()
            os.fsync(f.fileno())
        if CONFIG.is_symlink() or hashlib.sha256(CONFIG.read_bytes()).digest()!=hashlib.sha256(expected).digest():
            raise RuntimeError("Index configuration changed during installation")
    except BaseException:
        if CONFIG.is_file() and not CONFIG.is_symlink() and CONFIG.read_bytes()==expected:
            CONFIG.unlink()
        raise
    print("MPW_REVENUE_13_SCOPED_DIRECTORY_INDEX_PUBLISHED")

def rollback(run):
    expected=payload(run)
    if not CONFIG.is_file() or CONFIG.is_symlink() or CONFIG.read_bytes()!=expected:
        raise RuntimeError("Index configuration no longer matches this release")
    CONFIG.unlink()
    print("MPW_REVENUE_INDEX_ROLLBACK_OK")

def selftest():
    assert len(SLUGS)==12 and len(set(SLUGS))==12
    doc=payload("123456789")
    assert doc.count(b"DirectoryIndex index.html")==1
    assert b"Rewrite" not in doc and b"Options" not in doc
    print("MPW_SCOPED_DIRECTORY_INDEX_SELFTEST_OK")

if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":selftest()
    elif len(sys.argv)==3 and sys.argv[1]=="publish":publish(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:raise SystemExit("Usage: selftest | publish RUN | rollback RUN")
