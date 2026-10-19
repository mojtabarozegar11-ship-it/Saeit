#!/usr/bin/env python3
"""Fail-closed one-file favicon unification for MojPlayWin /company/ only."""
from pathlib import Path
import hashlib,json,os,re,stat,sys,tempfile

ROOT=Path("/home/zomorod2/mojplaywin.com")
PAGE=ROOT/"design-preview-20261017/mpw-ten-editorials-20261018/pages/company.html"
ROUTES=ROOT/".htaccess"
PREVIOUS="/static/site/company/company-logo.9155199ecf23.png"
CORRECT="/static/site/mojplaywin-coin-logo.420e0d1f954b.png"
MARK="MPW_COMPANY_FAVICON_UNIFIED_20261019"
def fail(text):raise RuntimeError(text)
def sha(x):return hashlib.sha256(x).hexdigest()
def paths(rid):
    if not re.fullmatch(r"[0-9]{9,20}",rid):fail("Invalid run identifier")
    return ROOT.parent/(".mpw-company-favicon-"+rid+".bak"),ROOT.parent/(".mpw-company-favicon-"+rid+".json")
def patch(s):
    if MARK in s:fail("Already patched")
    if s.count("MPW_ABOUT_COMPANY_SEMANTIC_20261019_V2")!=1:fail("Previous approved theme edition missing")
    original_tags=re.findall(r"<link\b[^>]*>",s,flags=re.I)
    matching=[tag for tag in original_tags if re.search(r'\brel=["\x27]icon["\x27]',tag,re.I)]
    if len(matching)!=1:fail("Cannot uniquely isolate company favicon")
    old=matching[0]
    if old.count(PREVIOUS)!=1:fail("Known icon source changed")
    if s.count(old)!=1:fail("Ambiguous favicon element")
    return s.replace(old,old.replace(PREVIOUS,CORRECT),1).replace("</head>","<!-- "+MARK+" -->\n</head>",1)
def atomic(page,content,mode):
    fd,tmp=tempfile.mkstemp(dir=page.parent,prefix=".mpw-company-favicon-")
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(content);f.flush();os.fsync(f.fileno())
        os.replace(tmp,page)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)
def guard():
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve()!=ROOT:fail("Site document root mismatch")
    if not PAGE.is_file() or PAGE.is_symlink() or PAGE.parent.is_symlink() or not ROUTES.is_file():fail("Unsafe target")
    if "mpw-ten-editorials-20261018/pages/company.html" not in ROUTES.read_text(errors="replace"):
        fail("Priority company route changed")
def install(rid):
    guard()
    backup,manifest=paths(rid)
    if backup.exists() or manifest.exists():fail("Existing run")
    before=PAGE.read_bytes()
    after=patch(before.decode("utf-8")).encode("utf-8")
    if after==before:fail("No modifications")
    with backup.open("xb") as f:
        os.fchmod(f.fileno(),0o600);f.write(before);f.flush();os.fsync(f.fileno())
    record={"run":rid,"old":sha(before),"new":sha(after)}
    with manifest.open("x") as f:
        os.fchmod(f.fileno(),0o600);json.dump(record,f);f.flush();os.fsync(f.fileno())
    if PAGE.read_bytes()!=before:fail("Concurrent company modification")
    atomic(PAGE,after,stat.S_IMODE(PAGE.stat().st_mode))
    if sha(PAGE.read_bytes())!=record["new"]:fail("Postwrite mismatch")
    print("MPW_COMPANY_FAVICON="+json.dumps(record))
def rollback(rid):
    guard()
    backup,manifest=paths(rid)
    rec=json.loads(manifest.read_text("utf-8"))
    prev=backup.read_bytes()
    if rec["run"]!=rid or sha(prev)!=rec["old"] or sha(PAGE.read_bytes())!=rec["new"]:
        fail("Rollback refused due to integrity or concurrent changes")
    atomic(PAGE,prev,stat.S_IMODE(PAGE.stat().st_mode))
    if sha(PAGE.read_bytes())!=rec["old"]:fail("Failed favicon rollback")
    print("MPW_COMPANY_FAVICON_ROLLBACK=PASS")
if __name__=="__main__":
    if len(sys.argv)!=3:fail("install|rollback RUN_ID")
    {"install":install,"rollback":rollback}[sys.argv[1]](sys.argv[2])
