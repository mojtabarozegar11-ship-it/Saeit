#!/usr/bin/env python3
"""Fail-closed, reversible installation of three QC-only verifier modules.

Never touches orders, products, databases, web roots, permissions to sell,
runner keys, signing keys, or evidence verdicts.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import pwd
from pathlib import Path
import sys
import tempfile

FILES = (
    "factory_commercial_quality_release_guard_v1.py",
    "factory_quality_signed_approval_v1.py",
    "factory_real_qc1000_live_monitor_20261023.py",
    "import_factory_store_drafts.py",
)
TARGET = Path("/home/zomorod2/.saeit-factory-inbox/bin")
PUBLISHER = "publish_verified_factory_store_listing.py"
LIVE_PUBLISHER_SHA = "e598544fce0f30783973e2b529549fed5d4b4457192db23e482304655963395e"
ANCHOR = '    body = release.read_text(encoding="utf-8")\n'
PREVIOUS_HOOK = (
    '    package_manifest=inbox/"packages"/RECIPE/(digest+".json")\n'
    '    if not package_manifest.is_file() or package_manifest.is_symlink():\n'
    '        raise ValueError("FACTORY_PRIVATE_RECIPE_MANIFEST_MISSING")\n'
    '    source_manifest=json.loads(package_manifest.read_text(encoding="utf8"))\n'
    '    if not isinstance(source_manifest,dict):\n'
    '        raise ValueError("FACTORY_PRIVATE_RECIPE_MANIFEST_INVALID")\n'
    '    if source_manifest.get("professional_quality_standard")=="100_groups_x_10":\n'
    '        quality=loaded("factory_premium_commercial_guard",\n'
    '                       "factory_commercial_quality_release_guard_v1.py")\n'
    '        quality.require_quality_clearance(inbox,RECIPE,digest,source_manifest,package)\n'
)
HOOK = (
    '    package_manifest=inbox/"packages"/RECIPE/(digest+".json")\n'
    '    if not package_manifest.is_file() or package_manifest.is_symlink():\n'
    '        raise ValueError("FACTORY_PRIVATE_RECIPE_MANIFEST_MISSING")\n'
    '    source_manifest=json.loads(package_manifest.read_text(encoding="utf8"))\n'
    '    if not isinstance(source_manifest,dict):\n'
    '        raise ValueError("FACTORY_PRIVATE_RECIPE_MANIFEST_INVALID")\n'
    '    quality=loaded("factory_premium_commercial_guard",\n'
    '                   "factory_commercial_quality_release_guard_v1.py")\n'
    '    clearance=quality.require_quality_clearance(\n'
    '        inbox,RECIPE,digest,source_manifest,package\n'
    '    )\n'
    '    if (clearance.get("status")!="VERIFIED_SIGNED_PREMIUM_1000"\n'
    '            or clearance.get("1000_quality_verified") is not True):\n'
    '        raise ValueError("QC1000_REQUIRED_FOR_FACTORY_EXIT")\n'
)



def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_file(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 250_000:
        raise RuntimeError("QC1000_INVALID_OR_SYMLINK_FILE: " + path.name)
    return path.read_bytes()


def verify_negative_controls(bin_dir):
    module_path = bin_dir / FILES[0]
    spec = importlib.util.spec_from_file_location("live_qc_guard", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("QC1000_GUARD_NOT_IMPORTABLE")
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    old = guard.require_quality_clearance(
        "/definitely-missing-qc-path", "oldedition", "a" * 64,
        {"professional_quality_standard": "legacy"},
        "/definitely-missing-qc-package.zip")
    if old.get("1000_quality_verified") is not False:
        raise RuntimeError("QC1000_FALSE_LEGACY_APPROVAL")
    try:
        guard.require_quality_clearance(
            "/definitely-missing-qc-path", "realproduct", "a" * 64,
            {"professional_quality_standard": "100_groups_x_10"},
            "/definitely-missing-qc-package.zip")
    except ValueError as exc:
        if str(exc) != "SIGNED_1000_QUALITY_GATE_EVIDENCE_MISSING":
            raise
    else:
        raise RuntimeError("QC1000_FALSE_PREMIUM_APPROVAL")
    if not callable(getattr(guard, "_verify_executed_qc1000", None)):
        raise RuntimeError("QC1000_EXECUTED_EVIDENCE_GATE_MISSING")
    publisher = (bin_dir / PUBLISHER).read_text(encoding="utf-8")
    if ("if source_manifest.get" in publisher
            or "QC1000_REQUIRED_FOR_FACTORY_EXIT" not in publisher
            or "clearance.get(\"1000_quality_verified\") is not True" not in publisher):
        raise RuntimeError("QC1000_PUBLISHER_EXIT_GATE_NOT_STRICT")
    importer = (bin_dir / "import_factory_store_drafts.py").read_text(encoding="utf-8")
    if ("STORE_BLOCKED_UNTIL_CHATGPT_AND_QC1000_APPROVE" not in importer
            or "factory_commercial_quality_release_guard_v1.py" not in importer):
        raise RuntimeError("QC1000_CHATGPT_STORE_IMPORT_GATE_NOT_STRICT")


def install(staging, expected):
    if os.getuid() == 0:
        raise RuntimeError("QC1000_ROOT_INSTALL_FORBIDDEN")
    if (TARGET.is_symlink() or not TARGET.is_dir()
            or TARGET.parent.is_symlink()
            or not (TARGET / PUBLISHER).is_file()
            or (TARGET / PUBLISHER).is_symlink()):
        raise RuntimeError("QC1000_PRIVATE_PUBLISHER_NOT_VERIFIED")
    publisher_raw = checked_file(TARGET / PUBLISHER)
    publisher = publisher_raw.decode("utf-8")
    if digest(publisher_raw) == LIVE_PUBLISHER_SHA:
        if publisher.count(ANCHOR) != 1 or "factory_commercial_quality_release_guard_v1.py" in publisher:
            raise RuntimeError("QC1000_PUBLISHER_PATCH_ANCHOR_UNTRUSTED")
        patched_publisher = publisher.replace(ANCHOR, HOOK + ANCHOR)
    else:
        # Idempotence only if exact original publisher was backed up and the
        # currently installed version is precisely the one surgical insertion.
        archived = TARGET / ".qc1000-versioned-backups" / LIVE_PUBLISHER_SHA / PUBLISHER
        original = checked_file(archived)
        if digest(original) != LIVE_PUBLISHER_SHA:
            raise RuntimeError("QC1000_LIVE_PUBLISHER_CHANGED_ABORT")
        original_text = original.decode("utf-8")
        if original_text.count(ANCHOR) != 1:
            raise RuntimeError("QC1000_ORIGINAL_PUBLISHER_ANCHOR_MISSING")
        patched_publisher = original_text.replace(ANCHOR, HOOK + ANCHOR)
        previous_publisher = original_text.replace(ANCHOR, PREVIOUS_HOOK + ANCHOR)
        if publisher == previous_publisher:
            # Upgrade only the exact previously installed surgical hook.
            pass
        elif publisher != patched_publisher:
            raise RuntimeError("QC1000_LIVE_PUBLISHER_CHANGED_ABORT")
    compile(patched_publisher, str(TARGET / PUBLISHER), "exec")
    stage = Path(staging)
    if stage.is_symlink() or not stage.is_dir():
        raise RuntimeError("QC1000_STAGING_MISSING")
    bytes_by_name = {}
    for name in FILES:
        value = checked_file(stage / name)
        if digest(value) != expected[name]:
            raise RuntimeError("QC1000_UPLOAD_HASH_MISMATCH:" + name)
        compile(value, str(stage / name), "exec")
        dest = TARGET / name
        if dest.exists() or dest.is_symlink():
            checked_file(dest)
        bytes_by_name[name] = value
    bytes_by_name[PUBLISHER] = patched_publisher.encode("utf-8")
    lockfile = TARGET / ".qc1000-modules-install.lock"
    if lockfile.is_symlink():
        raise RuntimeError("QC1000_UNSAFE_LOCK")
    with lockfile.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        old_files = {
            name: checked_file(TARGET / name) if (TARGET / name).exists() else None
            for name in bytes_by_name
        }
        backup_root = TARGET / ".qc1000-versioned-backups"
        if backup_root.is_symlink():
            raise RuntimeError("QC1000_BACKUP_LINK")
        backup_root.mkdir(mode=0o700, exist_ok=True)
        os.chmod(backup_root, 0o700)
        # Content-addressed backups remain readable even after a rollback.
        for name, previous in old_files.items():
            if previous is None or previous == bytes_by_name[name]:
                continue
            archived = backup_root / digest(previous)
            if archived.is_symlink():
                raise RuntimeError("QC1000_ARCHIVE_LINK")
            archived.mkdir(mode=0o700, exist_ok=True)
            backup = archived / name
            if backup.exists() or backup.is_symlink():
                if checked_file(backup) != previous:
                    raise RuntimeError("QC1000_BACKUP_COLLISION")
            else:
                with backup.open("xb") as stream:
                    stream.write(previous)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(backup, 0o600)
        changed = []
        try:
            for name, current in bytes_by_name.items():
                if old_files[name] == current:
                    continue
                fd, temp = tempfile.mkstemp(prefix=".qc1000.", dir=TARGET)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(current)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.chmod(temp, 0o600)
                    os.replace(temp, TARGET / name)
                    changed.append(name)
                finally:
                    if os.path.exists(temp):
                        os.unlink(temp)
            for name, correct in bytes_by_name.items():
                if digest(checked_file(TARGET / name)) != digest(correct):
                    raise RuntimeError("QC1000_INSTALLED_BYTES_DIFFER")
            verify_negative_controls(TARGET)
        except BaseException:
            for name in reversed(changed):
                previous = old_files[name]
                if previous is None:
                    (TARGET / name).unlink(missing_ok=True)
                else:
                    fd, temp = tempfile.mkstemp(prefix=".qc1000.rollback.", dir=TARGET)
                    try:
                        with os.fdopen(fd, "wb") as stream:
                            stream.write(previous)
                            stream.flush()
                            os.fsync(stream.fileno())
                        os.chmod(temp, 0o600)
                        os.replace(temp, TARGET / name)
                    finally:
                        if os.path.exists(temp):
                            os.unlink(temp)
            print("QC1000_MODULE_INSTALL_ROLLED_BACK=1", flush=True)
            raise
    print("QC1000_CPANEL_LIVE_GUARD_READBACK=PASS")
    print("QC1000_SURGICAL_PUBLISHER_HOOK_INSTALLED=PASS")
    print("QC1000_NO_FAKE_PREMIUM_CERTIFICATION=PASS")
    print("QC1000_FILES_INSTALLED=" + str(len(FILES)))
    print("QC1000_COMMERCIAL_PRODUCTS_MUTATED=0")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", required=True)
    for name in FILES:
        parser.add_argument("--sha-" + name.replace(".py", "").replace("_", "-"), required=True)
    args = parser.parse_args()
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("QC1000_EXPECTED_ACCOUNT_ONLY")
    checks = {
        name: getattr(args, "sha_" + name.replace(".py", ""))
        for name in FILES
    }
    for val in checks.values():
        if len(val) != 64 or any(x not in "0123456789abcdef" for x in val):
            raise RuntimeError("QC1000_SHA_INVALID")
    install(args.staging, checks)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("QC1000_INSTALL_ERROR=" + type(exc).__name__ + ":" + str(exc)[:140],
              file=sys.stderr)
        sys.exit(1)
