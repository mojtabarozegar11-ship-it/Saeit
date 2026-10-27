#!/usr/bin/env python3
"""Narrow, reversible repair for transient private JSON read failures on VPS.

Only the exact reviewed _read_private_json block may change. No product, order,
database, cron, quality approval or public site is touched.
"""
import argparse
import ast
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

OLD = '''def _read_private_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None
'''
NEW = '''def _read_private_json(path):
    """Fail closed on transient filesystem errors during private JSON inspection."""
    path = Path(path)
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            return None
        value = json.loads(path.read_text(encoding="utf8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None
'''

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def transform(source):
    if not isinstance(source, str):
        raise ValueError("SOURCE_TEXT_REQUIRED")
    old_count = source.count(OLD)
    new_count = source.count(NEW)
    if old_count == 0 and new_count == 1:
        ast.parse(source)
        return source, False
    if old_count != 1 or new_count:
        raise ValueError("REVIEWED_SOURCE_BLOCK_NOT_EXACT")
    updated = source.replace(OLD, NEW, 1)
    ast.parse(updated)
    return updated, True

def atomic_bytes(path, data):
    fd, temp = tempfile.mkstemp(prefix=".json-reader-hotfix-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def target_paths():
    base = Path.home() / "factory-runtime"
    operations = base / "operations"
    runtime = operations / "autonomous-product-runtime"
    target = runtime / "scripts/factory_vps_product_cycle.py"
    backups = operations / "backups"
    lock = operations / "autonomous-product-cycle.lock"
    for directory in (base, operations, runtime, target.parent, backups):
        if directory.is_symlink() or not directory.is_dir():
            raise RuntimeError("UNSAFE_FACTORY_DIRECTORY")
    if (target.is_symlink() or not target.is_file()
            or lock.is_symlink() or not lock.is_file()):
        raise RuntimeError("UNSAFE_FACTORY_CODE_OR_LOCK")
    if target.stat().st_uid != os.geteuid() or target.stat().st_size > 1_000_000:
        raise RuntimeError("UNSAFE_FACTORY_CODE_OWNER_OR_SIZE")
    return target, backups, lock

def repair(run_id, apply=False):
    if os.geteuid() == 0:
        raise RuntimeError("ROOT_FORBIDDEN")
    if not re.fullmatch(r"[0-9]{1,20}", run_id):
        raise ValueError("INVALID_RUN_ID")
    target, backups, lock = target_paths()
    if apply and shutil.disk_usage(target.parent).free < 2 * 1024**3:
        raise RuntimeError("FACTORY_DISK_RESERVE_HOLD")
    with lock.open("r+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX if apply else fcntl.LOCK_SH)
        original = target.read_bytes()
        if len(original) > 1_000_000:
            raise RuntimeError("SOURCE_OVERSIZED")
        source = original.decode("utf8")
        updated, changed = transform(source)
        result = {"schema": "saeit.factory.json-reader-hotfix.v1",
                  "original_sha256": sha(original),
                  "result_sha256": sha(updated.encode("utf8")),
                  "change_required": changed, "applied": False,
                  "commercial_release_authorized": False, "sites_modified": False}
        if not apply or not changed:
            return result
        backup = backups / ("factory-cycle-json-before-" + run_id + ".py")
        if backup.exists() or backup.is_symlink():
            raise RuntimeError("BACKUP_NAME_ALREADY_EXISTS")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(str(backup), flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        if sha(backup.read_bytes()) != sha(original):
            raise RuntimeError("BACKUP_INTEGRITY_FAILED")
        new_data = updated.encode("utf8")
        try:
            atomic_bytes(target, new_data)
            installed = target.read_bytes()
            if sha(installed) != sha(new_data):
                raise RuntimeError("INSTALL_HASH_MISMATCH")
            ast.parse(installed.decode("utf8"))
        except Exception:
            atomic_bytes(target, original)
            raise
        result["applied"] = True
        result["backup_sha256"] = sha(original)
        return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print("FACTORY_JSON_HOTFIX=" + json.dumps(repair(args.run_id, args.apply), sort_keys=True))

if __name__ == "__main__":
    main()
