#!/usr/bin/env python3
"""Atomic, checksum-pinned replacement of only the current main-domain dynamic PHP shell.

Changes to non-contact pages are rejected by an exact preimage check and
independent public route smoke tests. This NEVER edits .htaccess or Django.
"""
from __future__ import annotations
import hashlib,json,os,re,stat,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path("/home/zomorod2/mojplaywin.com")
HOME=ROOT.parent
TARGET=ROOT/"design-preview-20261017/_mpw_dynamic_main_shell_20261019.php"
HT=ROOT/".htaccess"
KEY="MPW_MAIN_19_EXACT_DYNAMIC_SHELL_20261019_BEGIN"
NEWKEY="mpw-contact-safe-business-20261019"
def sha(value):return hashlib.sha256(value).hexdigest()
def fail(reason):raise RuntimeError(reason)
def paths(run):
    if not re.fullmatch(r"[0-9]{9,20}",run):fail("Invalid GitHub run id")
    return (HOME/(".mpw-contact-shell-stage-"+run+".php"),
            HOME/(".mpw-contact-shell-backup-"+run+".php"),
            HOME/(".mpw-contact-shell-manifest-"+run+".json"))
def guard():
    if ROOT.resolve()!=ROOT or ROOT.is_symlink() or not ROOT.is_dir():fail("Unexpected site root")
    if not HT.is_file() or HT.is_symlink() or not TARGET.is_file() or TARGET.is_symlink():
        fail("Protected route/target missing")
    if TARGET.parent.is_symlink():fail("Symlinked script directory refused")
    lines=HT.read_text("utf-8",errors="replace")
    if KEY not in lines or "_mpw_dynamic_main_shell_20261019.php" not in lines:
        fail("Current exact GET-only route ownership changed")
    if "contact" not in lines:fail("Contact route missing")
def atomically_write(dest,data,mode):
    if dest.is_symlink():fail("Atomic write symlink target")
    fd,tmp=tempfile.mkstemp(dir=dest.parent,prefix=".mpw-contact-atomic-")
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,dest)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)
def check_hash(raw,expected,name):
    if not re.fullmatch("[0-9a-f]{64}",expected):fail("Invalid "+name+" sha256")
    if sha(raw)!=expected:fail(name+" changed or checksum mismatch")
def php_check(candidate):
    for cmd in (["php","-l",str(candidate)],["php",str(candidate),"selftest"]):
        check=subprocess.run(cmd,capture_output=True,text=True,timeout=25,check=False)
        if check.returncode!=0:fail("PHP lint or selftest failed: "+check.stderr[-800:])
        if cmd[-1]=="selftest" and "MPW_MAIN_ONLY_BRIDGE_SELFTEST=PASS" not in check.stdout:
            fail("PHP selftest did not confirm safe shared routes")
def install(run,expected_old,expected_new):
    guard()
    stage,backup,manifest=paths(run)
    if not stage.is_file() or stage.is_symlink() or backup.exists() or manifest.exists():
        fail("Private stage missing or recovery file already exists")
    before=TARGET.read_bytes();new=stage.read_bytes()
    check_hash(before,expected_old,"Original PHP")
    check_hash(new,expected_new,"Approved new PHP")
    if new.count(b"mpw-contact-safe-business-20261019")!=1:
        # Marker is one CSS id in source.
        fail("Unique contact CSS marker missing")
    if before.count(b"function transformMain(")!=1 or new.count(b"function transformMain(")!=1:
        fail("Main transformation signature drifted")
    if not b"'contact' => '/contact/'" in before or not b"'contact' => '/contact/'" in new:
        fail("Contact route unexpectedly changed")
    php_check(stage)
    with backup.open("xb") as f:
        os.fchmod(f.fileno(),0o600);f.write(before);f.flush();os.fsync(f.fileno())
    state={"run":run,"old_sha":sha(before),"new_sha":sha(new),"path":str(TARGET)}
    with manifest.open("x") as f:
        os.fchmod(f.fileno(),0o600);json.dump(state,f);f.flush();os.fsync(f.fileno())
    if TARGET.read_bytes()!=before:fail("Concurrent PHP modification before publish")
    mode=stat.S_IMODE(TARGET.stat().st_mode)
    try:
        atomically_write(TARGET,new,mode)
        if sha(TARGET.read_bytes())!=state["new_sha"]:fail("Postwrite PHP checksum mismatch")
    except BaseException:
        if sha(TARGET.read_bytes())==state["new_sha"]:
            atomically_write(TARGET,before,mode)
        raise
    print("MPW_CONTACT_BUSINESS_PUBLISH="+json.dumps(state))
def rollback(run):
    guard()
    _,backup,manifest=paths(run)
    if not manifest.is_file() or manifest.is_symlink() or not backup.is_file() or backup.is_symlink():
        fail("Backup/manifest not found")
    info=json.loads(manifest.read_text("utf-8"))
    original=backup.read_bytes()
    if info["run"]!=run or info["path"]!=str(TARGET) or sha(original)!=info["old_sha"]:
        fail("Backup integrity not verified")
    if sha(TARGET.read_bytes())!=info["new_sha"]:
        fail("Refuse rollback over a newer concurrent modification")
    atomically_write(TARGET,original,stat.S_IMODE(TARGET.stat().st_mode))
    if sha(TARGET.read_bytes())!=info["old_sha"]:fail("Rollback verification failed")
    print("MPW_CONTACT_BUSINESS_ROLLBACK=VERIFIED")
if __name__=="__main__":
    if len(sys.argv)==5 and sys.argv[1]=="install":
        install(sys.argv[2],sys.argv[3],sys.argv[4])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":
        rollback(sys.argv[2])
    else:fail("install RUN OLD_SHA NEW_SHA | rollback RUN")
