#!/usr/bin/env python3
"""MojPlayWin main-domain only: atomic one-line footer, no routing or app restart.

Touches 19 proven priority-routed static page files and the shared Django
MojPlayWin footer template; DOES NOT edit child sites, .htaccess, orders,
payment code, database or other server software.
"""
from __future__ import annotations
import hashlib,html,json,os,pwd,re,stat,sys,tempfile
from pathlib import Path

HOME=Path("/home/zomorod2")
ROOT=HOME/"mojplaywin.com"
APP=HOME/"Saeit-staging"
PAGES=ROOT/"design-preview-20261017/mpw-ten-editorials-20261018/pages"
HT=ROOT/".htaccess"
STATIC=(
    "about-mojtaba-rozegar","about","agents","company","economy",
    "industry","knowledge","market","research","services","studio",
    "ventures-agriculture","ventures-cafe-restaurant","ventures-carpets",
    "ventures-currency-crypto","ventures-ecommerce","ventures-fuel-station",
    "ventures-hospitality","ventures-jewelry-gold"
)
TEMPLATE=APP/"core/templates/mojplaywin/footer.html"
DISPLAY="☆ All Rights Reserved. ☆ 2022. ☆ Mojtaba roozegar ☆"
MARK="mpw-legal-one-line"
CSS_ID="mpw-footer-single-line-css-20261019"
LINE=(
    '<span class="'+MARK+'" data-mpw-final-founder="true" '
    'data-mpw-founder-source="Mojtaba Roozegar" '
    'aria-label="All Rights Reserved. 2022. Mojtaba roozegar" '
    'style="display:block;flex:1 1 100%;grid-column:1/-1;'
    'width:100%;max-width:100%;box-sizing:border-box;white-space:nowrap;'
    'overflow-x:auto;text-align:center;margin:0;padding:10px 4px;'
    'font-size:clamp(10px,2.5vw,14px);line-height:1.5;letter-spacing:0;'
    'color:#f3d184;font-weight:750">'+DISPLAY+'</span>'
)
CSS=('<style id="'+CSS_ID+'">'
     'footer.mw-site-footer:has(.'+MARK+')::after,'
     'footer.mpw-footer:has(.'+MARK+')::after'
     '{content:none!important;display:none!important}'
     'footer.mw-site-footer .mpx-bottom-bar:has(.'+MARK+')'
     '{flex-basis:100%!important;grid-column:1/-1;display:block!important;'
     'text-align:center}'
     'footer .'+MARK+'{white-space:nowrap!important}'
     '</style>')

def sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def fail(message):raise RuntimeError(message)
def targets():
    return [PAGES/(slug+".html") for slug in STATIC]+[TEMPLATE]

def before_guard():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":fail("Incorrect deployment user")
    for d in (ROOT,APP,PAGES,TEMPLATE.parent):
        if not d.is_dir() or d.is_symlink():fail("Unsafe directory "+str(d))
    if not HT.is_file() or HT.is_symlink():fail("Missing rewrite routing")
    rewrite=HT.read_text("utf-8",errors="replace")
    for slug in STATIC:
        ref="/design-preview-20261017/mpw-ten-editorials-20261018/pages/"+slug+".html"
        if ref not in rewrite:fail("Required static route no longer isolated: "+slug)
    wsgi=ROOT/"passenger_wsgi.py"
    if not wsgi.is_file() or wsgi.is_symlink() or "Saeit-staging" not in wsgi.read_text("utf-8",errors="replace"):
        fail("Wrong MojPlayWin app template origin")
    if len(targets())!=20:fail("Target inventory changed")
    for p in targets():
        if not p.is_file() or p.is_symlink() or p.parent.is_symlink():fail("Target missing or symlink: "+str(p))

