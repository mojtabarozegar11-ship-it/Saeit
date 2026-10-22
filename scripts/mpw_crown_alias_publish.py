#!/usr/bin/env python3
"""Install only an isolated Crown Defender spelling-alias directory on cPanel.

No shared .htaccess, application, database, payment or canonical game edit.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import sys

HOME = Path("/home/zomorod2")
DOCUMENT_ROOT = HOME / "mojplaywin.com"
PARENT = DOCUMENT_ROOT / "games"
TARGET = PARENT / "corwn-defender"
SNAPSHOTS = HOME / ".mpw-crown-alias-receipts"
FILES = ("index.html", ".htaccess")


def checksum(value):
    return hashlib.sha256(value).hexdigest()


def stop(reason):
    raise RuntimeError("CROWN_ALIAS_SAFE_ABORT: " + reason)


def paths(run):
    if not re.fullmatch(r"[0-9]{8,16}", run):
        stop("Invalid run")
    return (HOME / (".mpw-crown-alias-stage-" + run),
            SNAPSHOTS / ("alias-" + run + ".json"))


def verify_scope():
    for path in (DOCUMENT_ROOT, PARENT):
        if not path.is_dir() or path.is_symlink():
            stop("Expected existing non-symlink directory: " + str(path))
    if TARGET.is_symlink():
        stop("Target symlink prohibited")


def checked_stage(run, sha_html, sha_rules):
    if any(not re.fullmatch(r"[0-9a-f]{64}", sha) for sha in (sha_html, sha_rules)):
        stop("Invalid digest")
    stage, manifest = paths(run)
    if not stage.is_dir() or stage.is_symlink():
        stop("Private staging directory unavailable")
    expected = {"index.html": sha_html, ".htaccess": sha_rules}
    if {p.name for p in stage.iterdir()} != set(FILES):
        stop("Staging contains unexpected files")
    for name, sha in expected.items():
        f = stage / name
        if not f.is_file() or f.is_symlink() or checksum(f.read_bytes()) != sha:
            stop("Staging digest mismatch: " + name)
    html = (stage / "index.html").read_text("utf-8")
    rules = (stage / ".htaccess").read_text("utf-8")
    if ('href="https://mojplaywin.com/games/crown-defender/"' not in html
            or "url=/games/crown-defender/" not in html
            or "RedirectMatch 301 ^/games/corwn-defender/?$ /games/crown-defender/" not in rules):
        stop("Alias destination mismatch")
    return stage, manifest, expected


def verify_target(expected):
    if TARGET.is_symlink() or not TARGET.is_dir():
        stop("Alias target missing")
    if {p.name for p in TARGET.iterdir()} != set(FILES):
        stop("Alias directory contains unrecognized files")
    for name, sha in expected.items():
        path = TARGET / name
        if not path.is_file() or path.is_symlink() or checksum(path.read_bytes()) != sha:
            stop("Alias was changed since deployment")


def install(run, sha_html, sha_rules):
    verify_scope()
    stage, manifest, expected = checked_stage(run, sha_html, sha_rules)
    if TARGET.exists() or TARGET.is_symlink() or manifest.exists():
        stop("Pre-existing alias/receipt; never overwrite")
    SNAPSHOTS.mkdir(mode=0o700, exist_ok=True)
    if SNAPSHOTS.is_symlink():
        stop("Unsafe receipts directory")
    record = json.dumps({"run": run, "files": expected,
                         "target": str(TARGET), "status": "staged"}, sort_keys=True)
    with manifest.open("x", encoding="utf-8") as f:
        os.fchmod(f.fileno(), 0o600)
        f.write(record)
        f.flush()
        os.fsync(f.fileno())
    TARGET.mkdir(mode=0o755)
    try:
        for name in FILES:
            with (TARGET / name).open("xb") as f:
                os.fchmod(f.fileno(), 0o644)
                f.write((stage / name).read_bytes())
                f.flush()
                os.fsync(f.fileno())
        verify_target(expected)
    except BaseException:
        # Only remove exact staged bytes, and only within our newly created alias.
        for name in FILES:
            dest = TARGET / name
            if dest.exists() and dest.is_file() and not dest.is_symlink():
                if checksum(dest.read_bytes()) == expected[name]:
                    dest.unlink()
        if TARGET.is_dir() and not list(TARGET.iterdir()):
            TARGET.rmdir()
        raise
    record = json.dumps({"run": run, "files": expected,
                         "target": str(TARGET), "status": "installed"}, sort_keys=True)
    manifest.write_text(record, encoding="utf-8")
    os.chmod(manifest, stat.S_IRUSR | stat.S_IWUSR)
    print("CROWN_ALIAS_INSTALLED_ONLY=" + str(TARGET))


def status(run):
    verify_scope()
    _, manifest = paths(run)
    if not manifest.is_file() or manifest.is_symlink():
        stop("Missing receipt")
    data = json.loads(manifest.read_text("utf-8"))
    if data.get("status") != "installed" or data.get("target") != str(TARGET):
        stop("Wrong receipt")
    verify_target(data["files"])
    print("CROWN_ALIAS_VERIFIED=YES")


def rollback(run):
    verify_scope()
    _, manifest = paths(run)
    if not manifest.is_file() or manifest.is_symlink():
        stop("Missing receipt")
    data = json.loads(manifest.read_text("utf-8"))
    if data.get("target") != str(TARGET):
        stop("Wrong target")
    if TARGET.exists():
        verify_target(data["files"])
        for name in FILES:
            (TARGET / name).unlink()
        TARGET.rmdir()
    print("CROWN_ALIAS_ROLLBACK_ONLY=YES")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 4 and args[0] == "install":
        install(args[1], args[2], args[3])
    elif len(args) == 2 and args[0] == "status":
        status(args[1])
    elif len(args) == 2 and args[0] == "rollback":
        rollback(args[1])
    else:
        stop("Usage: install RUN HTML_SHA RULES_SHA | status RUN | rollback RUN")
