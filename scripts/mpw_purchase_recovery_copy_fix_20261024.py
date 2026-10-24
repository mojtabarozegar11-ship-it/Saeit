#!/usr/bin/env python3
"""Guarded, reversible copy-only fix for MojPlayWin buyer support and expired invoice recovery."""
from pathlib import Path
import hashlib, json, os, re, stat, sys, tempfile

HOME=Path("/home/zomorod2")
APP=HOME/"Saeit-staging"
SITE=HOME/"mojplaywin.com"
WSGI=SITE/"passenger_wsgi.py"
TARGETS={
    "support":APP/"core/brand_views.py",
    "invoice":APP/"services/mpw_trx_walletless_checkout_ui.py",
}
REPLACEMENTS={
    "support":[
        ("Game and account support will expand alongside released products.",
         "For login, order status, invoice expiry, or digital download help, email support@mojplaywin.com with your order number. Never share your wallet recovery phrase or private key."),
        ('("Account Help","Planned","Account recovery and profile support will be connected when accounts launch.")',
         '("Orders & Account Help","support@mojplaywin.com","For login, invoice, payment status, and download help, email with your order number. Never share your wallet recovery phrase or private key.")'),
    ],
    "invoice":[
        ("Automatic status checks paused. Contact support; do not send a second payment.",
         "Status checks paused after 35 minutes. If you sent TRX, do not pay again; check My TRX purchases or contact support. If unpaid, start a fresh invoice from the store."),
        ("<p>If the invoice expires or there is a network error, do not pay again. Contact support.</p>",
         '<p>If the invoice expires or status checks stop, do not pay again if you have already sent TRX. Check <a href="/commerce/trx-easy/purchases/">My TRX purchases</a> or <a href="/support/">contact support</a>. If you have not paid, return to the <a href="/store/">store</a> and create a fresh invoice.</p>'),
    ],
}

def digest(data): return hashlib.sha256(data).hexdigest()
def safe_run(value):
    if not re.fullmatch(r"[0-9]{9,20}",value): raise RuntimeError("Invalid workflow run id")
    return value
