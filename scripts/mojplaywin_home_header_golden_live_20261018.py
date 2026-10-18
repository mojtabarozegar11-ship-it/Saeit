#!/usr/bin/env python3
"""Atomic, host-scoped MojPlayWin root HTML header repair. No Passenger or child sites."""
from __future__ import annotations
import hashlib
import json
import os
import pwd
import re
import shutil
import sys
import tempfile
from pathlib import Path

HOME = Path("/home/zomorod2")
DOCROOT = HOME / "mojplaywin.com"
PREVIEW = DOCROOT / "design-preview-20261017"
TARGET = PREVIEW / "production-home-20261017.html"
REWRITE = DOCROOT / ".htaccess"
BACKUPS = HOME / ".mojplaywin-backups"
BEFORE_SHA = "6f6e68ffb916521a741cfad9cb034638f86210280ccad86207fc03ae795a67de"
TAG = "mpw-top-search-gold-20261018"

CSS = r"""
<style id="mpw-top-header-gold-css-20261018">
/* Only the active MojPlayWin root's top navigation; not shared app styling. */
.mw-site-nav nav .mpw-header-search-gold {
  display:flex!important;align-items:stretch;gap:5px;flex:0 1 235px;min-width:175px;
  padding:4px!important;margin:0!important;border:1px solid #d8b460!important;
  border-radius:12px!important;background:#11100d!important;
  box-shadow:0 0 0 1px rgba(242,211,140,.13),0 8px 22px rgba(0,0,0,.24);
}
.mw-site-nav nav .mpw-header-search-gold:focus-within{
  outline:2px solid #ffe1a1;outline-offset:2px;
}
.mw-site-nav nav .mpw-header-search-gold input[type="search"]{
  min-width:0;width:100%;flex:1 1 auto;box-sizing:border-box;
  margin:0!important;padding:9px 10px!important;border:0!important;border-radius:8px!important;
  background:#11100d!important;color:#f8efdb!important;
  font:500 13px/1.4 system-ui,sans-serif!important;outline:none!important;
}
.mw-site-nav nav .mpw-header-search-gold input::placeholder{color:#e8d09a!important;opacity:1}
.mw-site-nav nav .mpw-header-search-gold button{
  flex:0 0 auto;min-width:41px;padding:7px 10px!important;margin:0!important;
  border:0!important;border-radius:8px!important;
  background:linear-gradient(145deg,#f8e4a8,#d7a746)!important;
  color:#171106!important;font-size:20px!important;font-weight:800!important;
  cursor:pointer;box-shadow:inset 0 1px 0 rgba(255,255,255,.3);
}
.mw-site-nav nav .mpw-header-search-gold button:hover{
  background:linear-gradient(145deg,#fff0c8,#e8bb5f)!important;
}
.mw-site-nav nav .mw-nav-cta[href="/store/"]{
  display:inline-flex!important;justify-content:center!important;align-items:center!important;
  white-space:nowrap!important;min-height:44px!important;padding:9px 15px!important;
  border:1px solid #f3d88b!important;border-radius:12px!important;
  background:linear-gradient(145deg,#f3d790,#c99a41)!important;
  color:#16110a!important;font-weight:800!important;text-decoration:none!important;
  box-shadow:0 8px 22px rgba(220,180,90,.20)!important;
}
.mw-site-nav nav .mw-nav-cta[href="/store/"]:focus-visible{
  outline:3px solid #fff0ba!important;outline-offset:3px;
}
@media(max-width:900px){
  .mw-site-nav nav .mpw-header-search-gold{flex:1 1 220px}
}
@media(max-width:500px){
  .mw-site-nav nav .mpw-header-search-gold{flex:1 1 100%;width:100%}
  .mw-site-nav nav .mw-nav-cta[href="/store/"]{flex:1 1 auto}
}
</style>
"""
SEARCH_FORM = (
    '<form id="' + TAG + '" class="mpw-header-search-gold" method="get" action="/search/" '
    'role="search" aria-label="Search Moj Play Win">'
    '<label for="mpw-top-search-input-20261018" '
    'style="position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0">'
    'Search Moj Play Win</label>'
    '<input id="mpw-top-search-input-20261018" type="search" name="q" '
    'placeholder="Search Moj Play Win" aria-label="Search Moj Play Win" required>'
    '<button type="submit" aria-label="Search">⌕</button>'
    '</form>'
)

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def check_target() -> None:
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Unexpected account identity")
    for p in (DOCROOT, PREVIEW, TARGET, REWRITE):
        if p.is_symlink() or not p.exists():
            raise RuntimeError("Required path missing or symlink: " + str(p))
    rules = REWRITE.read_text(encoding="utf8", errors="replace")
    if "RewriteRule ^.*$ /design-preview-20261017/production-home-20261017.html [END,QSD]" not in rules:
        raise RuntimeError("Active root rewrite changed: refuse to patch")

