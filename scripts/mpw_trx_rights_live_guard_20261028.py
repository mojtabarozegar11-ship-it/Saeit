#!/usr/bin/env python3
"""Fail-closed, reversible live TRX rights gate; no buyer or payment writes.

Applies five exact edits from the reviewed rights-gate design to three existing
cPanel modules. Preserve public product listings and unrelated invoice recovery;
block only new unapproved checkouts and invoice creation.
"""
from __future__ import annotations
import ast
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import tempfile

APP=Path("/home/zomorod2/Saeit-staging")
PUBLIC=Path("/home/zomorod2/mojplaywin.com")
BACKUPS=Path("/home/zomorod2/.local/share/mpw-trx-rights-guard-20261028")
TARGETS={
    "context":APP/"services/mpw_trx_commercial_context.py",
    "web":APP/"services/mpw_trx_commercial_web.py",
    "pages":APP/"services/mpw_trx_public_pages.py",
}
CONTEXT_OLD='    return {"mpw_trx_easy_enabled":released}\n'
CONTEXT_NEW=CONTEXT_OLD+'''
def rights_cleared_for_sale(product):
    """Require independently recorded explicit rights approval, never truthy strings."""
    metadata = getattr(product, "metadata", None)
    return type(metadata) is dict and metadata.get("rights_cleared") is True
'''
WEB_IMPORT_OLD="from services.mpw_trx_walletless_core import PaymentHold\n"
WEB_IMPORT_NEW=WEB_IMPORT_OLD+"from services.mpw_trx_commercial_context import rights_cleared_for_sale\n"
WEB_CHECK_OLD='        if not _eligible(product) or not Decimal("0") < Decimal(product.price) <= Decimal("1000"):\n'
WEB_CHECK_NEW='''        if (not _eligible(product) or not rights_cleared_for_sale(product)
                or not Decimal("0") < Decimal(product.price) <= Decimal("1000")):
'''
PAGES_IMPORT_OLD="from services.mpw_trx_walletless_core import PaymentHold\n"
PAGES_IMPORT_NEW=PAGES_IMPORT_OLD+"from services.mpw_trx_commercial_context import rights_cleared_for_sale\n"
PAGES_CATALOG_OLD="        if not _eligible(p): continue\n"
PAGES_CHECKOUT_OLD="    if product is None or not _eligible(product): raise Http404\n"
PAGES_CHECKOUT_NEW="""    if product is None or not _eligible(product) or not rights_cleared_for_sale(product):
        raise Http404
"""
PATCHES={
    "context":[(CONTEXT_OLD,CONTEXT_NEW)],
    "web":[(WEB_IMPORT_OLD,WEB_IMPORT_NEW),(WEB_CHECK_OLD,WEB_CHECK_NEW)],
    "pages":[(PAGES_IMPORT_OLD,PAGES_IMPORT_NEW),
             (PAGES_CHECKOUT_OLD,PAGES_CHECKOUT_NEW)],
}

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def transform(key,src):
    if key not in PATCHES: raise RuntimeError("UNKNOWN_MODULE")
    statuses=[]
    for old,new in PATCHES[key]:
        if src.count(new)==1:
            statuses.append(False)
        elif src.count(old)==1:
            src=src.replace(old,new,1)
            statuses.append(True)
        else:
            raise RuntimeError("SOURCE_DRIFT_OR_AMBIGUOUS:"+key)
    if len(set(statuses))!=1:
        raise RuntimeError("PARTIAL_MODULE_PATCH:"+key)
    compile(src,key,"exec")
    return src,statuses[0]

