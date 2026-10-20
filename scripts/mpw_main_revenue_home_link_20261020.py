#!/usr/bin/env python3
"""Atomic main-home-only link to already verified MojPlayWin twelve-offer revenue hub."""
import hashlib,json,os,re,stat,sys,tempfile
from pathlib import Path

ROOT=Path("/home/zomorod2/mojplaywin.com")
PAGE=ROOT/"design-preview-20261017/production-home-20261017.html"
HT=ROOT/".htaccess"
MARKER='id="mpw-revenue-offers-20261020"'
SNIPPET='''<section id="mpw-revenue-offers-20261020" aria-labelledby="mpw-revenue-offers-title" style="max-width:1150px;margin:60px auto;padding:30px 24px;background:linear-gradient(120deg,#101726,#202a3a);border:1px solid #c9a66e;border-radius:20px;color:#f4f1e9;text-align:left;box-sizing:border-box">
<p style="margin:0;color:#efc987;font-size:.88rem;font-weight:800;letter-spacing:.08em">MOJPLAYWIN · TWELVE DIGITAL OFFERS</p>
<h2 id="mpw-revenue-offers-title" style="font-size:clamp(1.5rem,3vw,2.3rem);line-height:1.28;margin:13px 0">Digital services and practical business tools</h2>
<p style="max-width:750px;line-height:1.7;color:#dce4ef">Explore website audits, landing pages, AI workflow services, business templates and creative software concepts, with clear pricing guidance and current availability.</p>
<a href="/mpw-editorial/revenue/index.html" style="display:inline-block;padding:12px 22px;background:#e5bb70;color:#171b23;border-radius:12px;font-weight:800;text-decoration:none">Explore all 12 offers &#8594;</a>
<p style="font-size:.88rem;color:#bac8da">Service quotes and product releases are confirmed individually. No payment is collected from this introductory page.</p></section>
'''
def sha(data):return hashlib.sha256(data).hexdigest()
def guard():
    if ROOT.is_symlink() or not ROOT.is_dir() or ROOT.resolve()!=ROOT:raise RuntimeError("Unverified primary site root")
    if PAGE.is_symlink() or not PAGE.is_file() or PAGE.parent.is_symlink() or not HT.is_file() or HT.is_symlink():raise RuntimeError("Unverified homepage path")
    if "production-home-20261017.html" not in HT.read_text("utf8","replace"):raise RuntimeError("Home route is not pinned")
    target=ROOT/"mpw-editorial/revenue/index.html"
    if target.is_symlink() or not target.is_file():raise RuntimeError("Revenue hub not installed")
def backup(run):
    if not re.fullmatch("[0-9]{8,20}",run):raise RuntimeError("Invalid run id")
    return ROOT.parent/(".mpw-revenue-home-"+run+".backup")
def transform(before):
    text=before.decode("utf8")
    if MARKER in text:raise RuntimeError("Home link already installed")
    if text.lower().count("</main>")!=1 or text.count("<html")!=1:raise RuntimeError("Unexpected home structure")
    newer=text.replace("</main>",SNIPPET+"</main>",1)
    if newer.count(MARKER)!=1 or newer.count('href="/mpw-editorial/revenue/index.html"')!=1:raise RuntimeError("Unsafe transformation")
    if newer.replace(SNIPPET,"",1)!=text:raise RuntimeError("Patch modified unrelated home content")
    return newer.encode("utf8")
def write(new):
    mode=stat.S_IMODE(PAGE.stat().st_mode)
    fd,name=tempfile.mkstemp(prefix=".mpw-revenue-home-stage-",dir=PAGE.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:f.write(new);f.flush();os.fsync(f.fileno())
        os.replace(name,PAGE)
    finally:
        if os.path.exists(name):os.unlink(name)
def install(run):
    guard()
    original=PAGE.read_bytes()
    new=transform(original)
    dest=backup(run)
    if dest.exists() or dest.is_symlink():raise RuntimeError("Backup collision")
    with dest.open("xb") as f:
        os.fchmod(f.fileno(),0o600)
        f.write(original);f.flush();os.fsync(f.fileno())
    if PAGE.read_bytes()!=original:raise RuntimeError("Homepage changed concurrently")
    try:
        write(new)
        if sha(PAGE.read_bytes())!=sha(new):raise RuntimeError("Homepage postwrite digest mismatch")
    except BaseException:
        if PAGE.read_bytes()==new:write(original)
        raise
    print("MPW_HOME_REVENUE_LINK_INSTALLED="+json.dumps({"file":"main site home only","original_sha":sha(original),"new_sha":sha(new),"other_sites_touched":False}))
def rollback(run):
    guard()
    saved=backup(run)
    if not saved.is_file() or saved.is_symlink():raise RuntimeError("Missing verified backup")
    original=saved.read_bytes();now=PAGE.read_bytes()
    if transform(original)!=now:raise RuntimeError("Refuse rollback over concurrent changes")
    write(original)
    if sha(PAGE.read_bytes())!=sha(original):raise RuntimeError("Rollback verification mismatch")
    print("MPW_HOME_REVENUE_LINK_ROLLBACK=PASS")
def selftest():
    raw=b'<!doctype html><html lang="en"><main><h1>Original</h1></main></html>'
    changed=transform(raw)
    assert MARKER.encode() in changed and changed.count(b'Original')==1
    assert changed.replace(SNIPPET.encode(),b'',1)==raw
    print("MPW_HOME_REVENUE_LINK_SELFTEST=PASS")
if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ("install","rollback"):(install if sys.argv[1]=="install" else rollback)(sys.argv[2])
    else:raise SystemExit("selftest|install RUN_ID|rollback RUN_ID")
