#!/usr/bin/env python3
"""Install only two *new* MojPlayWin tools under one new isolated URL path.
Atomic directory rename, exact-owner preflight, evidence receipt, bounded rollback.
No edits to Django, Passenger, PHP, rewrites, existing editorial, catalog or assets.
"""
import fcntl, hashlib, json, os, pwd, re, shutil, stat, sys
from pathlib import Path

HOME=Path("/home/zomorod2")
SITE=HOME/"mojplaywin.com"
PARENT=SITE/"mpw-editorial"/"nextwave"
TARGET=PARENT/"20261023"
PRIVATE=HOME/".private_mpw_nextwave_20261023"
RELEASE="NEXTWAVE-20261023-01"
FILES=("index.html","release.json","frame-budget-lab/index.html","orbit-switch/index.html")
PHP=SITE/"design-preview-20261017"/"_mpw_dynamic_main_shell_20261019.php"
HTACCESS=SITE/".htaccess"
PHP_SHA="dd2bdbca509560e640fe7c67bb60443bf6cc2663fcac46af1c90b1d62ab834cc"
HTACCESS_SHA="6d06dc358b118ca59843941cd79c627eb4792a3584b0d11b4de7ed49b8552b63"
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def owner(p):
    return p.exists() and not p.is_symlink() and p.stat().st_uid==os.getuid()
def check_env():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":
        raise RuntimeError("Wrong cPanel account")
    for p in (HOME,SITE,SITE/"mpw-editorial",HTACCESS,PHP):
        if not owner(p):raise RuntimeError("Missing or unexpected path owner: "+str(p))
    if sha(HTACCESS)!=HTACCESS_SHA or sha(PHP)!=PHP_SHA:
        raise RuntimeError("Production routing or PHP shell changed; manual reconciliation required")
def scan_files(root):
    if not owner(root) or not root.is_dir():raise RuntimeError("Unknown staged/target directory")
    found=[]
    for base,dirs,files in os.walk(root,followlinks=False):
        here=Path(base)
        if here.is_symlink() or not owner(here):raise RuntimeError("Invalid directory owner")
        for d in dirs:
            p=here/d
            if p.is_symlink() or not owner(p):raise RuntimeError("Symlink or wrong directory ownership")
        for name in files:
            p=here/name
            if p.is_symlink() or not owner(p) or not p.is_file():raise RuntimeError("Invalid release file")
            found.append(str(p.relative_to(root)))
    if sorted(found)!=sorted(FILES):raise RuntimeError("Expected exactly four original release files; found "+repr(found))
    out={}
    for rel in FILES:
        path=root/rel
        if not (100<path.stat().st_size<75000):raise RuntimeError("Unexpected content size "+rel)
        b=path.read_bytes()
        if b'\0' in b or b'<script src=' in b.lower() or b'http-equiv="refresh"' in b.lower():
            raise RuntimeError("Unknown executable dependencies")
        out[rel]=sha(path)
    m=json.loads((root/"release.json").read_text())
    if m.get("release_id")!=RELEASE or sorted(x.get("id") for x in m.get("items",[]))!=["frame-budget-lab","orbit-switch"] or m.get("no_previous_release_reused") is not True:
        raise RuntimeError("Unrecognized release manifest")
    if "FRAME_BUDGET_FUNCTIONAL_TEST_PASS" not in (root/"frame-budget-lab/index.html").read_text() or "ORBIT_SWITCH_FUNCTIONAL_TEST_PASS" not in (root/"orbit-switch/index.html").read_text():
        raise RuntimeError("Expected browser selftest marker missing")
    if 'NEXTWAVE-20261023-01' not in (root/"index.html").read_text():
        raise RuntimeError("Version marker missing")
    return out
def prepared(run):
    if not re.fullmatch(r"[0-9]{8,20}",run):raise RuntimeError("Invalid run")
    if not owner(PRIVATE) or not PRIVATE.is_dir():raise RuntimeError("Private stage directory missing/unsafe")
    if PRIVATE.stat().st_dev!=SITE.stat().st_dev:raise RuntimeError("Non-atomic filesystem")
    return PRIVATE/("staging-"+run)/"20261023",PRIVATE/("receipt-"+run+".json")
def operate(mode,run,commit):
    if not re.fullmatch(r"[a-f0-9]{40}",commit):raise RuntimeError("Unrecognized Git SHA")
    check_env()
    stage,receipt=prepared(run)
    lock=PRIVATE/"deploy.lock"
    with open(lock,"a+") as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        if mode=="install":
            if TARGET.exists() or TARGET.is_symlink():raise RuntimeError("Non-overwrite policy: release already exists")
            if receipt.exists() or receipt.is_symlink():raise RuntimeError("Run receipt exists")
            hashes=scan_files(stage)
            if PARENT.exists() or PARENT.is_symlink():
                if not owner(PARENT) or not PARENT.is_dir():raise RuntimeError("Invalid release parent owner")
            else:
                PARENT.mkdir(mode=0o755)
            if not owner(PARENT):raise RuntimeError("Parent owner changed")
            for root,dirs,files in os.walk(stage):
                os.chmod(root,0o755)
                for n in files:os.chmod(Path(root)/n,0o644)
            receipt_info={"release_id":RELEASE,"run":run,"commit":commit,"target":str(TARGET),"files_sha256":hashes,"install_state":"candidate"}
            with open(receipt,"x") as f:
                json.dump(receipt_info,f,sort_keys=True);f.flush();os.fsync(f.fileno())
            if TARGET.exists() or TARGET.is_symlink():raise RuntimeError("Concurrent release collision")
            os.replace(stage,TARGET)
            verified=scan_files(TARGET)
            if verified!=hashes:raise RuntimeError("Post-swap integrity mismatch")
            receipt_info["install_state"]="live_directory_confirmed"
            temp=PRIVATE/("receipt-final-"+run+".json")
            with open(temp,"x") as f:
                json.dump(receipt_info,f,sort_keys=True);f.flush();os.fsync(f.fileno())
            os.replace(temp,receipt)
            print("NEXTWAVE_ATOMIC_DEPLOY",json.dumps(receipt_info,sort_keys=True))
        elif mode=="rollback":
            if not receipt.is_file() or receipt.is_symlink():
                print("NEXTWAVE_NOT_INSTALLED_NO_ROLLBACK");return
            info=json.loads(receipt.read_text())
            if info.get("release_id")!=RELEASE or info.get("run")!=run or info.get("commit")!=commit or info.get("target")!=str(TARGET):
                raise RuntimeError("Rollback provenance does not match")
            if not TARGET.exists():
                print("NEXTWAVE_NO_PUBLIC_DIR_NO_ROLLBACK");return
            actual=scan_files(TARGET)
            if actual!=info.get("files_sha256"):
                raise RuntimeError("Concurrent user edits detected; refuse destructive rollback")
            shutil.rmtree(TARGET)
            print("NEXTWAVE_EXACT_ROLLBACK",json.dumps({"run":run,"removed":str(TARGET),"protected_unchanged":True}))
        else:raise RuntimeError("No such operation")
if __name__=="__main__":
    if len(sys.argv)!=4:raise SystemExit("install|rollback RUN_ID GIT_SHA")
    operate(sys.argv[1],sys.argv[2],sys.argv[3])
