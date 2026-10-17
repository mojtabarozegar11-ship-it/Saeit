#!/usr/bin/env python3
"""Atomic Moj Play Win brand spelling and SEO metadata update on the approved
production HOME HTML file only. Independent time-bounded fail-safe rollback.
Never mutate Passenger, .htaccess, SQLite/DB, commercial pages or child sites.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path("/home/zomorod2/mojplaywin.com")
SOURCE = ROOT / "design-preview-20261017/production-home-20261017.html"
PRIVATE = Path("/home/zomorod2/.mpw-home-brand-seo-20261017")
BACKUP = PRIVATE / "production-home-before-seo.html"
STATE = PRIVATE / "state.json"
GUARD = PRIVATE / "rollback-guard.py"
OLD_SHA = "8fd8cb59d10eb48adb95a030ee427a27869eb19b29e8928a10d87f895f4a03ce"
BACKUP_ROOT_STATE = Path("/home/zomorod2/.mpw-main-root-route-release-20261017/state.json")
MARKER = "MJWP_ROOT_CANDIDATE_ONLY_20261017"

TITLE = "Moj Play Win | Games, AI, Research & Digital Products"
DESCRIPTION = (
    "Moj Play Win (MojPlayWin) brings together original games, AI tools, "
    "scientific research, web development and digital products."
)
OG_DESCRIPTION = (
    "Explore original games, AI tools, scientific research and digital "
    "products at Moj Play Win (MojPlayWin)."
)
SCHEMA = {
    "@context": "https://schema.org",
    "@graph": [
        {"@type": "Organization", "@id": "https://mojplaywin.com/#organization",
         "name": "Moj Play Win", "alternateName": ["MojPlayWin", "Moj play win"],
         "url": "https://mojplaywin.com/"},
        {"@type": "WebSite", "@id": "https://mojplaywin.com/#website",
         "name": "Moj Play Win", "alternateName": "MojPlayWin",
         "url": "https://mojplaywin.com/", "inLanguage": "en",
         "publisher": {"@id": "https://mojplaywin.com/#organization"}}
    ]
}

def digest(buf: bytes) -> str:
    return hashlib.sha256(buf).hexdigest()

def guarded_host():
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError("unsafe root")
    if SOURCE.is_symlink() or not SOURCE.is_file() or SOURCE.stat().st_uid != os.getuid():
        raise RuntimeError("unsafe source")
    if PRIVATE.is_symlink():
        raise RuntimeError("unsafe private location")
    state = json.loads(BACKUP_ROOT_STATE.read_text(encoding="utf-8"))
    if state.get("status") != "verified_committed" or state.get("mode") != "root":
        raise RuntimeError("expected root routing release not committed")
    ht = ROOT / ".htaccess"
    if ht.is_symlink() or digest(ht.read_bytes()) != state.get("candidate_sha"):
        raise RuntimeError("root routing drift")
    return state

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise RuntimeError("exact match failed for "+label+"; seen="+str(n))
    return text.replace(old, new, 1)

def urls_in(html):
    return re.findall(r'(?:href|src|action)="([^"]*)"', html)

def compose(old: bytes) -> bytes:
    source = old.decode("utf-8")
    if source.count("<title>") != 1 or source.count("<h1") != 1:
        raise RuntimeError("unexpected heading or title multiplicity")
    changes = [
        ("<title>MojPlayWin | Research, Games & Learning</title>",
         "<title>"+TITLE+"</title>", "page title"),
        ('<meta name="description" content="MojPlayWin connects scientific research, modern technology, games, and practical education with a curated digital catalog.">',
         '<meta name="description" content="'+DESCRIPTION+'">', "page meta description"),
        ('<meta property="og:site_name" content="MojPlayWin">',
         '<meta property="og:site_name" content="Moj Play Win">', "og site name"),
        ('<meta property="og:title" content="MojPlayWin | Digital Products, Research & Games">',
         '<meta property="og:title" content="'+TITLE+'">', "og title"),
        ('<meta property="og:description" content="Explore MojPlayWin digital products, original games, research and learning.">',
         '<meta property="og:description" content="'+OG_DESCRIPTION+'">', "og description"),
        ('<h1 id="mw-home-title">MojPlay<em>Win</em></h1>',
         '<h1 id="mw-home-title">Moj <em>Play</em> Win</h1>', "single visible h1"),
    ]
    for old_str, new_str, label in changes:
        source = replace_once(source, old_str, new_str, label)
    supplement = (
        '<meta name="robots" content="index,follow,max-image-preview:large">\n'
        '<meta property="og:locale" content="en_US">\n'
        '<meta name="twitter:title" content="'+TITLE+'">\n'
        '<meta name="twitter:description" content="Original games, research, AI and digital products at Moj Play Win.">\n'
        '<script type="application/ld+json">'+json.dumps(SCHEMA, ensure_ascii=False, separators=(",", ":"))+'</script>'
    )
    source = replace_once(
        source, '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:card" content="summary_large_image">\n'+supplement,
        "site JSON-LD + twitter + indexability"
    )
    # Display name while keeping existing address, logo and copyright untouched.
    for old_str,new_str in [
        ('<span class="mw-brand-copy"><strong>MojPlayWin</strong><small>Play · Build · Evolve</small>',
         '<span class="mw-brand-copy"><strong>Moj Play Win</strong><small>Play · Build · Evolve</small>'),
        ('aria-label="MojPlayWin home"','aria-label="Moj Play Win home"'),
        ('alt="MojPlayWin logo"','alt="Moj Play Win logo"'),
        ('MOJPLAYWIN · GLOBAL WEB ENGINEERING · DIGITAL INNOVATION',
         'MOJ PLAY WIN · GLOBAL WEB ENGINEERING · DIGITAL INNOVATION'),
        ('MojPlayWin brings scientific research, modern digital technology, gaming, and education together. Explore original projects, useful learning, and a growing collection of digital products.',
         'Moj Play Win (MojPlayWin) brings scientific research, digital technology, original games and education together. Explore practical learning and digital products.')
    ]:
        if old_str in source:
            source = replace_once(source, old_str, new_str, "visitor brand mention")
    upgraded = source.encode("utf-8")
    if urls_in(source) != urls_in(old.decode("utf-8")):
        raise RuntimeError("SEO update would change URL, forms, assets or links")
    if len(upgraded) - len(old) > 2300 or len(upgraded) - len(old) < 600:
        raise RuntimeError("unexpected file size delta")
    for marker,n in [('class="mpo-orbit-card"',18),('class="mpo-ring"',3),
                     ('id="home-guide-',10),('<h1',1),('<title',1)]:
        if upgraded.count(marker.encode("utf-8")) != n:
            raise RuntimeError("original page content preservation failed")
    for marker in ('MJWP_ROOT_CANDIDATE_ONLY_20261017',
                   'href="https://mojplaywin.com/"', 'data-globe-orbit="continuous"',
                   '© 2022 MojPlayWin. All rights reserved.'):
        if marker not in source:
            raise RuntimeError("important existing marker missing")
    if "noindex,nofollow,noarchive" in source or "MojPlayWin" not in source:
        raise RuntimeError("unexpected indexability or original spelling lost")
    return upgraded

def atomic_write(data: bytes):
    temp = SOURCE.with_name(".seo-new-"+str(os.getpid()))
    fd = os.open(str(temp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,"wb") as dst:
            dst.write(data); dst.flush(); os.fsync(dst.fileno())
        os.chmod(temp,0o644)
        os.replace(temp,SOURCE)
    finally:
        if temp.exists():temp.unlink()

def write_state(state):
    temp = PRIVATE/("state-"+str(os.getpid())+".tmp")
    if temp.exists() or temp.is_symlink():
        raise RuntimeError("unsafe state temp")
    temp.write_text(json.dumps(state,sort_keys=True),encoding="utf-8")
    os.chmod(temp,0o600)
    os.replace(temp,STATE)

def status():
    if STATE.is_symlink() or not STATE.is_file():
        raise RuntimeError("missing release state")
    return json.loads(STATE.read_text(encoding="utf-8"))

def watchdog():
    script = """import hashlib,json,os,time
