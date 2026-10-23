#!/usr/bin/env python3
"""Install one new versioned Field Studio publication; fail closed, no overwrites.

Scope: exactly /home/zomorod2/mojplaywin.com/mpw-editorial/field-guides/20261023.
No Django, Passenger, .htaccess, docroot, existing games or cards are modified.
Staged files hashed before a same-filesystem atomic directory rename. Receipt
provides content-addressed rollback only if files remain unchanged.
"""
from pathlib import Path
import fcntl,hashlib,json,os,pwd,re,shutil,stat,sys
HOME=Path("/home/zomorod2")
SITE=HOME/"mojplaywin.com"
PARENT=SITE/"mpw-editorial"/"field-guides"
TARGET=PARENT/"20261023"
PRIVATE=HOME/".private_mpw_fieldguides_20261023"
HTACCESS=SITE/".htaccess"
PASSENGER=SITE/"passenger_wsgi.py"
PHP=SITE/"design-preview-20261017"/"_mpw_dynamic_main_shell_20261019.php"
HTACCESS_SHA="6d06dc358b118ca59843941cd79c627eb4792a3584b0d11b4de7ed49b8552b63"
RELEASE="MPW-FIELDGUIDES-20261023-01"
def digest(b):return hashlib.sha256(b).hexdigest()
def owner(p):return p.exists() and not p.is_symlink() and p.stat().st_uid==os.getuid()
def validate_environment():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("Wrong cPanel account")
    for p in (HOME,SITE,SITE/"mpw-editorial",HTACCESS,PASSENGER,PHP):
        if not owner(p):raise RuntimeError("Protected site ownership/missing: "+str(p))
    if digest(HTACCESS.read_bytes())!=HTACCESS_SHA:raise RuntimeError("Routing safety digest changed")
    if PHP.stat().st_size>150000 or not PHP.is_file():raise RuntimeError("Unexpected PHP route owner")
def scan(root):
    if not owner(root) or not root.is_dir():raise RuntimeError("Untrusted release root")
    paths=[]
    for base,dirs,files in os.walk(root,followlinks=False):
        directory=Path(base)
        if not owner(directory):raise RuntimeError("Untrusted directory or symlink")
        for d in dirs:
            if not owner(directory/d):raise RuntimeError("Untrusted child directory")
        for name in files:
            p=directory/name
            if not owner(p) or not p.is_file():raise RuntimeError("Unknown file owner/symlink")
            paths.append(p.relative_to(root).as_posix())
    manifest=root/"release.json"
    if not manifest.is_file() or manifest.is_symlink():raise RuntimeError("Release manifest missing")
    m=json.loads(manifest.read_text(encoding="utf8"))
    if m.get("release_id")!=RELEASE or m.get("guide_count")!=50 or m.get("stage_count")!=150 or m.get("output_count")!=54:raise RuntimeError("Wrong release or count")
    known=m.get("files_sha256")
    if not isinstance(known,dict) or len(known)!=53 or len(paths)!=54 or set(paths)!=set(known)|{"release.json"}:raise RuntimeError("Release path list mismatch")
    wanted=["index.html","sitemap.xml","prism-relay/index.html"]+[f"guides/{p.parent.name}/index.html" for p in (root/"guides").glob("*/index.html")]
    if len(wanted)!=53 or len(set(wanted))!=53 or set(wanted)!=set(known):raise RuntimeError("Incorrect guides or extra file")
    for rel,expected in known.items():
        p=root/rel
        if not re.fullmatch(r"[a-z0-9][a-z0-9/_-]*\.(?:html|xml)",rel):raise RuntimeError("Invalid release entry path")
        if not re.fullmatch(r"[a-f0-9]{64}",expected):raise RuntimeError("Bad hash syntax")
        if p.stat().st_size<100 or p.stat().st_size>90000:raise RuntimeError("Unexpected document size")
        if digest(p.read_bytes())!=expected:raise RuntimeError("File integrity failure "+rel)
    if "PRISM_RELAY_FUNCTIONAL_TEST_PASS" not in (root/"prism-relay/index.html").read_text():raise RuntimeError("Missing game acceptance script")
    return {"release_id":RELEASE,"file_count":54,"guide_count":50,"files_sha256":known,"root_hash":digest(manifest.read_bytes())}
def operate(action,run_id,commit):
    if not re.fullmatch(r"[0-9]{8,20}",run_id) or not re.fullmatch(r"[a-f0-9]{40}",commit):raise RuntimeError("Invalid run/commit identity")
    validate_environment()
    if not owner(PRIVATE) or not PRIVATE.is_dir():raise RuntimeError("Private staging root absent or untrusted")
    if PRIVATE.stat().st_dev!=SITE.stat().st_dev:raise RuntimeError("Non-atomic cross-filesystem move")
    stage=PRIVATE/("staging-"+run_id)/"20261023"
    receipt=PRIVATE/("receipt-"+run_id+".json")
    with open(PRIVATE/"exclusive.lock","a+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if action=="install":
            if TARGET.exists() or TARGET.is_symlink():raise RuntimeError("Non-overwrite: version already exists")
            if receipt.exists() or receipt.is_symlink():raise RuntimeError("Run already has receipt")
            records=scan(stage)
            if PARENT.exists() or PARENT.is_symlink():
                if not owner(PARENT) or not PARENT.is_dir():raise RuntimeError("Invalid public release parent")
            else:
                PARENT.mkdir(mode=0o755)
            if not owner(PARENT):raise RuntimeError("Parent ownership changed")
            for base,dirs,files in os.walk(stage):
                os.chmod(base,0o755)
                for name in files:os.chmod(Path(base)/name,0o644)
            summary={"action":"install","run":run_id,"commit":commit,"target":str(TARGET),"release":RELEASE,**records}
            with open(receipt,"x") as f:json.dump(summary,f,sort_keys=True);f.flush();os.fsync(f.fileno())
            os.chmod(receipt,0o600)
            if TARGET.exists() or TARGET.is_symlink():raise RuntimeError("Concurrent install collision")
            os.replace(stage,TARGET)
            actual=scan(TARGET)
            if actual!=records:raise RuntimeError("After atomic publish manifest hashes changed")
            print("FIELD_STUDIO_ATOMIC_PUBLICATION_PASS",json.dumps({"release_id":RELEASE,"run":run_id,"guides":50,"game":"prism-relay","files":54,"manifest_sha256":records["root_hash"]},sort_keys=True))
        elif action=="rollback":
            if not receipt.is_file() or receipt.is_symlink():
                print("FIELD_STUDIO_NO_RECEIPT_NO_MUTATION");return
            data=json.loads(receipt.read_text())
            if (data.get("run"),data.get("commit"),data.get("release"),data.get("target"))!=(run_id,commit,RELEASE,str(TARGET)):raise RuntimeError("Rollback receipt identity mismatch")
            if not TARGET.exists():
                print("FIELD_STUDIO_ALREADY_ABSENT");return
            if TARGET.is_symlink():raise RuntimeError("Refuse rollback through symlink")
            current=scan(TARGET)
            for key in ("root_hash","files_sha256","file_count"):
                if current.get(key)!=data.get(key):raise RuntimeError("Rollback blocked by concurrent edits")
            shutil.rmtree(TARGET)
            print("FIELD_STUDIO_ONLY_OWN_VERSION_ROLLED_BACK",run_id)
        else:raise RuntimeError("Invalid operation")
if __name__=="__main__":
    if len(sys.argv)!=4:raise SystemExit("install|rollback RUN_ID GIT_SHA")
    operate(sys.argv[1],sys.argv[2],sys.argv[3])
