#!/usr/bin/env python3
"""Narrow cPanel repair for session cookie path in MojPlayWin inquiry form."""
import hashlib,json,os,re,shutil,sys
from pathlib import Path

ROOT=Path("/home/zomorod2/mojplaywin.com/mpw-editorial")
HOME=Path("/home/zomorod2")
TARGET=ROOT/"revenue"
MARKER=TARGET/".mpw-revenue-release.json"
FORM=TARGET/"inquiry.php"
def fail(s):raise RuntimeError(s)
def sha(b):return hashlib.sha256(b).hexdigest()
def paths(run):
    if not re.fullmatch(r"[0-9]{8,20}",run):fail("Invalid run id")
    return HOME/(".mpw-inquiry-cookie-backup-"+run),TARGET/(".inquiry-cookie-stage-"+run)
def guard():
    if ROOT.is_symlink() or not ROOT.is_dir() or ROOT.resolve()!=ROOT or not (ROOT.parent/".htaccess").is_file() or TARGET.is_symlink() or not TARGET.is_dir():fail("Unsafe site root")
    if any(p.is_symlink() for p in (MARKER,FORM)):fail("Managed form symlink")
    if not (MARKER.is_file() and FORM.is_file()):fail("Missing managed source")
    doc=json.loads(MARKER.read_text("utf-8"))
    if len(doc.get("sha256",{}))!=20 or doc.get("run")!="40274072290":fail("Unexpected revenue ownership marker")
    if doc.get("cookie_fix_run"):fail("Another cookie repair already completed")
    if sha(FORM.read_bytes())!=doc["sha256"]["inquiry.php"]:fail("Form changed outside release control")
    return doc
def publish(run):
    doc=guard()
    backup,stage=paths(run)
    if backup.exists() or backup.is_symlink() or stage.exists() or stage.is_symlink():fail("Release collision")
    old=FORM.read_bytes()
    if b"'path'=>'/mpw-editorial/revenue/index.html'" not in old:fail("Observed session path bug no longer exists")
    new=sys.stdin.buffer.read(80000)
    if not new or len(new)>50000:fail("Unexpected source size")
    if b"'path'=>'/mpw-editorial/revenue' . '/'" not in new or b"'path'=>'/mpw-editorial/revenue/'" in new:fail("Fixed cookie syntax not present")
    if b"store_inquiry" not in new or b"openssl_encrypt" not in new:fail("Submission data handling not preserved")
    if sha(old)==sha(new):fail("Unchanged form")
    backup.mkdir(mode=0o700)
    (backup/"inquiry.php").write_bytes(old)
    shutil.copy2(MARKER,backup/".mpw-revenue-release.json")
    if sha((backup/"inquiry.php").read_bytes())!=sha(old):fail("Original backup corrupt")
    stage.write_bytes(new)
    stage.chmod(0o644)
    nextdoc=json.loads(json.dumps(doc))
    nextdoc["sha256"]["inquiry.php"]=sha(new)
    nextdoc["cookie_fix_run"]=run
    marker_temp=TARGET/(".cookie-marker-"+run)
    replaced=False
    try:
        if sha(FORM.read_bytes())!=sha(old):fail("Concurrent alteration")
        os.replace(stage,FORM)
        replaced=True
        if sha(FORM.read_bytes())!=sha(new):fail("Form integrity mismatch")
        marker_temp.write_text(json.dumps(nextdoc,sort_keys=True)+"\n",encoding="utf-8")
        os.replace(marker_temp,MARKER)
        print("MPW_SESSION_COOKIE_PATH_REPAIRED="+json.dumps({"run":run,"owned_form_sha256_verified":True,"previous_private_backup":True,"customer_orders_modified":False,"payment_modified":False}))
    except BaseException:
        if replaced and FORM.is_file() and sha(FORM.read_bytes())==sha(new):
            os.replace(backup/"inquiry.php",FORM)
        raise
    finally:
        for p in (stage,marker_temp):
            if p.exists() and not p.is_symlink():p.unlink()
def rollback(run):
    if not re.fullmatch(r"[0-9]{8,20}",run):fail("Invalid rollback run")
    backup,stage=paths(run)
    if not backup.is_dir() or backup.is_symlink():fail("Missing backup")
    doc=json.loads(MARKER.read_text("utf-8"))
    if doc.get("cookie_fix_run")!=run:fail("Refuse rollback of later repair")
    newsha=doc["sha256"]["inquiry.php"]
    if sha(FORM.read_bytes())!=newsha:fail("Concurrent modifications block rollback")
    old=json.loads((backup/".mpw-revenue-release.json").read_text("utf-8"))
    if sha((backup/"inquiry.php").read_bytes())!=old["sha256"]["inquiry.php"]:fail("Original damaged")
    os.replace(backup/"inquiry.php",FORM)
    os.replace(backup/".mpw-revenue-release.json",MARKER)
    print("MPW_SESSION_COOKIE_FIX_ROLLED_BACK=VERIFIED")
if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1] not in ("publish","rollback"):raise SystemExit("publish|rollback RUN_ID")
    (publish if sys.argv[1]=="publish" else rollback)(sys.argv[2])