from pathlib import Path
time.sleep(180)
private=Path('/home/zomorod2/.mpw-home-brand-seo-20261017')
source=Path('/home/zomorod2/mojplaywin.com/design-preview-20261017/production-home-20261017.html')
try:
    st=json.loads((private/'state.json').read_text())
    if st.get('status')!='armed':raise SystemExit
    backup=(private/'production-home-before-seo.html').read_bytes()
    if hashlib.sha256(backup).hexdigest()!=st['old_sha']:raise SystemExit
    if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest()!=st['new_sha']:raise SystemExit
    tmp=source.with_name('.seo-guard-'+str(os.getpid()))
    fd=os.open(str(tmp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:
        f.write(backup);f.flush();os.fsync(f.fileno())
    os.chmod(tmp,0o644)
    os.replace(tmp,source)
    (private/'state.json').write_text(json.dumps({**st,'status':'watchdog_rolled_back'}))
except Exception:pass
"""
    GUARD.write_text(script,encoding="utf-8")
    os.chmod(GUARD,0o600)
    subprocess.Popen([sys.executable,str(GUARD)],stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)

def deploy():
    guarded_host()
    old=SOURCE.read_bytes()
    if digest(old)!=OLD_SHA:
        raise RuntimeError("different live candidate; no write allowed")
    new=compose(old)
    if not PRIVATE.exists():PRIVATE.mkdir(mode=0o700)
    if PRIVATE.stat().st_uid!=os.getuid() or PRIVATE.stat().st_mode & 0o077:
        raise RuntimeError("private dir permissions unsafe")
    if STATE.exists() and status().get("status")=="armed":
        raise RuntimeError("earlier SEO attempt still armed")
    if BACKUP.is_symlink() or (BACKUP.exists() and BACKUP.read_bytes()!=old):
        raise RuntimeError("untrusted existing backup")
    if not BACKUP.exists():
        with BACKUP.open("xb") as f:
            f.write(old);f.flush();os.fsync(f.fileno())
        os.chmod(BACKUP,0o600)
    st={"status":"armed","old_sha":OLD_SHA,"new_sha":digest(new),
        "target":"main-home-html-only","rollback_seconds":180}
    write_state(st)
    watchdog()
    atomic_write(new)
    if digest(SOURCE.read_bytes())!=st["new_sha"]:
        raise RuntimeError("candidate postwrite mismatch")
    print(json.dumps({"classification":"MAIN_HOME_SPACED_BRAND_SEO_ARMED",
      "old_sha":OLD_SHA,"new_sha":st["new_sha"],
      "all_original_urls_preserved":True,"auto_rollback_seconds":180},sort_keys=True),flush=True)

def rollback():
    st=status()
    backup=BACKUP.read_bytes()
    if digest(backup)!=st["old_sha"]:
        raise RuntimeError("invalid rollback backup")
    if SOURCE.is_symlink():raise RuntimeError("target now symlink")
    current=digest(SOURCE.read_bytes())
    if current!=st["old_sha"]:
        if current!=st["new_sha"]:raise RuntimeError("refuse to overwrite concurrent changes")
        atomic_write(backup)
    write_state({**st,"status":"rolled_back"})
    print("MAIN_HOME_SEO_ORIGINAL_RESTORED_NO_SHARED_FILE_WRITES",flush=True)

def commit():
    guarded_host()
    st=status()
    if st.get("status")!="armed" or digest(SOURCE.read_bytes())!=st["new_sha"]:
        raise RuntimeError("not an armed, verified SEO update")
    upgraded=SOURCE.read_text(encoding="utf-8")
    if "Moj Play Win | Games, AI, Research & Digital Products" not in upgraded:
        raise RuntimeError("title absent")
    write_state({**st,"status":"verified_committed"})
    print("MAIN_HOME_SEO_RELEASE_COMMITTED_ORIGINAL_BACKUP_RETAINED",flush=True)

if __name__=="__main__":
    try:
        if len(sys.argv)!=2:raise RuntimeError("operation required")
        op=sys.argv[1]
        if op=="deploy":deploy()
        elif op=="rollback":rollback()
        elif op=="commit":commit()
        else:raise RuntimeError("unknown operation")
    except Exception as exc:
        print("SEO_OPERATION_REJECTED_"+type(exc).__name__,file=sys.stderr)
        raise SystemExit(3)
