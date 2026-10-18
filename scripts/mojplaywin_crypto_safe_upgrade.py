#!/usr/bin/env python3
"""Safely upgrade ONLY existing MojPlayWin standalone payment files, still DISABLED.

No Passenger restart, no shared Django, no MySQL, no child-site writes.
This tool refuses to touch active payment processing, symlinks, mismatched
hashes, or any files beyond the two reviewed PHP files. Original bytes are
preserved inside the caller-provided private staging directory for rollback.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import shutil
import sys

GATEWAY=Path("/home/zomorod2/mojplaywin.com/checkout/crypto")
PRIVATE=Path("/home/zomorod2/.mojplaywin-crypto-payments-v1")
FILES=("index.php","bootstrap.php")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_file(path, expected, *, size=200000):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > size:
        raise RuntimeError("Unsafe or missing gateway source: "+path.name)
    if digest(path)!=expected:
        raise RuntimeError("Unexpected gateway source checksum: "+path.name)


def upgrade(stage, old_hashes, new_hashes):
    if GATEWAY.is_symlink() or not GATEWAY.is_dir():
        raise RuntimeError("Gateway directory missing or unsafe")
    if PRIVATE.is_symlink() or not PRIVATE.is_dir():
        raise RuntimeError("Private gateway state missing or unsafe")
    if (PRIVATE/"enabled.flag").exists() or (PRIVATE/"enabled.flag").is_symlink():
        raise RuntimeError("Never upgrade a gateway taking real payments")
    if stage.is_symlink() or not stage.is_dir() or stage.stat().st_mode & 0o077:
        raise RuntimeError("Private stage must be a mode-0700 directory")
    for name in FILES:
        require_file(GATEWAY/name,old_hashes[name])
        require_file(stage/name,new_hashes[name])
    for name in FILES:
        shutil.copyfile(GATEWAY/name,stage/("backup-"+name))
        os.chmod(stage/("backup-"+name),0o600)
        require_file(stage/("backup-"+name),old_hashes[name])
    replaced=[]
    try:
        for name in FILES:
            # Both private stage and main docroot are on the same cPanel volume.
            # The rename will fail closed if that assumption is untrue.
            replacement=stage/name
            os.chmod(replacement,0o644)
            os.replace(replacement,GATEWAY/name)
            replaced.append(name)
            require_file(GATEWAY/name,new_hashes[name])
    except BaseException:
        for name in reversed(replaced):
            os.chmod(stage/("backup-"+name),0o644)
            os.replace(stage/("backup-"+name),GATEWAY/name)
        raise
    for name in FILES:
        require_file(GATEWAY/name,new_hashes[name])
    print("MOJPLAYWIN_STANDALONE_GATEWAY_UPGRADED=true")
    print("PRIVATE_PAYMENT_ENABLED=false")
    print("SHARED_DJANGO_CHANGED=false")
    print("PROTECTED_CHILD_SITES_CHANGED=false")


if __name__=="__main__":
    if len(sys.argv)!=7 or sys.argv[1]!="upgrade":
        raise SystemExit("usage: upgrade.py upgrade stagedir sha_old_index sha_old_boot sha_new_index sha_new_boot")
    _,stage,oldi,oldb,newi,newb=sys.argv[1:]
    for value in (oldi,oldb,newi,newb):
        if len(value)!=64 or any(c not in "0123456789abcdef" for c in value):
            raise SystemExit("Invalid SHA256 digest.")
    upgrade(Path(stage),{"index.php":oldi,"bootstrap.php":oldb},{"index.php":newi,"bootstrap.php":newb})
