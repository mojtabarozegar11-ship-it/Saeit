#!/usr/bin/env python3
"""Bounded, reversible repair for one MojPlayWin header static asset.

This is deliberately NOT called by an automatic deploy workflow. A separately
approved operator must stage the exact Git-tracked JPEG and explicitly invoke
``apply``. No application, order, payment, email, or customer data is touched.
"""

import argparse
import fcntl
import hashlib
import json
import os
import pwd
import re
import stat
import tempfile
from pathlib import Path

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
ASSET = "site/mojplaywin-header-emblem.jpg"
CSS = "site/mojplaywin.css"
# Git blob of core/static/site/mojplaywin-header-emblem.jpg on the audited main.
EXPECTED_GIT_BLOB = "bfd6977e82b6623b67edbbbc00a60e25cd56f810"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def safe_file(path, required=False):
    if path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError("Unsafe asset or parent symlink")
    if path.exists() and not path.is_file():
        raise RuntimeError("Unexpected non-file path")
    if required and not path.is_file():
        raise RuntimeError("Required file missing")


def atomic_bytes(path, data, mode):
    safe_file(path)
    fd, name = tempfile.mkstemp(prefix=".mpw-header-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.lexists(name):
            os.unlink(name)


def hashed_name(raw):
    return "site/mojplaywin-header-emblem." + hashlib.md5(raw).hexdigest()[:12] + ".jpg"


def manifest_for_asset(original, raw):
    if len(original) > 3_000_000:
        raise RuntimeError("Oversized manifest refused")
    payload = json.loads(original.decode("utf-8"))
    if (not isinstance(payload, dict) or payload.get("version") != "1.1" or
            not isinstance(payload.get("paths"), dict)):
        raise RuntimeError("Unsupported manifest format")
    paths = payload["paths"]
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in paths.items()):
        raise RuntimeError("Invalid manifest paths")
    existing = paths.get(ASSET)
    new_target = hashed_name(raw)
    if existing is not None and existing != new_target:
        raise RuntimeError("Header has a different existing manifest target")
    if CSS not in paths:
        raise RuntimeError("Existing MojPlayWin CSS manifest mapping missing")
    paths[ASSET] = new_target
    payload["hash"] = hashlib.md5(json.dumps(sorted(paths.items())).encode()).hexdigest()[:12]
    return new_target, (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def plan(app, staged_jpeg, expected_blob=EXPECTED_GIT_BLOB):
    app = Path(app)
    static_root = app / "staticfiles"
    source = app / "core/static" / ASSET
    original = static_root / ASSET
    manifest = static_root / "staticfiles.json"
    jpeg = Path(staged_jpeg)
    for directory in (app, app / "core", app / "core/static", source.parent,
                      static_root, original.parent, jpeg.parent):
        if directory.is_symlink() or not directory.is_dir():
            raise RuntimeError("Unsafe or absent asset directory")
    for file in (source, original, manifest, jpeg):
        safe_file(file, file in (manifest, jpeg))
    raw = jpeg.read_bytes()
    if (len(raw) < 1000 or len(raw) > 1_000_000 or not raw.startswith(b"\xff\xd8") or
            not raw.endswith(b"\xff\xd9") or git_blob_sha(raw) != expected_blob):
        raise RuntimeError("Staged image fails pinned source identity")
    manifest_before = manifest.read_bytes()
    target_name, manifest_after = manifest_for_asset(manifest_before, raw)
    css_target = json.loads(manifest_before.decode("utf-8"))["paths"][CSS]
    if not re.fullmatch(r"site/mojplaywin\.[0-9a-f]{12}\.css", css_target):
        raise RuntimeError("Unsafe or uncollected CSS manifest target")
    css_collected = static_root / css_target
    safe_file(css_collected, required=True)
    target = static_root / target_name
    safe_file(target)
    for path in (source, original, target):
        if path.is_file() and path.read_bytes() != raw:
            raise RuntimeError("Refusing to overwrite a different image")
    return {
        "asset": raw,
        "manifest_before": manifest_before,
        "manifest_after": manifest_after,
        "manifest": manifest,
        "image_paths": (source, original, target),
        "ready": all(path.is_file() for path in (source, original, target)) and
                 manifest_before == manifest_after,
    }


def audit(app, staged_jpeg, expected_blob=EXPECTED_GIT_BLOB):
    result = plan(app, staged_jpeg, expected_blob)
    return {"scope": "mpw_header_only", "status": "ready" if result["ready"] else "repair_required",
            "source_present": result["image_paths"][0].is_file(),
            "collected_present": result["image_paths"][1].is_file(),
            "hashed_present": result["image_paths"][2].is_file(),
            "manifest_matches": result["manifest_before"] == result["manifest_after"],
            "writes_performed": False}


def apply(app, staged_jpeg, backup, expected_blob=EXPECTED_GIT_BLOB):
    state = plan(app, staged_jpeg, expected_blob)
    if state["ready"]:
        return {"scope": "mpw_header_only", "status": "already_ready", "writes_performed": False}
    backup = Path(backup)
    if backup.exists() or backup.is_symlink() or backup.parent.is_symlink():
        raise RuntimeError("Backup path already exists or unsafe")
    if not backup.parent.is_dir():
        raise RuntimeError("Missing backup parent")
    disk = os.statvfs(state["manifest"].parent)
    if disk.f_bavail * disk.f_frsize < 100_000_000:
        raise RuntimeError("Insufficient free disk space")
    entries = list(state["image_paths"]) + [state["manifest"]]
    old = {str(p): p.read_bytes() if p.is_file() else None for p in entries}
    updated = {str(p): state["asset"] for p in state["image_paths"]}
    updated[str(state["manifest"])] = state["manifest_after"]
    modes = {str(p): stat.S_IMODE(p.stat().st_mode) if p.is_file() else 0o644 for p in entries}
    backup.mkdir(mode=0o700)
    record = {"files": {}, "status": "prepared", "target": state["image_paths"][2].name}
    for n, path in enumerate(entries):
        before = old[str(path)]
        record["files"][str(n)] = {"existed": before is not None, "mode": modes[str(path)],
                                    "old": sha256(before) if before is not None else None,
                                    "new": sha256(updated[str(path)])}
        if before is not None:
            atomic_bytes(backup / str(n), before, 0o600)
    atomic_bytes(backup / "record.json", json.dumps(record, sort_keys=True).encode(), 0o600)
    written = []
    try:
        for path in entries:
            key = str(path)
            if old[key] == updated[key]:
                continue
            if (path.read_bytes() if path.is_file() else None) != old[key]:
                raise RuntimeError("Concurrent asset change refused")
            atomic_bytes(path, updated[key], modes[key])
            written.append(path)
        record["status"] = "applied"
        atomic_bytes(backup / "record.json", json.dumps(record, sort_keys=True).encode(), 0o600)
    except Exception:
        for path in reversed(written):
            key = str(path)
            if path.is_file() and sha256(path.read_bytes()) == sha256(updated[key]):
                if old[key] is None:
                    path.unlink()
                else:
                    atomic_bytes(path, old[key], modes[key])
        raise
    return {"scope": "mpw_header_only", "status": "applied", "writes_performed": True,
            "passenger_restart_required": True, "public_runtime_verified": False}


def rollback(app, backup):
    app, backup = Path(app), Path(backup)
    safe_file(backup / "record.json", required=True)
    record = json.loads((backup / "record.json").read_text(encoding="utf-8"))
    if (record.get("status") not in ("prepared", "applied") or
            set(record.get("files", {})) != {"0", "1", "2", "3"} or
            not isinstance(record.get("target"), str) or
            not re.fullmatch(r"mojplaywin-header-emblem\.[0-9a-f]{12}\.jpg", record["target"])):
        raise RuntimeError("Invalid backup record")
    static_root = app / "staticfiles"
    files = [app / "core/static" / ASSET, static_root / ASSET]
    # The target is a fixed directory plus a tightly validated recorded basename.
    # This also supports interrupted installs where the app source is still absent.
    target = static_root / "site" / record["target"]
    files += [target, static_root / "staticfiles.json"]
    previous = []
    for index, path in enumerate(files):
        safe_file(path)
        item = record["files"][str(index)]
        current = sha256(path.read_bytes()) if path.is_file() else None
        if (current != item["new"] and
                (record["status"] == "applied" or current != item["old"])):
            raise RuntimeError("Rollback refused due to concurrent change")
        data = None
        if item["existed"]:
            saved = backup / str(index)
            safe_file(saved, required=True)
            data = saved.read_bytes()
            if sha256(data) != item["old"]:
                raise RuntimeError("Backup checksum mismatch")
        previous.append((path, data, item["mode"], current))
    for path, data, mode, current in reversed(previous):
        if current == (sha256(data) if data is not None else None):
            continue
        if data is None:
            path.unlink()
        else:
            atomic_bytes(path, data, mode)
    return {"scope": "mpw_header_only", "status": "rolled_back", "passenger_restart_required": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("audit", "apply", "rollback"))
    parser.add_argument("run_id")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]{1,20}", args.run_id):
        raise SystemExit("Invalid run ID")
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise SystemExit("Wrong cPanel account")
    stage = HOME / (".mpw-header-static-stage-" + args.run_id)
    jpeg = stage / "mojplaywin-header-emblem.jpg"
    backup_root = HOME / ".mpw-header-static-backups"
    if args.mode == "audit":
        result = audit(APP, jpeg)
    else:
        if backup_root.is_symlink() or (backup_root.exists() and not backup_root.is_dir()):
            raise SystemExit("Unsafe backup root")
        backup_root.mkdir(mode=0o700, exist_ok=True)
        lock_path = backup_root / ".header-static.lock"
        if lock_path.is_symlink():
            raise SystemExit("Unsafe operation lock")
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.mode == "rollback":
                result = rollback(APP, backup_root / args.run_id)
            else:
                result = apply(APP, jpeg, backup_root / args.run_id)
        finally:
            os.close(fd)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
