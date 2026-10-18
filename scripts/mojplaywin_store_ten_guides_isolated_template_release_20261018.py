#!/usr/bin/env python3
"""Exact additive store-guide template installation in the isolated MojPlayWin template.

Safety:
- Active WSGI root pinned to /home/zomorod2/Saeit-staging.
- Only one existing store.html and one newly created store guide partial are touched.
- No shared code, static files, DB, payment/order state, domain routing or Passenger restart.
- Fail-closed SHA gate and byte-exact private rollback.
"""
import hashlib,json,os,re,stat,sys,tempfile
from pathlib import Path

HOME=Path("/home/zomorod2")
APP=HOME/"Saeit-staging"
TEMPLATES=APP/"core/templates/mojplaywin"
STORE=TEMPLATES/"store.html"
GUIDES=TEMPLATES/"store_ten_buyer_guides_20261018.html"
WSGI=HOME/"mojplaywin.com/passenger_wsgi.py"
EXPECTED_STORE_SHA="8e0df19a94921d746d14fa5a468e1ba8e3184d56aaa01c083c9176160590157d"
INCLUDE='{% include "mojplaywin/store_ten_buyer_guides_20261018.html" %}'
ORIGINAL_TAIL='</p></div>{% include "mojplaywin/footer.html" %}{% endblock %}'
PATCHED_TAIL='</p>'+INCLUDE+'</div>{% include "mojplaywin/footer.html" %}{% endblock %}'
IMAGE_BASE="/design-preview-20261017/mpw-ten-editorials-20261018/images/market-"
DATA_MARKER='id="mpw-store-ten-guides"'

def digest(data):return hashlib.sha256(data).hexdigest()
def fail(message):raise RuntimeError(message)
def verify_run(runid):
    if not re.fullmatch(r"[0-9]{9,20}",runid):fail("Unsafe run ID")
    return runid