def patch(doc:str)->str:
    if MARK in doc or CSS_ID in doc:fail("Already installed")
    match=list(re.finditer(r'<footer\b[^>]*>[\s\S]*?</footer\s*>',doc,re.I))
    chosen=[m for m in match if ("mw-site-footer" in m.group(0) or "mpw-footer" in m.group(0))
            and "MojPlayWin" in m.group(0)]
    if len(chosen)!=1:fail("Must identify one MojPlayWin footer; got "+str(len(chosen)))
    m=chosen[0];seg=m.group(0)
    # The common modern template has a complete original copyright bar.
    bars=re.findall(r'<div class="mpx-bottom-bar">[\s\S]*?</div>',seg,re.I)
    if len(bars)==1:
        seg=seg.replace(bars[0],'<div class="mpx-bottom-bar">'+LINE+'</div>',1)
    elif len(bars)==0:
        # Pages built before the modern footer carry a stand-alone gold name
        # block. Replace only that, and remove the redundant short copyright
        # text; retain the Privacy/Terms/Cookies link container intact.
        old=re.findall(r'<span\b[^>]*\bclass="mpw-founder-footer-final"[^>]*>\s*Mojtaba Roozegar\s*</span>',seg,re.I)
        if len(old)!=1:fail("Missing or repeated legacy founder credit")
        seg=seg.replace(old[0],'<div class="mpw-footer-legal-wrap" style="flex-basis:100%;grid-column:1/-1;width:100%;min-width:0;border-top:1px solid rgba(218,176,89,.38);margin-top:12px">'+LINE+'</div>',1)
        short=re.findall(r'<span>\s*©\s*MojPlayWin\s*</span>',seg,re.I)
        if len(short)>1:fail("Repeated legacy copyright blocks")
        if len(short)==1:seg=seg.replace(short[0],"",1)
    else:fail("Duplicated bottom bars")
    if "Mojtaba Roozegar</span>" in seg:fail("Old founder text still visible")
    if seg.count(DISPLAY)!=1 or seg.count(MARK)!=1:fail("Expected exactly one final legal line")
    if seg.count("data-mpw-final-founder")!=1:fail("Old footer JS deduplication marker wrong")
    if seg.count("data-mpw-founder-source")!=1:fail("Dynamic PHP compatibility marker missing")
    if seg.count("</footer>")!=1:fail("Unexpected footer end")
    seg=seg.replace("</footer>",CSS+"\n</footer>",1)
    out=doc[:m.start()]+seg+doc[m.end():]
    if len(out)<len(doc)//2:fail("Unexpected content removal")
    if out.count(CSS_ID)!=1:fail("CSS integrity check failed")
    return out

def prepare():
    before_guard()
    batch=[]
    for p in targets():
        raw=p.read_bytes()
        new=patch(raw.decode("utf-8")).encode("utf-8")
        mode=stat.S_IMODE(p.stat().st_mode)
        batch.append((p,raw,new,mode))
    return batch

def atomic(p:Path,raw:bytes,mode:int):
    if p.is_symlink() or not p.is_file():fail("Unsafe atomic target")
    fd,temp=tempfile.mkstemp(dir=p.parent,prefix=".mpw-legal-one-line-")
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(temp,p)
    finally:
        if os.path.lexists(temp):os.unlink(temp)

def backup_dir(run):
    if not re.fullmatch(r"[0-9]{9,20}",run):fail("Unsafe GitHub run ID")
    return HOME/(".mpw-legal-one-line-"+run)

def install(run):
    batch=prepare() # preflight all files BEFORE any write
    recovery=backup_dir(run)
    if recovery.exists() or recovery.is_symlink():fail("Backup run already exists")
    recovery.mkdir(mode=0o700)
    manifest=[]
    for idx,(p,before,after,mode) in enumerate(batch):
        backup=recovery/("%02d.bak"%idx)
        with backup.open("xb") as f:
            os.fchmod(f.fileno(),0o600);f.write(before);f.flush();os.fsync(f.fileno())
        manifest.append({"path":str(p),"before":sha(before),"after":sha(after),
                         "mode":mode,"backup":backup.name})
    with (recovery/"manifest.json").open("x") as f:
        os.fchmod(f.fileno(),0o600);json.dump(manifest,f);f.flush();os.fsync(f.fileno())
    modified=[]
    try:
        for p,before,after,mode in batch:
            if sha(p.read_bytes())!=sha(before):fail("Concurrent site edit: "+str(p))
            atomic(p,after,mode)
            modified.append((p,before,after,mode))
            if sha(p.read_bytes())!=sha(after):fail("Write checksum error: "+str(p))
    except BaseException:
        for p,before,after,mode in reversed(modified):
            if sha(p.read_bytes())==sha(after):atomic(p,before,mode)
        (recovery/"FAILED").write_text("Auto-recovery attempted")
        raise
    (recovery/"INSTALLED").write_text("verified",encoding="utf-8")
    print("MPW_FOOTER_SINGLE_LINE_INSTALLED="+str(len(modified))+" FILES=20 RESTART=false BACKUP="+str(recovery))

