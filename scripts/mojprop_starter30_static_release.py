#!/usr/bin/env python3
"""Dedicated one-time *static-only* Starter30 deployment, never backend/payment.

Runs only as the actual cPanel tenant after independent host/backups are proven.
Does not run by itself, and is not triggered by push, PR or GitHub Actions.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import tempfile

HOME = Path("/home/zomorod2")
ROOT = HOME / "mojplaywin.com"
TARGET = ROOT / "moj-prop/starter-30-trx"
BACKUP = HOME / ".mojprop-starter30-backups"
FILES = ("index.html", "journal-template.csv", "journal-guide.txt")
# Exact Git blob identities read from the current reviewed main source.
# The owner must explicitly review/re-pin any revision; do not trust staged
# tarballs or a caller-supplied commit string as proof of identical bytes.
REVIEWED_GIT_BLOBS = {
    "index.html": "443581774a7b56f8b4bbaaf3fd8c7531da2ffbc7",
    "journal-template.csv": "2d732321f1c1f431685e514789cf26bf2a977d84",
    "journal-guide.txt": "7a8978ca6f3db31064552a41b2bdfb6c7de56036",
}
MAX_STAGE_FILE_BYTES = 90_000
RUN_ID_RE = re.compile(r"[1-9][0-9]{0,18}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_id(run_id: str, commit: str) -> None:
    if not RUN_ID_RE.fullmatch(run_id) or not COMMIT_RE.fullmatch(commit):
        raise ValueError("invalid pinned run or commit")


def _check_ancestors(root: Path, path: Path) -> None:
    if not path.is_relative_to(root) or path == root:
        raise RuntimeError("out-of-scope path")
    cursor = path
    while cursor != root:
        if cursor.is_symlink():
            raise RuntimeError("symlink under managed route")
        cursor = cursor.parent
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("untrusted root")


def _host() -> None:
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("wrong tenant account")
    for p in (ROOT, ROOT / ".htaccess", ROOT / "passenger_wsgi.py", ROOT / "moj-prop"):
        _check_ancestors(HOME, p)
        if not p.exists() or p.is_symlink():
            raise RuntimeError("unverified cPanel root: " + str(p))
    if not ROOT.is_dir():
        raise RuntimeError("invalid docroot")


def _atomic(path: Path, data: bytes, mode: int = 0o644) -> None:
    _check_ancestors(ROOT, path)
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=str(path.parent), prefix=".mojprop-starter-")
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        # Atomic create-if-absent: os.replace would clobber a file added
        # between preflight and publication (TOCTOU). Both files share one
        # directory/filesystem, so hard-link creation fails when it exists.
        os.link(temporary, path, follow_symlinks=False)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _private_backup_root(*, create: bool) -> None:
    """Never chmod/follow an existing backup root or accept unknown owner bytes.

    A previous installer used BACKUP.mkdir(..., exist_ok=True) followed by
    os.chmod(BACKUP, 0700). If BACKUP were a symlink, chmod could change
    permissions of an unrelated directory. Deny instead of repairing it.
    """
    parent = BACKUP.parent
    if parent.is_symlink() or not parent.is_dir():
        raise RuntimeError("untrusted backup parent")
    parent_mode = parent.lstat()
    if (not stat.S_ISDIR(parent_mode.st_mode)
            or parent_mode.st_uid != os.geteuid()
            or parent_mode.st_mode & stat.S_IWOTH):
        raise RuntimeError("untrusted backup parent owner or mode")
    if BACKUP.is_symlink():
        raise RuntimeError("symlinked backup directory")
    if BACKUP.exists():
        state = BACKUP.lstat()
        if (not stat.S_ISDIR(state.st_mode)
                or state.st_uid != os.geteuid()
                or state.st_mode & 0o077):
            raise RuntimeError("existing private backup root is not safe")
    elif create:
        BACKUP.mkdir(mode=0o700)
    else:
        raise RuntimeError("required private backup does not exist")


def _stage(run_id: str) -> Path:
    return HOME / (".mojprop-starter30-stage-" + run_id) / "templates/moj-prop-v4/starter-30-trx"


def _stage_bytes(run_id: str) -> dict[str, bytes]:
    stage = _stage(run_id)
    if stage.is_symlink() or not stage.is_dir():
        raise RuntimeError("missing staged product")
    out: dict[str, bytes] = {}
    for item in FILES:
        p = stage / item
        if p.is_symlink() or not p.is_file():
            raise RuntimeError("missing staged deliverable: " + item)
        if p.stat().st_size < 10 or p.stat().st_size > 90_000:
            raise RuntimeError("invalid staged asset size")
        out[item] = p.read_bytes()
    page = out["index.html"].decode("utf-8")
    if ('MOJPROP-STARTER30' not in page or 'Payment not enabled' not in page
            or 'noindex,follow' not in page or 'Do not send TRX' not in page
            or b"session,closing_equity_usd,risk_plan_recorded,reflection_recorded" not in out["journal-template.csv"]):
        raise RuntimeError("staged product does not meet the no-payment scope")
    return out


def _manifest(run_id: str, commit: str, source: dict[str, bytes]) -> dict:
    _safe_id(run_id, commit)
    return {"schema": "mojprop.starter30.static.v1", "run_id": run_id,
            "commit": commit, "files": {name: sha(data) for name, data in source.items()},
            "scope": "static-no-payment-no-backend"}


def preflight(run_id: str, commit: str) -> dict:
    _safe_id(run_id, commit)
    _host()
    data = _stage_bytes(run_id)
    for name in FILES:
        target = TARGET / name
        _check_ancestors(ROOT, target)
        if target.is_symlink() or target.exists():
            raise RuntimeError("unexpected existing target; refuse overwrite: " + name)
    return _manifest(run_id, commit, data)


def deploy(run_id: str, commit: str) -> None:
    if os.environ.get("MOJPROP_STARTER30_OWNER_APPROVED") != "static-only-approved":
        raise RuntimeError("explicit per-release approval missing")
    manifest = preflight(run_id, commit)
    data = _stage_bytes(run_id)
    location = BACKUP / run_id
    if location.exists() or location.is_symlink():
        raise RuntimeError("run id already used")
    _private_backup_root(create=True)
    location.mkdir(mode=0o700)
    manifest_path = location / "manifest.json"
    with manifest_path.open("x", encoding="utf-8") as output:
        json.dump(manifest, output, sort_keys=True)
        output.flush()
        os.fsync(output.fileno())
    os.chmod(manifest_path, 0o600)
    try:
        for name in FILES:
            _atomic(TARGET / name, data[name])
        for name, expected in manifest["files"].items():
            if sha((TARGET / name).read_bytes()) != expected:
                raise RuntimeError("public asset verification failed: " + name)
    except BaseException:
        rollback(run_id, commit)
        raise
    print("STARTER30_STATIC_RELEASE=PASS; PAYMENT=LOCKED; DB=UNTOUCHED")


def rollback(run_id: str, commit: str) -> None:
    _safe_id(run_id, commit)
    _host()
    _private_backup_root(create=False)
    location = BACKUP / run_id
    manifest_path = location / "manifest.json"
    if location.is_symlink() or manifest_path.is_symlink() or not manifest_path.is_file():
        raise RuntimeError("unverified backup manifest")
    if (location.stat().st_mode & 0o077) or (manifest_path.stat().st_mode & 0o077):
        raise RuntimeError("unprotected backup manifest")
    manifest = json.loads(manifest_path.read_text("utf-8"))
    if (manifest.get("schema") != "mojprop.starter30.static.v1"
            or manifest.get("run_id") != run_id or manifest.get("commit") != commit
            or set(manifest.get("files", {})) != set(FILES)
            or manifest.get("scope") != "static-no-payment-no-backend"):
        raise RuntimeError("manifest cannot authorize rollback")
    for name, expected in manifest["files"].items():
        path = TARGET / name
        _check_ancestors(ROOT, path)
        if path.is_symlink():
            raise RuntimeError("unsafe symlink during rollback")
        if path.exists() and (not path.is_file() or sha(path.read_bytes()) != expected):
            raise RuntimeError("live asset changed; refuse to delete")
    for name in FILES:
        (TARGET / name).unlink(missing_ok=True)
    print("STARTER30_STATIC_ROLLBACK=PASS; DB=UNTOUCHED")


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in ("preflight", "deploy", "rollback"):
        raise SystemExit("usage: script.py preflight|deploy|rollback RUN_ID COMMIT")
    action, run, revision = sys.argv[1:]
    if action == "preflight":
        print(json.dumps(preflight(run, revision), sort_keys=True))
    elif action == "deploy":
        deploy(run, revision)
    else:
        rollback(run, revision)