def build(original: str) -> str:
    if TAG in original:
        raise RuntimeError("Already patched: refusing duplicate injection")
    if original.count("<head>") != 1 or original.count("</head>") != 1:
        raise RuntimeError("Unexpected document head")
    if original.count("mpw-home-ten-guides") < 1 or "Mojtaba Roozegar" not in original:
        raise RuntimeError("Wrong MojPlayWin active home source")
    if "mpw-17x20-mainonly-autostart" not in original or "mpx-bottom-bar" not in original:
        raise RuntimeError("Existing home widgets must be preserved")
    found = list(re.finditer(r'<header\b[^>]*class="mw-site-nav"[^>]*>.*?</header>', original, re.S | re.I))
    if len(found) != 1:
        raise RuntimeError("Expected exactly one owner navigation header")
    old = found[0].group(0)
    ctas = list(re.finditer(r'<a\b[^>]*class="mw-nav-cta"[^>]*href="/store/"[^>]*>[^<]*</a>', old, re.S | re.I))
    if len(ctas) != 1:
        raise RuntimeError("Expected exactly one existing store CTA in header")
    prior = ctas[0].group(0)
    updated_link = re.sub(r'>[^<]*</a>$', '>Enter Store ↗</a>', prior, count=1)
    revised_header = old.replace(prior, SEARCH_FORM + updated_link, 1)
    changed = original[:found[0].start()] + revised_header + original[found[0].end():]
    changed = changed.replace("</head>", CSS + "</head>", 1)
    if len(changed) - len(original) > 6500 or len(changed) - len(original) < 2000:
        raise RuntimeError("Unexpected modification footprint")
    suffix = original[original.rfind('<footer class="mw-site-footer"'):]
    if not suffix or not changed.endswith(suffix):
        raise RuntimeError("Footer or trailing content changed")
    if changed.count(TAG) != 1 or changed.count('action="/search/"') != 1:
        raise RuntimeError("Search form verification failed")
    anchor_pattern = r'<a\b[^>]*href="/store/"'
    if len(re.findall(anchor_pattern, changed)) != len(re.findall(anchor_pattern, original)):
        raise RuntimeError("Existing store targets changed")
    return changed

def atomic_replace(path: Path, payload: bytes, mode: int) -> None:
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".mpw-gold-", delete=False) as tmp:
            temp_path = Path(tmp.name)
            tmp.write(payload)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

def folder_for(run_id: str) -> Path:
    if not re.fullmatch(r"[0-9]{1,20}", run_id):
        raise RuntimeError("Invalid run ID")
    return BACKUPS / ("mpw-gold-search-" + run_id)

def apply(run_id: str) -> None:
    check_target()
    previous = TARGET.read_bytes()
    if digest(previous) != BEFORE_SHA:
        raise RuntimeError("Live home changed since read-only audit; do not overwrite")
    proposed = build(previous.decode("utf8")).encode("utf8")
    backup = folder_for(run_id)
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("Backup folder already exists")
    backup.mkdir(mode=0o700, parents=True)
    previous_mode = TARGET.stat().st_mode & 0o777
    shutil.copy2(TARGET, backup / "production-home.original.html")
    if digest((backup / "production-home.original.html").read_bytes()) != BEFORE_SHA:
        raise RuntimeError("Backup hash mismatch")
    meta = {"old": BEFORE_SHA, "new": digest(proposed), "mode": previous_mode}
    (backup / "manifest.json").write_text(json.dumps(meta), encoding="utf8")
    atomic_replace(TARGET, proposed, previous_mode)
    if digest(TARGET.read_bytes()) != meta["new"]:
        raise RuntimeError("Postwrite hash mismatch; recover with rollback")
    print("MPW_GOLD_HOME_ATOMIC_PATCH_OK=true", flush=True)
    print("MPW_GOLD_HOME_BACKUP_SHA256=" + meta["old"], flush=True)
    print("MPW_GOLD_HOME_NEW_SHA256=" + meta["new"], flush=True)
    print("MPW_NO_PASSENGER_RESTART=true", flush=True)

def rollback(run_id: str) -> None:
    check_target()
    backup = folder_for(run_id)
    if backup.is_symlink():
        raise RuntimeError("Unsafe backup symlink")
    meta = json.loads((backup / "manifest.json").read_text())
    old = (backup / "production-home.original.html").read_bytes()
    if digest(old) != meta["old"]:
        raise RuntimeError("Original backup digest mismatch")
    if digest(TARGET.read_bytes()) not in (meta["old"], meta["new"]):
        raise RuntimeError("Concurrent live edit; refuse to overwrite")
    atomic_replace(TARGET, old, meta["mode"])
    if digest(TARGET.read_bytes()) != meta["old"]:
        raise RuntimeError("Rollback verification failed")
    print("MPW_GOLD_HOME_ROLLBACK_VERIFIED=true", flush=True)

def selftest() -> None:
    dummy = ('<html><head></head><body><header class="mw-site-nav"><nav>'
             '<a class="mw-nav-cta" href="/store/">Digital Store ↗</a>'
             '</nav></header><div id="mpw-home-ten-guides">a</div>'
             '<span>mpw-17x20-mainonly-autostart</span>'
             '<footer class="mw-site-footer"><span>mpx-bottom-bar</span>'
             '<span>Mojtaba Roozegar</span></footer></body></html>')
    changed = build(dummy)
    assert changed.count(TAG) == 1
    assert len(re.findall(r'<a\b[^>]*href="/store/"', changed)) == 1
    assert changed.endswith(dummy[dummy.index('<footer class="mw-site-footer"'):])
    print("MPW_STATIC_HOME_PATCH_SELFTEST_OK=true")

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) == 3 and sys.argv[1] in ("apply", "rollback"):
        (apply if sys.argv[1] == "apply" else rollback)(sys.argv[2])
    else:
        raise SystemExit("Usage: selftest | apply RUN_ID | rollback RUN_ID")
