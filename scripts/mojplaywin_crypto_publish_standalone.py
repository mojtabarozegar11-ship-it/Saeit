#!/usr/bin/env python3
"""Deploy ONLY a previously nonexistent /checkout/crypto/ PHP route.

Never touches shared Django/Passenger code/config, other docroot paths, MySQL,
or existing files. All source hashes supplied by trusted CI are verified before
exclusive creates. No production activation takes place here.
"""
import hashlib
import os
from pathlib import Path
import sys

DOCROOT=Path("/home/zomorod2/mojplaywin.com")
PARENT=DOCROOT/"checkout"
TARGET=PARENT/"crypto"
EXPECTED={"index.php", "bootstrap.php"}

def safe_root():
    if DOCROOT.is_symlink() or not DOCROOT.is_dir():
        raise RuntimeError("Main MojPlayWin docroot is not an isolated real directory.")
    if PARENT.exists() or PARENT.is_symlink():
        raise RuntimeError("Checkout parent already exists; do not overwrite/redeploy.")
    if TARGET.exists() or TARGET.is_symlink():
        raise RuntimeError("Gateway already exists.")

def publish(stage, expected):
    safe_root()
    if set(expected)!=EXPECTED:
        raise RuntimeError("Unexpected source manifest.")
    if stage.is_symlink() or not stage.is_dir():
        raise RuntimeError("Unsafe source stage.")
    for name in EXPECTED:
        f=stage/name
        if f.is_symlink() or not f.is_file() or f.stat().st_size>200_000:
            raise RuntimeError("Invalid or symlinked source.")
        if hashlib.sha256(f.read_bytes()).hexdigest()!=expected[name]:
            raise RuntimeError("Gateway source checksum mismatch.")
    PARENT.mkdir(mode=0o755)
    try:
        TARGET.mkdir(mode=0o755)
        for name in sorted(EXPECTED):
            p=TARGET/name
            fd=os.open(str(p),os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o644)
            with os.fdopen(fd,"wb") as out:
                out.write((stage/name).read_bytes())
                out.flush()
                os.fsync(out.fileno())
            os.chmod(p,0o644)
    except BaseException:
        rollback(expected)
        raise
    print("MOJPLAYWIN_STANDALONE_PAYMENT_FILES_STAGED=true")
    print("SHARED_DJANGO_AND_CHILD_SITES_TOUCHED=false")

def verify(existing, expected):
    """Idempotent verification; this never rewrites pre-existing production files."""
    if existing.is_symlink() or not existing.is_dir() or PARENT.is_symlink():
        raise RuntimeError("Unsafe gateway deployment path.")
    actual = {p.name for p in existing.iterdir() if p.is_file()}
    if not EXPECTED.issubset(actual):
        raise RuntimeError("Deployed gateway source is incomplete.")
    for name in EXPECTED:
        f=existing/name
        if f.is_symlink() or f.stat().st_size>200_000:
            raise RuntimeError("Deployed source is symlinked or oversized.")
        if hashlib.sha256(f.read_bytes()).hexdigest()!=expected[name]:
            raise RuntimeError("Deployed gateway does not match reviewed source.")
    print("MOJPLAYWIN_STANDALONE_EXISTING_FILES_VERIFIED=true")
    print("MOJPLAYWIN_PRODUCTION_FILES_OVERWRITTEN=false")


def rollback(expected):
    if TARGET.is_symlink() or PARENT.is_symlink():
        raise RuntimeError("Symlink encountered in rollback; refusing.")
    if TARGET.is_dir():
        for name in EXPECTED:
            file=TARGET/name
            if file.is_symlink():
                raise RuntimeError("Rollback file is symlink.")
            if file.is_file():
                digest=hashlib.sha256(file.read_bytes()).hexdigest()
                if digest!=expected[name]:
                    raise RuntimeError("File changed after stage; rollback refused.")
                file.unlink()
        TARGET.rmdir()  # never recursive deletion
    if PARENT.is_dir():
        PARENT.rmdir()  # only if empty
    print("MOJPLAYWIN_STANDALONE_ROUTE_REMOVED=true")

if __name__=="__main__":
    if len(sys.argv)!=5 or sys.argv[1] not in ("publish","rollback","verify"):
        raise SystemExit("usage: stage.py publish|rollback|verify stagedir sha_index sha_bootstrap")
    mode,stage,hash_index,hash_boot=sys.argv[1:]
    manifest={"index.php":hash_index,"bootstrap.php":hash_boot}
    if mode=="publish": publish(Path(stage),manifest)
    elif mode=="verify": verify(TARGET,manifest)
    else: rollback(manifest)
