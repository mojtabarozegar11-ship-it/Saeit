#!/usr/bin/env python3
"""Crown checkout route release: PINNED cPanel-internal promotion only.

Run as the actual cPanel site user via the trusted SSH relay. Never modifies
merchant settings, payment flags, wallets, databases, or unrelated websites.
The payment adapter is deliberately absent: this fixes code deployment ONLY.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import stat
import sys
import tempfile

HOME = Path("/home/zomorod2")
STAGE = HOME / "Saeit-staging"
SOURCE = HOME / "Saeit"
BACKUPS = HOME / ".mpw-crown-python-route-backups"
LOCKFILE = HOME / ".mpw-crown-python-route-lock"

OLD_STAGE = {
    "core/crown_fleet.py": "d8c97fb6714a8e50c9bfb2443bf4ffc10375dfef0da34d16ebd581ce0b2d15c3",
    "config/urls.py": "4185f70b6e6c14b2aed83e1f782b51e1ac177247eb44e3abbf0b405b5eed9321",
}
PROMOTED = {
    "core/crown_checkout.py": "23615aa9d38c9c6796a19c94e07bc10d77458d4a5cfa0ce5853f2df473e8ec2a",
    "core/crown_fleet.py": "7c2195eac823065553c4f707f49abd1c197345b94fc251f73fff59dab541123f",
    "core/crown_tron_receipts.py": "4dbef1c009e99178a7b04858d9f3c2c2403f17ce03a82793d67dfe882f5c4f4b",
}
APPEND = (
    "\n# Crown Defender: scoped, fail-closed paid cosmetic checkout route.\n"
    "from core.crown_checkout import crown_cosmetic_checkout\n"
    "urlpatterns += [path('store/crown/<int:product_id>/checkout/', "
    "crown_cosmetic_checkout, name='crown_cosmetic_checkout')]\n"
)
FILES = tuple(PROMOTED) + ("config/urls.py",)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def halt(msg: str):
    raise RuntimeError("CROWN_ROUTE_SAFE_ABORT: " + msg)


def read_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        halt("Unsafe or missing file: " + path.name)
    return path.read_bytes()


def ensure_owner():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        halt("Expected cPanel application owner")
    if (SOURCE.is_symlink() or STAGE.is_symlink()
        or not SOURCE.is_dir() or not STAGE.is_dir()
        or BACKUPS.is_symlink()):
        halt("Unexpected application directories")
    site = HOME / "mojplaywin.com"
    if site.is_symlink():
        halt("Unsafe website directory")
    text = read_regular(site / "passenger_wsgi.py").decode("utf-8", "replace")
    if "APP='/home/zomorod2/Saeit-staging'" not in text:
        halt("Passenger target has changed")


def prepared_files() -> tuple[dict[str, bytes], dict[str, bytes]]:
    prior = {}
    intended = {}
    for name, known in PROMOTED.items():
        src = read_regular(SOURCE / name)
        if digest(src) != known:
            halt("Approved source changed: " + name)
        intended[name] = src
        dest = STAGE / name
        if dest.is_symlink():
            halt("Unsafe symlink target")
        if name in OLD_STAGE:
            old = read_regular(dest)
            if digest(old) != OLD_STAGE[name]:
                halt("Staging file changed: " + name)
            prior[name] = old
        else:
            if dest.exists():
                halt("Expected new module absent: " + name)
            prior[name] = None
    old_urls = read_regular(STAGE / "config/urls.py")
    if digest(old_urls) != OLD_STAGE["config/urls.py"]:
        halt("Staging URL table changed")
    if (b"crown_cosmetic_checkout" in old_urls
        or b"urlpatterns" not in old_urls
        or b"from django.urls import" not in old_urls):
        halt("URL configuration no longer matches audited baseline")
    prior["config/urls.py"] = old_urls
    modified = old_urls.rstrip(b"\n") + b"\n" + APPEND.encode("utf-8")
    intended["config/urls.py"] = modified
    for path, data in intended.items():
        compile(data, str(STAGE / path), "exec")
    return prior, intended


def replace_bytes(path: Path, data: bytes, mode: int) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        halt("Unsafe replacement path")
    fd, temporary = tempfile.mkstemp(prefix=".crown-route-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def restart_marker():
    root = STAGE / "tmp"
    if root.is_symlink():
        halt("Unsafe Passenger restart directory")
    root.mkdir(mode=0o700, exist_ok=True)
    flag = root / "restart.txt"
    if flag.is_symlink():
        halt("Unsafe Passenger restart marker")
    if flag.exists():
        os.utime(flag, None)
    else:
        fd = os.open(str(flag), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)


def install(run: str):
    prior, intended = prepared_files()
    folder = BACKUPS / run
    if folder.exists() or folder.is_symlink():
        halt("Release identifier already used")
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    folder.mkdir(mode=0o700)
    manifest = {"run": run, "paths": {}, "status": "prepared"}
    for name in FILES:
        old = prior[name]
        entry = {"original": digest(old) if old is not None else None,
                 "installed": digest(intended[name]),
                 "mode": stat.S_IMODE((STAGE / name).stat().st_mode) if old is not None else 0o644}
        manifest["paths"][name] = entry
        if old is not None:
            backup = folder / name.replace("/", "__")
            with backup.open("xb") as f:
                f.write(old)
            backup.chmod(0o600)
    (folder / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), "utf-8")
    (folder / "manifest.json").chmod(0o600)
    applied = []
    try:
        for name in FILES:
            replace_bytes(STAGE / name, intended[name], manifest["paths"][name]["mode"])
            applied.append(name)
        for name in FILES:
            if digest(read_regular(STAGE / name)) != manifest["paths"][name]["installed"]:
                halt("Staged Python promotion failed read-back")
        restart_marker()
    except BaseException:
        for name in reversed(applied):
            old = prior[name]
            target = STAGE / name
            if old is None:
                if digest(read_regular(target)) == digest(intended[name]):
                    target.unlink()
            else:
                if digest(read_regular(target)) == digest(intended[name]):
                    replace_bytes(target, old, manifest["paths"][name]["mode"])
        restart_marker()
        raise
    manifest["status"] = "installed"
    (folder / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), "utf-8")
    print("CROWN_STAGING_SCOPED_PYTHON_FILES_INSTALLED=4")
    print("CROWN_STAGING_PURCHASES_ACTIVATED=NO")


def state(run: str):
    path = BACKUPS / run / "manifest.json"
    doc = json.loads(read_regular(path).decode("utf8"))
    if doc.get("run") != run or set(doc.get("paths", {})) != set(FILES):
        halt("Invalid private release receipt")
    for name, entry in doc["paths"].items():
        if digest(read_regular(STAGE / name)) != entry["installed"]:
            halt("Promoted file changed unexpectedly: " + name)
    print("CROWN_STAGING_SAFE_READBACK=PASS")
    print("CROWN_STAGING_PURCHASES_ACTIVATED=NO")


def rollback(run: str):
    path = BACKUPS / run / "manifest.json"
    doc = json.loads(read_regular(path).decode("utf8"))
    if doc.get("run") != run or set(doc.get("paths", {})) != set(FILES):
        halt("Invalid rollback receipt")
    for name, entry in doc["paths"].items():
        if digest(read_regular(STAGE / name)) != entry["installed"]:
            halt("Refusing to overwrite updated site code: " + name)
    for name in reversed(FILES):
        entry = doc["paths"][name]
        target = STAGE / name
        if entry["original"] is None:
            target.unlink()
        else:
            original = read_regular(BACKUPS / run / name.replace("/", "__"))
            if digest(original) != entry["original"]:
                halt("Private backup integrity failure")
            replace_bytes(target, original, entry["mode"])
    restart_marker()
    print("CROWN_STAGING_EXACT_ROLLBACK=PASS")


def main():
    if (len(sys.argv) != 3 or sys.argv[1] not in ("install", "status", "rollback")
        or not sys.argv[2].isdigit() or not 8 <= len(sys.argv[2]) <= 20):
        halt("Usage: install|status|rollback NUMERIC_RUN_ID")
    ensure_owner()
    with LOCKFILE.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        {"install": install, "status": state, "rollback": rollback}[sys.argv[1]](sys.argv[2])


if __name__ == "__main__":
    main()
