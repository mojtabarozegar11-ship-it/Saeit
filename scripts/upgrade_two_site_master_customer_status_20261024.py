#!/usr/bin/env python3
"""Guarded, reversible upgrade of only two /ask-master PHP endpoints.

No payments, cron, order sources, datasets, existing agent code, or other pages
are modified. Both existing index.php hashes must exactly match the originally
installed code; otherwise abort before changing either site.
"""
from __future__ import annotations
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tarfile
import time

HOME = Path("/home/zomorod2")
ROOT = HOME / ".private_mojplaywin_main_agents"
SITES = (("zomorod", HOME / "public_html/ask-master", HOME / ".private/zomorod-business", "zomorodmelal.ir"),
         ("mojplaywin", HOME / "mojplaywin.com/ask-master", ROOT, "mojplaywin.com"))
FILES = {"portal.php", "status.php", "manifest.json"}

def require(flag, reason):
    if not flag: raise RuntimeError(reason)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def write_new(path, raw, mode):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(path), flags, mode)
    with os.fdopen(fd, "wb") as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())
    os.chmod(path, mode)

def run(argv, timeout=22):
    return subprocess.run(argv, text=True, capture_output=True, timeout=timeout, check=False)

def verify_live():
    for site, directory, private, domain in SITES:
        for endpoint in ("index.php", "status.php"):
            result = run(["curl", "-fsS", "--max-time", "16", "https://" + domain + "/ask-master/" + endpoint], 20)
            require(result.returncode == 0, "PUBLIC_ENDPOINT_FAILED:" + site + ":" + endpoint)
        page = run(["curl", "-fsS", "--max-time", "16", "https://" + domain + "/ask-master/index.php"], 20).stdout
        require('href="/ask-master/status.php"' in page, "TICKET_LINK_MISSING:" + site)
        print("LIVE_SITE_MASTER_CUSTOMER_STATUS="+site+":PASS")

def main():
    require(sys.argv[1:] == ["upgrade"], "UPGRADE_COMMAND_REQUIRED")
    require(pwd.getpwuid(os.geteuid()).pw_name == "zomorod2" and Path.home() == HOME, "UNEXPECTED_ACCOUNT")
    require(ROOT.is_dir() and not ROOT.is_symlink() and ROOT.stat().st_mode & 0o007 == 0, "UNSAFE_BACKUP_ROOT")
    payload = sys.stdin.buffer.read(120001)
    require(500 < len(payload) <= 120000, "INVALID_PAYLOAD_SIZE")
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        members = archive.getmembers()
        require({m.name for m in members} == FILES and all(m.isfile() and m.size < 100000 for m in members),
                "UNEXPECTED_PAYLOAD_CONTENT")
        files = {member.name: archive.extractfile(member).read() for member in members}
    manifest = json.loads(files["manifest.json"].decode("utf-8"))
    require(manifest.get("scope") == "master_customer_tracking_only" and
            manifest.get("sites") == ["zomorod", "mojplaywin"], "WRONG_TARGET")
    for name in ("portal.php", "status.php"):
        require(manifest.get("sha256", {}).get(name) == sha(files[name]), "PAYLOAD_SHA_FAILED:"+name)
    previous = manifest.get("previous_portal_sha256")
    require(isinstance(previous, str) and len(previous) == 64, "PREVIOUS_SHA_INVALID")
    lockpath = ROOT / ".master_ticket_status_upgrade.lock"
    require(not lockpath.is_symlink(), "SYMLINK_LOCK")
    fd = os.open(str(lockpath), os.O_CREAT|os.O_RDWR, 0o600)
    changed = []
    temps = []
    backup = ROOT / ("master_ticket_status_upgrade_" + str(int(time.time())))
    try:
        fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
        for site, directory, private, domain in SITES:
            require(directory.is_dir() and not directory.is_symlink(), "PUBLIC_DIR_INVALID:"+site)
            require(private.is_dir() and not private.is_symlink() and private.stat().st_mode & 0o007 == 0,
                    "PRIVATE_DIR_INVALID:"+site)
            index = directory / "index.php"
            status = directory / "status.php"
            require(index.is_file() and not index.is_symlink() and
                    not status.exists() and not status.is_symlink(), "EXISTING_STATUS_OR_MISSING_INDEX:"+site)
            require(sha(index.read_bytes()) == previous, "LIVE_SITE_SOURCE_CHANGED:"+site)
        require(not backup.exists() and not backup.is_symlink(), "BACKUP_NAME_COLLISION")
        os.mkdir(backup, 0o700)
        for site, directory, private, domain in SITES:
            write_new(backup / (site+".old_index.php"), (directory/"index.php").read_bytes(), 0o600)
        for site, directory, private, domain in SITES:
            index = directory / "index.php"
            status = directory / "status.php"
            tempindex = directory / (".master_index_v2_"+str(os.getpid())+".php")
            tempstatus = directory / (".master_status_v2_"+str(os.getpid())+".php")
            for file,raw in ((tempindex,files["portal.php"]),(tempstatus,files["status.php"])):
                require(not file.exists() and not file.is_symlink(), "TEMP_PATH_COLLISION")
                write_new(file, raw, 0o644)
                temps.append(file)
                lint=run(["php","-l",str(file)],18)
                require(lint.returncode==0,"PHP_VALIDATION_FAILED:"+site+":"+file.name)
            require(sha(index.read_bytes()) == previous and not status.exists(), "TARGET_CHANGED_CONCURRENTLY:"+site)
            os.replace(tempindex,index)
            changed.append((site,index,previous,files["portal.php"]))
            os.replace(tempstatus,status)
            changed.append((site,status,"",files["status.php"]))
            require(sha(index.read_bytes())==sha(files["portal.php"]) and
                    sha(status.read_bytes())==sha(files["status.php"]), "READBACK_FAILED:"+site)
        verify_live()
        write_new(backup/"receipt.json",json.dumps({"scope":"customer_ticket_status_only",
                   "sites":["zomorod","mojplaywin"],"old_index_sha256":previous,
                   "new_index_sha256":sha(files["portal.php"]),
                   "new_status_sha256":sha(files["status.php"]),
                   "existing_orders_mutated":False,"existing_cron_mutated":False},
                   sort_keys=True).encode(),0o600)
        print("TWO_SITE_MASTER_CUSTOMER_TRACKING_UPGRADE=PASS")
        print("NO_PAYMENT_OR_CRON_MUTATIONS=PASS")
    except BaseException:
        for site,path,old,raw in reversed(changed):
            try:
                if not path.is_file() or path.is_symlink() or sha(path.read_bytes())!=sha(raw):
                    print("ROLLBACK_MANUAL_REVIEW="+site+":"+path.name)
                    continue
                if path.name=="status.php":
                    path.unlink()
                else:
                    back=backup/(site+".old_index.php")
                    restore=path.parent/(".master_restore_"+str(os.getpid())+".php")
                    require(back.is_file() and sha(back.read_bytes())==old,"BACKUP_INTEGRITY_FAILED")
                    write_new(restore,back.read_bytes(),0o644)
                    temps.append(restore)
                    os.replace(restore,path)
            except Exception:
                print("ROLLBACK_MANUAL_REVIEW="+site+":"+path.name)
        raise
    finally:
        for file in temps:
            try:
                if file.is_file() and not file.is_symlink(): file.unlink()
            except OSError:
                pass
        os.close(fd)

if __name__ == "__main__":
    main()
