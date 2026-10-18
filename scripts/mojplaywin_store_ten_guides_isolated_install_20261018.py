#!/usr/bin/env python3
"""MojPlayWin ONLY: isolated active store template + new 10-guide fragment.

Fail-closed two-file additive publication into Saeit-staging; NEVER writes
the separate Saeit app (Zomorod Melal), root web .htaccess, database, payment,
store views, Passenger restart, or sibling subsite content.
"""
from pathlib import Path
import hashlib,json,os,re,stat,sys,tempfile

APP=Path("/home/zomorod2/Saeit-staging")
DIR=APP/"core/templates/mojplaywin"
STORE=DIR/"store.html"
NEW=DIR/"store_ten_buyer_guides_20261018.html"
ORIGINAL_SHA="8e0df19a94921d746d14fa5a468e1ba8e3184d56aaa01c083c9176160590157d"
INC='{% include "mojplaywin/store_ten_buyer_guides_20261018.html" %}'
MARKER=b'id="mpw-store-ten-guides"'
HOME=Path("/home/zomorod2")
def sha(x):return hashlib.sha256(x).hexdigest()
def fail(s):raise RuntimeError(s)
def run_guard(value):
    if not re.fullmatch(r"[0-9]{9,20}",value):fail("Invalid run ID")
    return value
def stage(run):return HOME/(".mpw-store-guides-stage-"+run_guard(run))
def backup(run):return HOME/(".mpw-store-guides-backup-"+run_guard(run))
def atomic(path,data,mode):
    if path.is_symlink():fail("Symlink target")
    fd,p=tempfile.mkstemp(dir=path.parent,prefix=".mpw-store-guides-")
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(p,path)
    finally:
        if os.path.exists(p):os.unlink(p)
def check():
    if not APP.is_dir() or APP.is_symlink() or not DIR.is_dir() or DIR.is_symlink():
        fail("Active MojPlayWin template root is invalid")
    if not STORE.is_file() or STORE.is_symlink():fail("Existing MojPlayWin store template unsafe")
    if sha(STORE.read_bytes())!=ORIGINAL_SHA:fail("Live store template no longer matches read-only verified SHA")
    if NEW.exists() or NEW.is_symlink():fail("Guide fragment already exists: no overwrite")
    if not (APP/"config/settings.py").is_file():fail("Staging Django environment unexpected")
    active=(HOME/"mojplaywin.com/passenger_wsgi.py").read_text("utf8","replace")
    if "APP='/home/zomorod2/Saeit-staging'" not in active:
        fail("Passenger no longer uses the verified isolated MojPlayWin app")
def inspect_source(raw,partial):
    content=raw.decode("utf8")
    fragments=partial.decode("utf8")
    if content.count(INC)!=1:fail("Expected exactly one additive include")
    original=content.replace(INC,"",1).encode("utf8")
    if sha(original)!=ORIGINAL_SHA:fail("All previous store template bytes were not preserved")
    if content.count("{% for product in products %}")!=1 or "id=\"catalog\"" not in content:
        fail("Existing catalog loop or anchor damaged")
    if '<form' in fragments.lower() or '{% csrf_token %}' in fragments or '<script' in fragments.lower():
        fail("Fragment must not create any new form, script, or payment workflow")
    if fragments.count('class="mpw-store-guide"')!=10 or fragments.count(".webp")!=10:
        fail("Expected exactly ten light illustrated buyer guides")
    if fragments.count(MARKER.decode())!=1:
        fail("Missing unique section marker")
    for i in range(1,11):
        image="/design-preview-20261017/mpw-ten-editorials-20261018/images/market-%02d.webp"%i
        if fragments.count(image)!=1:fail("Missing or repeated original compact image: "+image)
    if len(partial)>24000 or len(partial)<6500:fail("Unexpected guide fragment size")
    if len(raw)>4000:fail("Store template unexpectedly large")
def install(run):
    run=run_guard(run)
    check()
    st=stage(run);bk=backup(run)
    if not st.is_dir() or st.is_symlink() or bk.exists() or bk.is_symlink():
        fail("Private stage missing or backup collision")
    src=st/"store.html"
    frag=st/"store_ten_buyer_guides_20261018.html"
    if not src.is_file() or not frag.is_file() or src.is_symlink() or frag.is_symlink():
        fail("Private source files missing")
    old=STORE.read_bytes();new=src.read_bytes();content=frag.read_bytes()
    inspect_source(new,content)
    bk.mkdir(mode=0o700)
    with open(bk/"store.original.html","xb") as f:
        os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
    info={"run":run,"old_sha":sha(old),"new_sha":sha(new),"partial_sha":sha(content),
          "store_path":str(STORE),"partial_path":str(NEW)}
    (bk/"manifest.json").write_text(json.dumps(info),"utf8")
    os.chmod(bk/"manifest.json",0o600)
    mode=stat.S_IMODE(STORE.stat().st_mode)
    try:
        atomic(NEW,content,0o644)
        if sha(NEW.read_bytes())!=info["partial_sha"]:fail("Fragment SHA mismatch")
        if sha(STORE.read_bytes())!=ORIGINAL_SHA:fail("Concurrent template edit")
        atomic(STORE,new,mode)
        if sha(STORE.read_bytes())!=info["new_sha"]:fail("Store template SHA mismatch")
    except BaseException:
        if STORE.is_file() and sha(STORE.read_bytes())==info["new_sha"]:
            atomic(STORE,old,mode)
        if NEW.is_file() and sha(NEW.read_bytes())==info["partial_sha"]:
            NEW.unlink()
        (bk/"INSTALL_FAILED").write_text("true\n","utf8")
        raise
    print(json.dumps({"status":"MPW_STORE_GUIDES_TEMPLATE_INSTALLED","previous_sha":sha(old),
     "new_sha":sha(new),"partial_sha":sha(content),"new_illustrated_guides":10,
     "existing_catalog_and_product_loop_preserved":True,"staging_app_only":True,
     "django_view_or_database_modified":False,"passenger_restarted":False,
     "backup_path":str(bk)}))
def rollback(run):
    run=run_guard(run)
    bk=backup(run)
    if not bk.is_dir() or bk.is_symlink():fail("Private backup missing")
    info=json.loads((bk/"manifest.json").read_text("utf8"))
    old=(bk/"store.original.html").read_bytes()
    if sha(old)!=ORIGINAL_SHA or info["old_sha"]!=ORIGINAL_SHA:
        fail("Backup integrity failure")
    actual=sha(STORE.read_bytes())
    if actual==info["new_sha"]:
        atomic(STORE,old,stat.S_IMODE(STORE.stat().st_mode))
    elif actual!=ORIGINAL_SHA:
        fail("Concurrent site edit detected; refuse overwrite")
    if NEW.is_file() and not NEW.is_symlink() and sha(NEW.read_bytes())==info["partial_sha"]:
        NEW.unlink()
    if sha(STORE.read_bytes())!=ORIGINAL_SHA:fail("Rollback verification failed")
    print(json.dumps({"status":"MPW_STORE_GUIDES_ROLLED_BACK","previous_sha":ORIGINAL_SHA,
                      "partial_removed":not NEW.exists()}))
if __name__=="__main__":
    if len(sys.argv)!=3:fail("Usage install|rollback RUN_ID")
    if sys.argv[1]=="install":install(sys.argv[2])
    elif sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:fail("Invalid action")
