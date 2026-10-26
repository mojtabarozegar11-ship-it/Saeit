#!/usr/bin/env python3
"""One MojPlayWin navigation source for PHP search and topic readers.

Only two verified main-site PHP files change. Their search/topic logic, JSON
records, URLs, canonical tags, metadata and response semantics stay intact.
The published HTML header is sourced from the current production homepage.
No other site, shared routing, checkout, child or personal resource is touched.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path("/home/zomorod2/mojplaywin.com")
WORK = ROOT / "design-preview-20261017/mpw-site-integrity-20261019"
HOME = ROOT / "design-preview-20261017/production-home-20261017.html"
CSS = ROOT / "mpw-editorial/revenue/assets/mpw-one-shell-20261026.css"
NAV = WORK / "mpw-main-header-20261026.html"
FILES = (WORK / "search.php", WORK / "topic.php")
MARK = 'data-mpw-dynamic-shell="20261026"'
HRE = re.compile(r'<header\b[^>]*class="mw-site-nav"[^>]*>[\s\S]*?</header>', re.I)
OLD = re.compile(r"function top_nav\(\)\{echo '([^'\r\n]*)';\}")
FOOT = re.compile(r"function footer_html\(\)\{echo '([^'\r\n]*)';\}")
NEW_TOP = """function top_nav(){
 echo '<link rel="stylesheet" href="/mpw-editorial/revenue/assets/mpw-one-shell-20261026.css"></head><body>';
 $nav_file=__DIR__.'/mpw-main-header-20261026.html';
 if(!is_file($nav_file)){http_response_code(503);exit('Navigation temporarily unavailable');}
 readfile($nav_file);
 echo '<div class="shell">';
}"""
NEW_FOOT = """function footer_html(){
 echo '<footer class="footer" aria-label="MojPlayWin navigation"><a href="/">Home</a> · <a href="/services/">Services</a> · <a href="/knowledge/">Knowledge</a> · <a href="/contact/">Contact</a> · Mojtaba Roozegar</footer></div></body></html>';
}"""

def fail(message: str) -> None:
    raise RuntimeError(message)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def nav_from_home(home: str) -> bytes:
    items = list(HRE.finditer(home))
    if len(items) != 1:
        fail("Production header must be unique")
    header = items[0].group(0)
    for required in ('aria-label="Primary MojPlayWin navigation"',
                     'href="/services/"', 'data-mpw-earning-directory="v1"'):
        if required not in header:
            fail("Main navigation fingerprint changed: " + required)
    header = header.replace('<header class="mw-site-nav"',
        '<header class="mw-site-nav mpw-unified-shell" ' + MARK, 1)
    if header.count(MARK) != 1:
        fail("Unable to mark official header")
    return header.encode("utf-8")

def transform(raw: bytes) -> bytes:
    doc = raw.decode("utf-8")
    if MARK in doc or "mpw-main-header-20261026.html" in doc:
        fail("Previously modified or mixed dynamic nav detected")
    a = list(OLD.finditer(doc))
    b = list(FOOT.finditer(doc))
    if len(a) != 1 or len(b) != 1:
        fail("Unexpected PHP navigation definitions")
    if ('<nav class="nav" aria-label="MojPlayWin navigation">' not in a[0].group(1)
        or '<strong>MojPlayWin</strong>' not in a[0].group(1)
        or '</head><body><div class="shell">' not in a[0].group(1)
        or '<footer class="footer">Mojtaba Roozegar</footer>' not in b[0].group(1)):
        fail("Original PHP shell differs from audited version")
    original_core = [doc.count(s) for s in ("function head_html(", "function safe(",
                                                  "top_nav();", "footer_html();")]
    if original_core != [1, 1, 1, 1]:
        fail("Unexpected content logic structure")
    out = doc[:b[0].start()] + NEW_FOOT + doc[b[0].end():]
    m = OLD.search(out)
    if m is None:
        fail("Missing PHP navigation after footer edit")
    out = out[:m.start()] + NEW_TOP + out[m.end():]
    if any(out.count(s) != original_core[i] for i, s in
           enumerate(("function head_html(", "function safe(",
                      "top_nav();", "footer_html();"))):
        fail("Content route logic changed")
    if out.count("mpw-main-header-20261026.html") != 1:
        fail("Bad new shared-navigation file reference")
    return out.encode("utf-8")

def verify() -> None:
    if ROOT.is_symlink() or ROOT.resolve() != ROOT or ROOT.name != "mojplaywin.com":
        fail("Unexpected document root")
    ht = ROOT / ".htaccess"
    if not ht.is_file() or ht.is_symlink():
        fail("Main production routing unavailable")
    routing = ht.read_text("utf-8", "replace")
    for expected in ("production-home-20261017.html",
                     "mpw-site-integrity-20261019/search.php",
                     "mpw-site-integrity-20261019/topic.php"):
        if expected not in routing:
            fail("Scoped main-site routing missing " + expected)
    for p in (WORK, HOME.parent, CSS.parent):
        if not p.is_dir() or p.is_symlink():
            fail("Missing or unsafe main-site directory " + str(p))
    for p in (HOME, CSS, *FILES):
        if not p.is_file() or p.is_symlink():
            fail("Missing or unsafe main-site file " + str(p))
    if ".mpw-unified-shell" not in CSS.read_text("utf-8", "replace"):
        fail("Required already-deployed CSS has drifted")
    if NAV.exists() or NAV.is_symlink():
        fail("Shared header already exists; refusing overwrite")

def run_backup(run: str) -> Path:
    if not re.fullmatch(r"[0-9]{8,20}", run):
        fail("Bad run ID")
    return ROOT.parent / (".mpw-dynamic-shell-" + run)

def atomic(path: Path, blob: bytes, mode: int) -> None:
    fd, temp = tempfile.mkstemp(prefix=".mpw-dyn-nav-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def publish(run: str) -> None:
    verify()
    originals = {p.name: p.read_bytes() for p in FILES}
    revisions = {name: transform(data) for name, data in originals.items()}
    header = nav_from_home(HOME.read_text("utf-8"))
    backup = run_backup(run)
    if backup.exists() or backup.is_symlink():
        fail("Backup already exists")
    backup.mkdir(mode=0o700)
    manifest = {"run": run, "nav_after": sha(header), "files": {}}
    for p in FILES:
        original = originals[p.name]
        saved = backup / (p.name + ".original")
        with saved.open("xb") as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(original)
        manifest["files"][p.name] = {"before": sha(original),
             "after": sha(revisions[p.name]),
             "mode": stat.S_IMODE(p.stat().st_mode)}
    with (backup / "manifest.json").open("x", encoding="utf-8") as f:
        os.fchmod(f.fileno(), 0o600)
        json.dump(manifest, f, sort_keys=True)
    changed = []
    try:
        for p in FILES:
            item = manifest["files"][p.name]
            if p.is_symlink() or sha(p.read_bytes()) != item["before"]:
                fail("Concurrent main-site edit " + p.name)
            atomic(p, revisions[p.name], item["mode"])
            changed.append(p)
            if sha(p.read_bytes()) != item["after"]:
                fail("PHP file hash mismatch " + p.name)
        if NAV.exists() or NAV.is_symlink():
            fail("Navigation target was concurrently created")
        with NAV.open("xb") as f:
            os.fchmod(f.fileno(), 0o644)
            f.write(header)
        if sha(NAV.read_bytes()) != manifest["nav_after"]:
            fail("Navigation file hash mismatch")
    except BaseException:
        if NAV.is_file() and not NAV.is_symlink() and sha(NAV.read_bytes()) == manifest["nav_after"]:
            NAV.unlink()
        for p in reversed(changed):
            item = manifest["files"][p.name]
            if p.is_file() and not p.is_symlink() and sha(p.read_bytes()) == item["after"]:
                atomic(p, originals[p.name], item["mode"])
        raise
    print("MPW_SEARCH_AND_340_TOPICS_ONE_NAVIGATION_SHELL=PASS")

def rollback(run: str) -> None:
    backup = run_backup(run)
    meta = backup / "manifest.json"
    if not backup.is_dir() or backup.is_symlink() or not meta.is_file():
        fail("No verified backup")
    manifest = json.loads(meta.read_text("utf-8"))
    if manifest.get("run") != run or set(manifest.get("files", {})) != {p.name for p in FILES}:
        fail("Wrong backup inventory")
    if not NAV.is_file() or NAV.is_symlink() or sha(NAV.read_bytes()) != manifest["nav_after"]:
        fail("Shared navigation concurrently edited")
    previous = {}
    for p in FILES:
        item = manifest["files"][p.name]
        saved = backup / (p.name + ".original")
        if (not p.is_file() or p.is_symlink() or
            sha(p.read_bytes()) != item["after"] or not saved.is_file() or saved.is_symlink()):
            fail("PHP file changed after publication")
        old = saved.read_bytes()
        if sha(old) != item["before"]:
            fail("Saved PHP backup checksum differs")
        previous[p.name] = old
    for p in FILES:
        atomic(p, previous[p.name], manifest["files"][p.name]["mode"])
    NAV.unlink()
    print("MPW_DYNAMIC_SHELL_ROLLBACK=PASS")

def selftest() -> None:
    old = ("""<?php
function safe($s){return $s;}
function head_html($a,$b,$c){echo $a;}
function top_nav(){echo '</head><body><div class="shell"><nav class="nav" aria-label="MojPlayWin navigation"><strong>MojPlayWin</strong><a href="/">Home</a></nav>';}
function footer_html(){echo '<footer class="footer">Mojtaba Roozegar</footer></div></body></html>';}
top_nav(); footer_html();
""").encode()
    fixed = transform(old)
    assert b"readfile($nav_file)" in fixed
    assert b"function head_html($a,$b,$c)" in fixed
    assert b'<nav class="nav"' not in fixed
    header = nav_from_home('<header class="mw-site-nav"><nav aria-label="Primary MojPlayWin navigation"><a href="/services/">Services</a><i data-mpw-earning-directory="v1"></i></nav></header>')
    assert header.count(MARK.encode()) == 1
    print("MPW_DYNAMIC_SHELL_SELFTEST_OK")

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) == 3 and sys.argv[1] == "publish":
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    else:
        raise SystemExit("Usage: selftest | publish RUN | rollback RUN")