def refresh_app(run):
    """Signal only MojPlayWin's Passenger app to reload its cached Django templates.

    No source bytes, routing, site assets or other application folders change.
    """
    before_guard()
    recovery=backup_dir(run)
    if not recovery.is_dir() or not (recovery/"INSTALLED").is_file():
        fail("Cannot reload without completed, backed-up footer install")
    records=json.loads((recovery/"manifest.json").read_text("utf-8"))
    if len(records)!=20 or any(sha(Path(row["path"]).read_bytes())!=row["after"] for row in records):
        fail("Site changed after install; refusing application reload")
    # This virtual host explicitly declares PassengerAppRoot as ROOT, and
    # Passenger's supported restart signal is ROOT/tmp/restart.txt.
    ht=HT.read_text("utf-8",errors="replace")
    if "PassengerAppRoot /home/zomorod2/mojplaywin.com" not in ht or "PassengerStartupFile passenger_wsgi.py" not in ht:
        fail("PassengerAppRoot changed since read-only audit")
    signal=ROOT/"tmp/restart.txt"
    if not signal.parent.is_dir() or signal.parent.is_symlink() or not signal.is_file() or signal.is_symlink():
        fail("Passenger restart signal path not safe")
    digest=sha(signal.read_bytes())
    os.utime(signal,None)
    if sha(signal.read_bytes())!=digest:fail("Passenger restart marker bytes changed")
    print("MPW_PASSENGER_ROOT_TEMPLATE_RESTART=PASS",flush=True)

def rollback(run):
    before_guard()
    recovery=backup_dir(run)
    if not recovery.is_dir() or recovery.is_symlink():fail("Invalid backup directory")
    manifest=json.loads((recovery/"manifest.json").read_text("utf-8"))
    if len(manifest)!=20 or {x["path"] for x in manifest}!={str(p) for p in targets()}:
        fail("Recovery targets unexpected")
    for row in manifest:
        p=Path(row["path"]);backup=(recovery/row["backup"]).read_bytes()
        if sha(backup)!=row["before"] or sha(p.read_bytes())!=row["after"]:
            fail("Concurrent file changed: refusing rollback")
    for row in reversed(manifest):
        p=Path(row["path"])
        atomic(p,(recovery/row["backup"]).read_bytes(),row["mode"])
    # After exact file restoration ask only the configured MojPlayWin
    # PassengerAppRoot to reload its Django template cache.
    ht=HT.read_text("utf-8",errors="replace")
    if "PassengerAppRoot /home/zomorod2/mojplaywin.com" not in ht:
        fail("Rollback Passenger root changed")
    signal=ROOT/"tmp/restart.txt"
    if not signal.is_file() or signal.is_symlink() or signal.parent.is_symlink():
        fail("Rollback Passenger restart signal missing")
    digest=sha(signal.read_bytes())
    os.utime(signal,None)
    if sha(signal.read_bytes())!=digest:fail("Rollback changed restart signal content")
    print("MPW_FOOTER_SINGLE_LINE_ROLLED_BACK=20 PASSENGER_RESTART_SIGNALED=true")

def selftest():
    a='<footer class="mpw-footer"><div>©</div><div><span>© MojPlayWin</span><a href="/privacy/">Privacy</a></div><span class="mpw-founder-footer-final" style="color:gold">Mojtaba Roozegar</span></footer>'
    b=patch(a)
    assert b.count(DISPLAY)==1 and "mpw-founder-footer-final" not in b
    assert "Privacy</a>" in b and "<span>© MojPlayWin</span>" not in b
    c='<footer class="mw-site-footer"><nav>MojPlayWin</nav><div class="mpx-bottom-bar"><span>© MojPlayWin</span><span>Built for research</span><span class="mpw-copyright-founder">Mojtaba Roozegar</span></div></footer>'
    d=patch(c)
    assert d.count(DISPLAY)==1 and "Built for research" not in d
    for value in (b,d):
        assert "Mojtaba Roozegar</span>" not in value
        assert 'data-mpw-founder-source="Mojtaba Roozegar"' in value
        try:patch(value);raise AssertionError("Double patch permitted")
        except RuntimeError:pass
    print("MPW_FOOTER_SINGLE_LINE_SELFTEST=PASS")

if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":selftest()
    elif len(sys.argv)==2 and sys.argv[1]=="audit":
        batch=prepare()
        print("MPW_FOOTER_SINGLE_LINE_READY="+str(len(batch)))
    elif len(sys.argv)==3 and sys.argv[1]=="install":install(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="refresh":refresh_app(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:fail("Usage: selftest|audit|install RUN_ID|refresh RUN_ID|rollback RUN_ID")
