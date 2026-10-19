#!/usr/bin/env python3
"""Fail-closed one-file MojPlayWin Company obsolete mobile-nav null guard."""
from pathlib import Path
import hashlib,json,os,re,stat,sys,tempfile
HOME=Path("/home/zomorod2")
ROOT=HOME/"mojplaywin.com"
PAGE=ROOT/"design-preview-20261017/mpw-ten-editorials-20261018/pages/company.html"
RULES=ROOT/".htaccess"
MARK="MPW_COMPANY_NAV_NULL_GUARD_20261019"
OLD1="if(b){b.addEventListener('click',()=>{n.classList.toggle('open');b.setAttribute('aria-expanded',n.classList.contains('open'));});}"
OLD2="n.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{n.classList.remove('open');b.setAttribute('aria-expanded','false');}));"
OLD3="window.addEventListener('keydown',e=>{if(e.key==='Escape'){n.classList.remove('open');b.setAttribute('aria-expanded','false');}});"
OLD_DECL="const b=document.querySelector('.menu-toggle'),n=document.querySelector('.nav');"
def sha(v):return hashlib.sha256(v).hexdigest()
def fail(x):raise RuntimeError(x)
def pths(run):
    if not re.fullmatch(r"[0-9]{9,20}",run):fail("Invalid GitHub run")
    return HOME/(".mpw-company-nav-"+run+".bak"),HOME/(".mpw-company-nav-"+run+".json")
def patch(html):
    if MARK in html:fail("Already patched")
    if html.count("MPW_ABOUT_COMPANY_SEMANTIC_20261019_V2")!=1:fail("Unknown Company edition")
    for old in (OLD_DECL,OLD1,OLD2,OLD3):
        if html.count(old)!=1:fail("Obsolete Company navigation snippet changed")
    if html.count('class="mpw-ten-card"')!=10:fail("Company guide cards changed")
    updated=html.replace(OLD1,OLD1.replace("if(b){","if(b&&n){"),1)
    updated=updated.replace(OLD2,"if(b&&n){"+OLD2+"}",1)
    updated=updated.replace(OLD3,"if(b&&n){"+OLD3+"}",1)
    if updated.count("</body>")!=1:fail("HTML body closing changed")
    updated=updated.replace("</body>","<!-- "+MARK+" -->\n</body>",1)
    if updated.count("if(b&&n){")!=3:fail("Incomplete nav guard")
    if updated.count('class="mpw-ten-card"')!=10:fail("Company content unexpectedly changed")
    return updated
def atomic(data,mode):
    if PAGE.is_symlink():fail("Symlink write denied")
    fd,tmp=tempfile.mkstemp(dir=PAGE.parent,prefix=".mpw-company-nav-")
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,PAGE)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)
def guard():
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve()!=ROOT:fail("Root changed")
    if not PAGE.is_file() or PAGE.is_symlink() or PAGE.parent.is_symlink() or not RULES.is_file() or RULES.is_symlink():
        fail("Static Company target not safe")
    if "mpw-ten-editorials-20261018/pages/company.html" not in RULES.read_text("utf-8",errors="replace"):
        fail("Company rewrite route changed")
def install(run):
    guard()
    backup,manifest=pths(run)
    if backup.exists() or manifest.exists():fail("Run reused")
    old=PAGE.read_bytes()
    new=patch(old.decode("utf-8")).encode("utf-8")
    state={"run":run,"before":sha(old),"after":sha(new),"page":str(PAGE)}
    with backup.open("xb") as f:
        os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
    with manifest.open("x") as f:
        os.fchmod(f.fileno(),0o600);json.dump(state,f);f.flush();os.fsync(f.fileno())
    if PAGE.read_bytes()!=old:fail("Concurrent change")
    atomic(new,stat.S_IMODE(PAGE.stat().st_mode))
    if sha(PAGE.read_bytes())!=state["after"]:fail("Postwrite checksum mismatch")
    print("MPW_COMPANY_NAV_GUARD="+json.dumps(state))
def rollback(run):
    guard()
    backup,manifest=pths(run)
    if not manifest.is_file() or manifest.is_symlink() or not backup.is_file() or backup.is_symlink():
        fail("Recovery state missing")
    state=json.loads(manifest.read_text("utf-8"))
    prior=backup.read_bytes()
    if state["run"]!=run or state["page"]!=str(PAGE) or sha(prior)!=state["before"]:
        fail("Recovery manifest invalid")
    if sha(PAGE.read_bytes())!=state["after"]:fail("Refusing rollback over newer edit")
    atomic(prior,stat.S_IMODE(PAGE.stat().st_mode))
    if sha(PAGE.read_bytes())!=state["before"]:fail("Rollback failed")
    print("MPW_COMPANY_NAV_ROLLBACK=VERIFIED")
if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1] not in ("install","rollback"):fail("install|rollback RUN_ID")
    {"install":install,"rollback":rollback}[sys.argv[1]](sys.argv[2])