def check_structure(sources):
    for key,src in sources.items():
        tree=ast.parse(src)
        funcs={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        if key=="context":
            if "rights_cleared_for_sale" not in funcs:
                raise RuntimeError("RIGHTS_HELPER_ABSENT")
        elif key=="web":
            fn=funcs.get("_select_order")
            if fn is None or not any(isinstance(n,ast.With) for n in ast.walk(fn)):
                raise RuntimeError("ATOMIC_ORDER_GUARD_ABSENT")
            if "rights_cleared_for_sale(product)" not in ast.get_source_segment(src,fn):
                raise RuntimeError("ORDER_RIGHTS_CHECK_ABSENT")
        elif key=="pages":
            shop=funcs.get("public_shop")
            if shop is None:
                raise RuntimeError("PUBLIC_SHOP_MISSING")
            shop_source=ast.get_source_segment(src,shop)
            if PAGES_CATALOG_OLD not in shop_source or "rights_cleared_for_sale(p)" in shop_source:
                raise RuntimeError("PUBLIC_CATALOG_VISIBILITY_CHANGED")
            fn=funcs.get("product_checkout")
            if fn is None or "rights_cleared_for_sale(product)" not in ast.get_source_segment(src,fn):
                raise RuntimeError("CHECKOUT_RIGHTS_CHECK_ABSENT")

def guard():
    if pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":
        raise RuntimeError("WRONG_HOST_ACCOUNT")
    if any(p.is_symlink() or not p.is_dir() for p in (APP,PUBLIC)):
        raise RuntimeError("UNSAFE_APP_ROOT")
    wsgi=PUBLIC/"passenger_wsgi.py"
    if wsgi.is_symlink() or not wsgi.is_file() or "Saeit-staging" not in wsgi.read_text("utf8","replace"):
        raise RuntimeError("UNEXPECTED_PASSENGER_MAPPING")
    for key,path in TARGETS.items():
        if path.is_symlink() or path.parent.is_symlink() or not path.is_file() or APP not in path.parents:
            raise RuntimeError("UNSAFE_TARGET:"+key)
    for p in (APP/"tmp/restart.txt",PUBLIC/"tmp/restart.txt"):
        if p.is_symlink() or not p.parent.is_dir():
            raise RuntimeError("UNSAFE_PASSENGER_RESTART")

def inspect():
    old={k:p.read_bytes() for k,p in TARGETS.items()}
    new={}
    statuses=[]
    for k,raw in old.items():
        source,changed=transform(k,raw.decode("utf8"))
        new[k]=source.encode("utf8")
        statuses.append(changed)
    if len(set(statuses))!=1:
        raise RuntimeError("CROSS_MODULE_PARTIAL_PATCH")
    check_structure({k:v.decode("utf8") for k,v in new.items()})
    return old,new,statuses[0]

def atomic(path,raw):
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=".mpw-rights-")
    try:
        os.fchmod(fd,stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        if path.is_symlink(): raise RuntimeError("TARGET_CHANGED_TO_SYMLINK")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def restart():
    for p in (APP/"tmp/restart.txt",PUBLIC/"tmp/restart.txt"):
        p.touch()

def runtime_validate():
    """Read-only Django import + SKU flags; no order creation."""
    code='''import json,os,sys
os.chdir("/home/zomorod2/Saeit-staging");sys.path.insert(0,os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from core.models import Product
from services.mpw_trx_commercial_context import rights_cleared_for_sale
from services.mpw_trx_commercial_web import _select_order
from services.mpw_trx_public_pages import public_shop,product_checkout
data={}
for sku in (72,225,879):
    p=Product.objects.filter(pk=sku).first()
    data[str(sku)]={"exists":p is not None,
      "explicit_rights":rights_cleared_for_sale(p) if p is not None else False}
print("MPW_TRX_RIGHTS_RUNTIME="+json.dumps({"read_only":True,"no_invoices_created":True,
 "gate_imports_ok":True,"products":data},sort_keys=True))
'''
    py="/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python"
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1")
    result=subprocess.run([py,"-B","-c",code],cwd=APP,env=env,capture_output=True,
                          text=True,timeout=45)
    if result.returncode:
        raise RuntimeError("RIGHTS_GATE_RUNTIME_IMPORT_FAILED:"+result.stderr[-400:])
    evidence=[line for line in result.stdout.splitlines() if line.startswith("MPW_TRX_RIGHTS_RUNTIME=")]
    if len(evidence)!=1: raise RuntimeError("RUNTIME_EVIDENCE_MISSING")
    print(evidence[0])

def private_root():
    BACKUPS.mkdir(mode=0o700,parents=True,exist_ok=True)
    if BACKUPS.is_symlink() or stat.S_IMODE(BACKUPS.stat().st_mode)&0o077:
        raise RuntimeError("UNSAFE_BACKUP_DIR")

def receipt(run_id):
    folder=BACKUPS/run_id
    manifest=folder/"manifest.json"
    if folder.is_symlink() or not folder.is_dir() or manifest.is_symlink() or not manifest.is_file():
        raise RuntimeError("RELEASE_SNAPSHOT_MISSING")
    return folder,json.loads(manifest.read_text("utf8"))

def operation(mode,run_id=None):
    if mode not in ("check","apply","verify","rollback","recover"): raise RuntimeError("UNKNOWN_MODE")
    if mode!="check" and (run_id is None or not re.fullmatch(r"[0-9]{6,20}",run_id)):
        raise RuntimeError("INVALID_RUN_ID")
    guard()
    if mode=="check":
        old,new,needed=inspect()
        print("MPW_TRX_RIGHTS_PREFLIGHT="+json.dumps({"needs_install":needed,
          "old":{k:digest(v) for k,v in old.items()},
          "candidate":{k:digest(v) for k,v in new.items()},
          "read_only":True,"new_orders":0},sort_keys=True))
        return
    private_root()
    with (BACKUPS/"release.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        if mode=="apply":
            old,new,needed=inspect()
            if not needed:
                runtime_validate()
                print("MPW_TRX_RIGHTS_RELEASE=ALREADY_INSTALLED_NO_RESTART")
                return
            folder=BACKUPS/run_id
            folder.mkdir(mode=0o700)
            info={"run_id":run_id,"paths":{k:str(p) for k,p in TARGETS.items()},
                  "old":{k:digest(v) for k,v in old.items()},
                  "new":{k:digest(v) for k,v in new.items()}}
            for k,raw in old.items():
                with (folder/(k+".original.py")).open("xb") as f:
                    os.fchmod(f.fileno(),0o600)
                    f.write(raw);f.flush();os.fsync(f.fileno())
            with (folder/"manifest.json").open("x",encoding="utf8") as f:
                os.fchmod(f.fileno(),0o600)
                json.dump(info,f,sort_keys=True);f.flush();os.fsync(f.fileno())
            touched=[]
            try:
                for k,path in TARGETS.items():
                    if digest(path.read_bytes())!=info["old"][k]:
                        raise RuntimeError("CONCURRENT_EDIT:"+k)
                    atomic(path,new[k]);touched.append(k)
                current,_,needed=inspect()
                if needed or any(digest(current[k])!=info["new"][k] for k in TARGETS):
                    raise RuntimeError("POST_WRITE_MISMATCH")
                runtime_validate()
                restart()
            except BaseException:
                for k in reversed(touched):
                    path=TARGETS[k]
                    if digest(path.read_bytes())==info["new"][k]:
                        atomic(path,old[k])
                if touched: restart()
                print("MPW_TRX_RIGHTS_RELEASE=ROLLED_BACK_AFTER_FAILURE")
                raise
            print("MPW_TRX_RIGHTS_RELEASE=APPLIED_AND_SOURCE_VERIFIED; ORDERS=0; PAYMENTS=0")
            return
        folder,info=receipt(run_id)
        if info.get("run_id")!=run_id or info.get("paths")!={k:str(p) for k,p in TARGETS.items()}:
            raise RuntimeError("MANIFEST_MISMATCH")
        for k,path in TARGETS.items():
            backup=folder/(k+".original.py")
            if backup.is_symlink() or not backup.is_file() or digest(backup.read_bytes())!=info["old"][k]:
                raise RuntimeError("BACKUP_HASH_MISMATCH")
            if mode!="recover" and digest(path.read_bytes())!=info["new"][k]:
                raise RuntimeError("NEWER_SOURCE_EDIT_OR_WRONG_RELEASE")
        if mode=="recover":
            # The remote apply process can be terminated between atomic file writes.
            # Refuse all recovery writes unless every target is exactly old or new.
            current={k:digest(path.read_bytes()) for k,path in TARGETS.items()}
            if any(current[k] not in (info["old"][k],info["new"][k]) for k in TARGETS):
                raise RuntimeError("NEWER_SOURCE_EDIT_OR_WRONG_RELEASE")
            restored=0
            for k,path in TARGETS.items():
                if current[k]==info["new"][k]:
                    atomic(path,(folder/(k+".original.py")).read_bytes())
                    restored+=1
            if restored:
                restart()
            if any(digest(path.read_bytes())!=info["old"][k] for k,path in TARGETS.items()):
                raise RuntimeError("RECOVERY_VERIFICATION_FAILED")
            print("MPW_TRX_RIGHTS_RELEASE=RECOVERED_EXACT_SNAPSHOT; FILES="+str(restored))
        else:
            if mode=="verify":
                _,_,needed=inspect()
                if needed: raise RuntimeError("RIGHTS_GATE_MISSING")
                runtime_validate()
                print("MPW_TRX_RIGHTS_RELEASE=VERIFIED")
            else:
                for k,path in TARGETS.items():
                    atomic(path,(folder/(k+".original.py")).read_bytes())
                restart()
                print("MPW_TRX_RIGHTS_RELEASE=ROLLED_BACK_EXACT_RELEASE")

if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="check": operation("check")
    elif len(sys.argv)==3: operation(sys.argv[1],sys.argv[2])
    else: raise SystemExit("check | apply RUN_ID | verify RUN_ID | rollback RUN_ID | recover RUN_ID")