def stage_path(runid):return HOME/(".mpw-store-guides-"+verify_run(runid)+".stage.html")
def backup_dir(runid):return HOME/(".mpw-store-guides-"+verify_run(runid)+".rollback")
def safe_write(path,blob,mode=0o644):
    if path.is_symlink():fail("Refuse symlink target")
    fd,tmp=tempfile.mkstemp(prefix=".mpw-store-guides-",dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as out:
            out.write(blob);out.flush();os.fsync(out.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def check():
    if not APP.is_dir() or APP.is_symlink() or not (APP/"manage.py").is_file():
        fail("Unexpected active Django application root")
    if not WSGI.is_file() or WSGI.is_symlink() or "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf-8","replace"):
        fail("Passenger no longer points at pinned active app; refusal")
    if not TEMPLATES.is_dir() or TEMPLATES.is_symlink():fail("MojPlayWin templates directory unsafe")
    if not STORE.is_file() or STORE.is_symlink() or digest(STORE.read_bytes())!=EXPECTED_STORE_SHA:
        fail("Existing live store template differs from read-only preflight")
    if GUIDES.exists() or GUIDES.is_symlink():fail("Guide partial already exists; refuse overwrite")
def construct(store,guide):
    before=store.decode("utf-8")
    newcontent=guide.decode("utf-8")
    if len(guide)<8000 or len(guide)>20000:fail("Guide editorial file size outside expected bounds")
    if before.count(ORIGINAL_TAIL)!=1 or INCLUDE in before:fail("Old store insertion anchor unexpected")
    if newcontent.count(DATA_MARKER)!=1 or newcontent.count('class="mpw-store-guide"')!=10:
        fail("Not exactly 10 illustrated guide cards")
    if newcontent.count('loading="lazy"')!=10:fail("Ten lazy-loaded images required")
    for n in range(1,11):
        if newcontent.count(IMAGE_BASE+f"{n:02d}.webp")!=1:
            fail("Missing or duplicated tiny WebP: "+str(n))
    if "<form" in newcontent.lower() or "<script" in newcontent.lower() or "{% extends" in newcontent:
        fail("Prohibited form/script/inheritance in purely editorial guide partial")
    if 'Digital Store' not in before or 'INITIAL COLLECTION' not in before or '{{ product.url }}' not in before:
        fail("Original dynamic catalog markers absent")
    amended=before.replace(ORIGINAL_TAIL,PATCHED_TAIL,1)
    if amended.replace(PATCHED_TAIL,ORIGINAL_TAIL,1)!=before:fail("Patch not byte-reversible")
    if amended.count(INCLUDE)!=1:fail("Duplicate include")
    if "{{ products|length }}" not in amended or "{{ product.title }}" not in amended or "{{ product.url }}" not in amended:
        fail("Live product template fields changed")
    return amended.encode("utf-8")
def install(runid,expected_sha):
    runid=verify_run(runid)
    if not re.fullmatch(r"[a-f0-9]{64}",expected_sha):fail("Invalid editorial SHA")
    check()
    staged=stage_path(runid)
    back=backup_dir(runid)
    if not staged.is_file() or staged.is_symlink():fail("Staged guide absent")
    if back.exists() or back.is_symlink():fail("Backup directory already exists")
    guide=staged.read_bytes()
    if digest(guide)!=expected_sha:fail("Editorial file SHA mismatch")
    previous=STORE.read_bytes()
    rewritten=construct(previous,guide)
    back.mkdir(mode=0o700)
    (back/"original-store.html").write_bytes(previous)
    os.chmod(back/"original-store.html",0o600)
    meta={"runid":runid,"store_before":digest(previous),"store_after":digest(rewritten),
          "guide_sha":expected_sha,"guide_bytes":len(guide),
          "new_guides":10,"original_catalog_preserved":True}
    (back/"manifest.json").write_text(json.dumps(meta,sort_keys=True),encoding="utf-8")
    os.chmod(back/"manifest.json",0o600)
    try:
        safe_write(GUIDES,guide,0o644)
        if digest(GUIDES.read_bytes())!=expected_sha:fail("Guide partial not identical to staged file")
        safe_write(STORE,rewritten,stat.S_IMODE(STORE.stat().st_mode))
        if digest(STORE.read_bytes())!=meta["store_after"]:fail("Store template write not verified")
    except BaseException:
        if STORE.is_file() and not STORE.is_symlink() and digest(STORE.read_bytes())==meta["store_after"]:
            safe_write(STORE,previous,stat.S_IMODE(STORE.stat().st_mode))
        if GUIDES.is_file() and not GUIDES.is_symlink() and digest(GUIDES.read_bytes())==expected_sha:
            GUIDES.unlink()
        (back/"FAILED").write_text("yes")
        raise
    print(json.dumps({"result":"STORE_TEN_GUIDES_TEMPLATE_INSTALLED",
        "original_catalog_preserved":True,"store_before":meta["store_before"],
        "store_after":meta["store_after"],"guide_sha":expected_sha,"guides":10,
        "passenger_restarted":False,"payments_files_untouched":True,
        "backup_ready":True}))
def rollback(runid):
    back=backup_dir(verify_run(runid))
    if not back.is_dir() or back.is_symlink():fail("No safe backup")
    original=(back/"original-store.html").read_bytes()
    meta=json.loads((back/"manifest.json").read_text())
    if digest(original)!=meta["store_before"] or meta["store_before"]!=EXPECTED_STORE_SHA:
        fail("Prior template source changed")
    if not STORE.is_file() or STORE.is_symlink():fail("Unsafe store rollback target")
    current=digest(STORE.read_bytes())
    if current==meta["store_after"]:
        safe_write(STORE,original,stat.S_IMODE(STORE.stat().st_mode))
    elif current!=meta["store_before"]:
        fail("Concurrent template change; do not overwrite")
    if GUIDES.is_file() and not GUIDES.is_symlink() and digest(GUIDES.read_bytes())==meta["guide_sha"]:
        GUIDES.unlink()
    if digest(STORE.read_bytes())!=EXPECTED_STORE_SHA:fail("Store rollback checksum incorrect")
    print(json.dumps({"result":"STORE_TEN_GUIDES_ROLLED_BACK","live_template_original":True,
          "guide_file_removed":not GUIDES.exists(),"passenger_restarted":False}))
def status(runid):
    back=backup_dir(verify_run(runid))
    meta=json.loads((back/"manifest.json").read_text()) if (back/"manifest.json").is_file() else {}
    print(json.dumps({"result":"STORE_GUIDES_TEMPLATE_STATUS",
        "template_sha":digest(STORE.read_bytes()) if STORE.is_file() and not STORE.is_symlink() else None,
        "guide_sha":digest(GUIDES.read_bytes()) if GUIDES.is_file() and not GUIDES.is_symlink() else None,
        "installed":(STORE.is_file() and digest(STORE.read_bytes())==meta.get("store_after") and GUIDES.is_file()
            and digest(GUIDES.read_bytes())==meta.get("guide_sha"))}))
if __name__=="__main__":
    if len(sys.argv)<3:fail("Usage install|rollback|status RUNID [guide_sha]")
    action,runid=sys.argv[1:3]
    if action=="install" and len(sys.argv)==4:install(runid,sys.argv[3])
    elif action=="rollback" and len(sys.argv)==3:rollback(runid)
    elif action=="status" and len(sys.argv)==3:status(runid)
    else:fail("Invalid operation")
