#!/usr/bin/env python3
"""Relocate two pinned old cPanel root backups to VPS with verified recovery copies.

This tool is intentionally narrow: it refuses arbitrary filenames, sizes, hashes,
or directories. It can only run after the operator activates the guarded workflow.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


TARGETS = {
    "8f37e05333ca": (312655273, "2ff7db09ccf3f31a8fe8"),
    "938b93515d71": (117467212, "4cca1e08040c588a7b32"),
}
DEST = "/home/githubops/zomorod-cpanel-archive-quarantine"
CPANEL = "saeit-cpanel"
VPS = "saeit-vps"


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ssh(config: Path, host: str, code: str, *args: str) -> str:
    command = "PYTHONDONTWRITEBYTECODE=1 python3 -c " + shlex.quote(code)
    command += "".join(" " + shlex.quote(str(arg)) for arg in args)
    result = subprocess.run(
        ["ssh", "-F", str(config), host, command],
        check=True, capture_output=True, text=True, timeout=180,
    )
    return result.stdout.strip()


SOURCE_INVENTORY = r'''
import hashlib,json,os,stat,time
from pathlib import Path
targets=json.loads(__import__("sys").argv[1])
home=Path("/home/zomorod2")
assert home.is_dir() and not home.is_symlink() and home.stat().st_uid==os.geteuid()
seen={}
for p in home.iterdir():
    key=hashlib.sha256(p.name.encode()).hexdigest()[:12]
    if key not in targets:
        continue
    assert not p.is_symlink() and p.parent==home
    s=p.stat()
    assert stat.S_ISREG(s.st_mode) and s.st_uid==os.geteuid()
    assert s.st_size==targets[key][0] and time.time()-s.st_mtime>=28*86400
    d=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""):
            d.update(b)
    assert d.hexdigest().startswith(targets[key][1])
    assert key not in seen
    seen[key]={"key":key,"name":p.name,"size":s.st_size,
               "sha256":d.hexdigest(),"mtime_ns":s.st_mtime_ns,
               "inode":s.st_ino}
assert seen.keys()==targets.keys()
print(json.dumps(list(seen.values()),separators=(",",":")))
'''


VPS_PREPARE = r'''
import os,stat,sys
from pathlib import Path
root=Path(sys.argv[1]);required=int(sys.argv[2])
assert root.parent==Path("/home/githubops")
root.mkdir(mode=0o700,exist_ok=True)
s=root.lstat()
assert stat.S_ISDIR(s.st_mode) and s.st_uid==os.geteuid() and not root.is_symlink()
assert (s.st_mode & 0o077)==0
v=os.statvfs(str(root));free=v.f_bavail*v.f_frsize
assert free>=required+4*1024*1024*1024,"VPS_FREE_SPACE_GUARD"
print("VPS_QUARANTINE_PREPARED=true")
'''


VPS_EXISTING = r'''
import hashlib,os,stat,sys
from pathlib import Path
p=Path(sys.argv[1]);expected=sys.argv[2];size=int(sys.argv[3])
if not p.exists():
    print("absent");sys.exit(0)
assert not p.is_symlink()
s=p.stat();assert stat.S_ISREG(s.st_mode) and s.st_uid==os.geteuid() and s.st_size==size
h=hashlib.sha256()
with p.open("rb") as f:
    for b in iter(lambda:f.read(1048576),b""):
        h.update(b)
assert h.hexdigest()==expected,"EXISTING_BACKUP_MISMATCH"
print("verified")
'''


VPS_FINALIZE = r'''
import hashlib,json,os,stat,sys
from pathlib import Path
root=Path(sys.argv[1]);key=sys.argv[2];expected=sys.argv[3];size=int(sys.argv[4])
manifest=json.loads(sys.argv[5]);assert manifest["key"]==key
part=root/("root-"+key+".part")
dest=root/("root-"+key+".archive")
assert root.is_dir() and not root.is_symlink() and root.stat().st_uid==os.geteuid()
assert part.is_file() and not part.is_symlink() and part.stat().st_uid==os.geteuid()
assert part.stat().st_size==size
h=hashlib.sha256()
with part.open("rb") as f:
    for b in iter(lambda:f.read(1048576),b""):
        h.update(b)
assert h.hexdigest()==expected,"TRANSFER_HASH_MISMATCH"
assert not dest.exists(),"DEST_ALREADY_EXISTS_NO_OVERWRITE"
os.replace(part,dest)
sidecar=root/("root-"+key+".json")
assert not sidecar.exists(),"MANIFEST_ALREADY_EXISTS"
fd=os.open(str(sidecar),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,"w") as f:
    json.dump(manifest,f,ensure_ascii=False,sort_keys=True)
    f.flush();os.fsync(f.fileno())
assert stat.S_ISREG(dest.stat().st_mode)
print("VPS_ARCHIVE_VERIFIED="+key+":BYTES="+str(size))
'''


SOURCE_DELETE = r'''
import hashlib,os,stat,sys,time
from pathlib import Path
key=sys.argv[1];expected=sys.argv[2];size=int(sys.argv[3]);mtime=int(sys.argv[4]);inode=int(sys.argv[5])
home=Path("/home/zomorod2")
matches=[p for p in home.iterdir() if hashlib.sha256(p.name.encode()).hexdigest()[:12]==key]
assert len(matches)==1,"SOURCE_NOT_UNIQUE"
p=matches[0];assert p.parent==home and not p.is_symlink()
s=p.lstat();assert stat.S_ISREG(s.st_mode) and s.st_uid==os.geteuid()
assert s.st_size==size and s.st_mtime_ns==mtime and s.st_ino==inode
assert time.time()-s.st_mtime>=28*86400
unknown=0;opened=0;root=str(p)
for proc in Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    try:
        if proc.stat().st_uid!=os.geteuid():
            continue
        for link in (proc/"cwd",proc/"exe"):
            try:
                opened+=int(os.readlink(link)==root)
            except FileNotFoundError:
                pass
            except OSError:
                unknown+=1
        for link in (proc/"fd").iterdir():
            try:
                opened+=int(os.readlink(link)==root)
            except FileNotFoundError:
                pass
            except OSError:
                unknown+=1
    except FileNotFoundError:
        pass
    except OSError:
        unknown+=1
assert not opened and not unknown,"PROCESS_REFERENCE_OR_UNCERTAINTY"
h=hashlib.sha256()
with p.open("rb") as f:
    assert os.fstat(f.fileno()).st_ino==inode
    for b in iter(lambda:f.read(1048576),b""):
        h.update(b)
assert h.hexdigest()==expected,"SOURCE_CHANGED"
assert p.lstat().st_ino==inode and p.stat().st_mtime_ns==mtime
p.unlink()
assert not p.exists()
print("CPANEL_ARCHIVE_RELOCATED="+key+":BYTES="+str(size))
'''


def run() -> None:
    if os.environ.get("CONFIRM_BACKUP_RELOCATION") != "true":
        raise RuntimeError("EXPLICIT_BACKUP_RELOCATION_CONFIRMATION_REQUIRED")
    relay_dir = Path(os.environ["RUNNER_TEMP"]) / "zomorod-baseline-inventory"
    config = relay_dir / "config"
    if not config.is_file():
        raise RuntimeError("PINNED_RELAY_MISSING")
    inventory = json.loads(ssh(config, CPANEL, SOURCE_INVENTORY, json.dumps(TARGETS)))
    if len(inventory) != len(TARGETS):
        raise RuntimeError("EXPECTED_TWO_ARCHIVES_NOT_FOUND")
    for item in inventory:
        if (item["key"] not in TARGETS or
                not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", item["name"])):
            raise RuntimeError("UNSAFE_SOURCE_BASENAME")
    total = sum(item["size"] for item in inventory)
    print("ARCHIVE_RELOCATION_EXPECTED_BYTES=" + str(total), flush=True)
    print(ssh(config, VPS, VPS_PREPARE, DEST, str(total)), flush=True)
    staging = relay_dir / "archive-staging"
    staging.mkdir(mode=0o700, exist_ok=True)
    for item in inventory:
        key, expected, size = item["key"], item["sha256"], item["size"]
        destination = f"{DEST}/root-{key}.archive"
        state = ssh(config, VPS, VPS_EXISTING, destination, expected, str(size))
        if state == "absent":
            local = staging / ("root-" + key + ".archive")
            subprocess.run(["scp", "-q", "-F", str(config),
                            f"{CPANEL}:/home/zomorod2/{item['name']}", str(local)],
                           check=True, timeout=600)
            if local.stat().st_size != size or checksum(local) != expected:
                raise RuntimeError("RUNNER_SOURCE_HASH_MISMATCH")
            part = f"{DEST}/root-{key}.part"
            subprocess.run(["scp", "-q", "-F", str(config), str(local),
                            f"{VPS}:{part}"], check=True, timeout=600)
            print(ssh(config, VPS, VPS_FINALIZE, DEST, key, expected,
                      str(size), json.dumps(item, ensure_ascii=False)), flush=True)
            local.unlink()
        elif state != "verified":
            raise RuntimeError("UNEXPECTED_DESTINATION_STATE")
        if ssh(config, VPS, VPS_EXISTING, destination, expected, str(size)) != "verified":
            raise RuntimeError("DESTINATION_FINAL_VERIFICATION_FAILED")
        print("VPS_ARCHIVE_RECOVERABLE=" + key, flush=True)
    # No source deletion is possible until *both* final VPS copies are verified.
    for item in inventory:
        print(ssh(config, CPANEL, SOURCE_DELETE, item["key"], item["sha256"],
                  str(item["size"]), str(item["mtime_ns"]), str(item["inode"])), flush=True)
    print("ARCHIVE_RELOCATION_TOTAL_BYTES=" + str(total), flush=True)


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("ARCHIVE_RELOCATION_STOPPED=" + type(exc).__name__, file=sys.stderr)
        raise
