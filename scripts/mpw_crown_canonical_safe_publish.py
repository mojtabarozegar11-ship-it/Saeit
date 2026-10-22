#!/usr/bin/env python3
"""Scoped, hash-pinned Crown canonical HTML deployment with private rollback.

Never touches parent .htaccess, Django, payments, other games, or databases.
Refuse to replace a file whose current bytes are not exactly the expected old
public release. Restore from a private byte-for-byte snapshot on smoke failure.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import sys

HOME = Path("/home/zomorod2")
GAME = HOME / "mojplaywin.com/design-preview-20261017/mpw-crown-defender-20261019"
TARGET = GAME / "index.html"
RECEIPTS = HOME / ".mpw-crown-canonical-receipts"


def abort(message):
    raise RuntimeError("CROWN_CANONICAL_SAFE_ABORT: " + message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked(run, old, new):
    if not re.fullmatch(r"[0-9]{8,16}", run):
        abort("Invalid GitHub run number")
    if not all(re.fullmatch(r"[0-9a-f]{64}", x) for x in (old, new)) or old == new:
        abort("Invalid changed-file SHA-256 pair")
    for path in (HOME, GAME):
        if path.is_symlink() or not path.is_dir():
            abort("Directory is missing or a symlink")
    if TARGET.is_symlink() or not TARGET.is_file():
        abort("Canonical game HTML is missing or a symlink")
    if RECEIPTS.is_symlink():
        abort("Unsafe backup directory")
    return (HOME / (".mpw-crown-canonical-stage-" + run),
            RECEIPTS / ("release-" + run))


def atomic_write(target, data, mode):
    # Never create a temporary directory under an untrusted or broad path.
    scratch = target.parent / (".crown-atomic-" + str(os.getpid()) + "-" + target.name)
    if scratch.exists() or scratch.is_symlink():
        abort("Atomic temp filename collision")
    fd = os.open(str(scratch), os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), mode)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(scratch), str(target))
    except BaseException:
        if scratch.is_file() and not scratch.is_symlink():
            scratch.unlink()
        raise


def install(run, old_sha, new_sha):
    stage, receipt = checked(run, old_sha, new_sha)
    if (not stage.is_dir() or stage.is_symlink()
            or {p.name for p in stage.iterdir()} != {"index.html"}
            or receipt.exists() or receipt.is_symlink()):
        abort("Missing isolated staging file or repeated deployment")
    staged_file = stage / "index.html"
    if not staged_file.is_file() or staged_file.is_symlink():
        abort("Unsafe staged game")
    current, incoming = TARGET.read_bytes(), staged_file.read_bytes()
    if digest(current) != old_sha or digest(incoming) != new_sha:
        abort("Canonical current/staged bytes differ from approved release")
    if (b"store\\/product\\/" not in current
            or b"store\\/crown\\/" not in incoming
            or b"Air Supremacy" not in incoming
            or b"100 / 100" not in incoming):
        abort("Game and unchanged 100-life contract do not match")

    RECEIPTS.mkdir(mode=0o700, exist_ok=True)
    if RECEIPTS.is_symlink():
        abort("Receipt directory became unsafe")
    receipt.mkdir(mode=0o700)
    backup = receipt / "original.html"
    fd = os.open(str(backup), os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(current)
        stream.flush()
        os.fsync(stream.fileno())
    manifest = receipt / "manifest.json"
    record = {"run": run, "target": str(TARGET), "old": old_sha,
              "new": new_sha, "status": "prepared"}
    with manifest.open("x", encoding="utf-8") as f:
        os.fchmod(f.fileno(), 0o600)
        json.dump(record, f, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    mode = stat.S_IMODE(TARGET.stat().st_mode)
    if not stat.S_ISREG(TARGET.stat().st_mode):
        abort("Refusing non-regular target")
    atomic_write(TARGET, incoming, mode)
    record["status"] = "installed"
    manifest.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    os.chmod(manifest, 0o600)
    print("CROWN_CANONICAL_DEPLOY_SHA256=" + digest(TARGET.read_bytes()))


def receipt_for(run, old, new):
    _, receipt = checked(run, old, new)
    manifest = receipt / "manifest.json"
    original = receipt / "original.html"
    if (not manifest.is_file() or manifest.is_symlink()
            or not original.is_file() or original.is_symlink()):
        abort("Missing or unsafe rollback receipt")
    record = json.loads(manifest.read_text("utf-8"))
    if (record.get("run") != run or record.get("target") != str(TARGET)
            or record.get("old") != old or record.get("new") != new
            or record.get("status") not in ("prepared", "installed", "rolled_back")
            or digest(original.read_bytes()) != old):
        abort("Receipt does not match pinned deployment")
    return receipt, manifest, record, original


def status(run, old, new):
    _, _, record, _ = receipt_for(run, old, new)
    if record["status"] != "installed" or digest(TARGET.read_bytes()) != new:
        abort("Canonical does not contain installed approved bytes")
    print("CROWN_CANONICAL_LIVE_BYTES=PASS")


def rollback(run, old, new):
    receipt, manifest, record, original = receipt_for(run, old, new)
    if record["status"] == "rolled_back":
        if digest(TARGET.read_bytes()) != old:
            abort("Unexpected modification after rollback")
        print("CROWN_CANONICAL_ALREADY_RESTORED=YES")
        return
    if digest(TARGET.read_bytes()) != new:
        abort("Canonical changed after install; refuse overwrite")
    mode = stat.S_IMODE(TARGET.stat().st_mode)
    atomic_write(TARGET, original.read_bytes(), mode)
    record["status"] = "rolled_back"
    manifest.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    os.chmod(manifest, 0o600)
    print("CROWN_CANONICAL_RESTORED_SHA256=" + digest(TARGET.read_bytes()))


if __name__ == "__main__":
    if len(sys.argv) != 5 or sys.argv[1] not in ("install", "status", "rollback"):
        abort("Usage: install|status|rollback RUN OLD_SHA NEW_SHA")
    {"install": install, "status": status, "rollback": rollback}[sys.argv[1]](*sys.argv[2:])