def backup_dir(run): return HOME/(".mpw-purchase-ux-backup-"+safe_run(run))
def atomic_write(path,data,mode):
    if path.is_symlink() or not path.is_file(): raise RuntimeError("Target path changed or is unsafe")
    fd,name=tempfile.mkstemp(prefix=".mpw-purchase-ux-",dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        os.replace(name,path)
        dfd=os.open(path.parent,os.O_RDONLY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
    finally:
        if os.path.exists(name): os.unlink(name)
def verify_roots():
    if APP.is_symlink() or not APP.is_dir() or SITE.is_symlink() or not SITE.is_dir():
        raise RuntimeError("Verified MojPlayWin app/site roots changed")
    if WSGI.is_symlink() or not WSGI.is_file() or "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8","replace"):
        raise RuntimeError("Passenger app root is not the pinned MojPlayWin root")
    for path in TARGETS.values():
        if path.is_symlink() or not path.is_file() or path.stat().st_size>2_000_000:
            raise RuntimeError("A source target is missing, oversized, or unsafe")
def render_patches():
    originals={};patched={}
    for name,path in TARGETS.items():
        raw=path.read_bytes()
        try: source=raw.decode("utf8")
        except UnicodeDecodeError as exc: raise RuntimeError("Source encoding changed") from exc
        updated=source
        for old,new in REPLACEMENTS[name]:
            count=updated.count(old)
            if count!=1: raise RuntimeError(f"Expected one exact source match in {name}, found {count}")
            updated=updated.replace(old,new,1)
        originals[name]=raw;patched[name]=updated.encode("utf8")
    return originals,patched
def check_patched():
    for name,path in TARGETS.items():
        text=path.read_text("utf8")
        for old,new in REPLACEMENTS[name]:
            if old in text or text.count(new)!=1: raise RuntimeError(f"Post-write check failed for {name}")
    os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from django.test import Client
    from django.template import engines
    def reset(loader):
        if hasattr(loader,"reset"): loader.reset()
        for child in getattr(loader,"loaders",()): reset(child)
    for loader in engines["django"].engine.template_loaders: reset(loader)
    response=Client(raise_request_exception=True).get("/support/",secure=True,HTTP_HOST="mojplaywin.com")
    body=response.content.decode("utf8","replace")
    required=("For login, order status, invoice expiry, or digital download help",
              "Orders &amp; Account Help","Never share your wallet recovery phrase or private key")
    if response.status_code!=200 or any(x not in body for x in required):
        raise RuntimeError("Django support page did not render the updated customer instructions")
def save_backup(path,data):
    with open(path,"xb") as out:
        os.fchmod(out.fileno(),0o600);out.write(data);out.flush();os.fsync(out.fileno())
def restart_markers():
    for root in (APP,SITE):
        if root.is_symlink() or not root.is_dir(): raise RuntimeError("Restart root changed")
        d=root/"tmp"
        if d.is_symlink(): raise RuntimeError("Restart directory is a symlink")
        d.mkdir(exist_ok=True)
        p=d/"restart.txt"
        if p.is_symlink() or (p.exists() and not p.is_file()): raise RuntimeError("Restart marker unsafe")
        p.touch()
def install(run):
    run=safe_run(run);verify_roots(); originals,patched=render_patches()
    backup=backup_dir(run)
    if backup.exists() or backup.is_symlink(): raise RuntimeError("Backup collision")
    backup.mkdir(mode=0o700)
    manifest={"run":run,"files":{}}
    for name,path in TARGETS.items():
        original=originals[name]; mode=stat.S_IMODE(path.stat().st_mode)
        save_backup(backup/(name+".original"),original)
        manifest["files"][name]={"path":str(path),"old_sha256":digest(original),"new_sha256":digest(patched[name]),"mode":mode}
    with open(backup/"manifest.json","x",encoding="utf8") as out:
        os.chmod(backup/"manifest.json",0o600);json.dump(manifest,out,sort_keys=True);out.flush();os.fsync(out.fileno())
    written=[]
    try:
        for name,path in TARGETS.items():
            atomic_write(path,patched[name],manifest["files"][name]["mode"]);written.append(name)
        check_patched()
        restart_markers()
    except BaseException:
        for name in reversed(written):
            atomic_write(TARGETS[name],originals[name],manifest["files"][name]["mode"])
        raise
    print(json.dumps({"status":"MPW_PURCHASE_UX_COPY_FIX_INSTALLED","changed_files":{n:manifest["files"][n] for n in TARGETS},"orders_or_payments_changed":False,"wallet_data_changed":False,"backup":str(backup)},sort_keys=True))
def rollback(run):
    run=safe_run(run);backup=backup_dir(run)
    if not backup.is_dir() or backup.is_symlink(): raise RuntimeError("Verified backup missing")
    manifest=json.loads((backup/"manifest.json").read_text("utf8"))
    if manifest.get("run")!=run: raise RuntimeError("Backup run mismatch")
    for name,path in TARGETS.items():
        info=manifest["files"][name];old=(backup/(name+".original")).read_bytes()
        if digest(old)!=info["old_sha256"] or str(path)!=info["path"]: raise RuntimeError("Backup integrity failed")
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes())!=info["new_sha256"]:
            raise RuntimeError("Concurrent source change; refusing rollback")
    for name,path in TARGETS.items():
        info=manifest["files"][name];atomic_write(path,(backup/(name+".original")).read_bytes(),info["mode"])
    restart_markers()
    print(json.dumps({"status":"MPW_PURCHASE_UX_COPY_FIX_ROLLED_BACK","restored":list(TARGETS),"orders_or_payments_changed":False},sort_keys=True))
if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1] not in ("install","rollback"): raise SystemExit("Usage: patch.py install|rollback RUN_ID")
    {"install":install,"rollback":rollback}[sys.argv[1]](sys.argv[2])
