#!/usr/bin/env python3
"""Additive, fail-closed, reversible publication of an owned Arcade Lab static release."""
import json, os, pwd, re, shutil, sys
from pathlib import Path

HOME = Path("/home/zomorod2")
SITE = HOME / "mojplaywin.com"
PARENT = SITE / "mpw-editorial" / "arcade-lab"
DEST = PARENT / "20261022"
OWNER = ".mpw-arcade-owner.json"

def inspect():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Unexpected cPanel user")
    if SITE.is_symlink() or not SITE.is_dir():
        raise RuntimeError("Unexpected site root")
    if not (SITE / ".htaccess").is_file() or not (SITE / "passenger_wsgi.py").is_file():
        raise RuntimeError("MojPlayWin site identity not confirmed")
    editorial = SITE / "mpw-editorial"
    if editorial.is_symlink() or not editorial.is_dir() or not (editorial / "index.html").is_file():
        raise RuntimeError("Existing isolated static editorial path not confirmed")
    if PARENT.is_symlink() or (PARENT.exists() and not PARENT.is_dir()):
        raise RuntimeError("Unsafe or modified parent")
    if DEST.is_symlink():
        raise RuntimeError("Symlink destination refused")

def valid(run, sha):
    if not re.fullmatch(r"[0-9]{8,20}", run) or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("Invalid run or commit identity")

def deploy(run, sha):
    valid(run, sha)
    inspect()
    src = HOME / (".mpw-arcade-" + run) / "payload"
    if not src.is_dir() or src.is_symlink() or any(x.is_symlink() for x in src.rglob("*")):
        raise RuntimeError("Missing or unsafe source")
    html = list(src.rglob("*.html"))
    imgs = list(src.rglob("*.webp"))
    scripts = list(src.rglob("*.js"))
    if (len(html), len(imgs), len(scripts)) != (55, 3, 2):
        raise RuntimeError("Unexpected release file counts")
    if any(x.stat().st_size > 60000 for x in imgs):
        raise RuntimeError("Oversized public WebP image")
    if any(x.stat().st_size > 300000 for x in src.rglob("*") if x.is_file()):
        raise RuntimeError("Unexpectedly large public file")
    manifest = json.loads((src / "release.json").read_text())
    if manifest.get("git_sha") != sha or manifest.get("html_count") != 55:
        raise RuntimeError("Release identity mismatch")
    for p in ["index.html", "guides/index.html", "guides/01/index.html",
              "guides/50/index.html", "circuit-courier/index.html",
              "economy-simulator/index.html", "qa-matrix/index.html"]:
        if not (src / p).is_file():
            raise RuntimeError("Missing page " + p)
    if DEST.exists() or DEST.is_symlink():
        raise RuntimeError("Release path already occupied; refuse overwrite")
    PARENT.mkdir(exist_ok=True)
    pending = PARENT / (".pending-" + run)
    if pending.exists() or pending.is_symlink():
        raise RuntimeError("Pending path occupied")
    try:
        shutil.copytree(src, pending)
        (pending / ".htaccess").write_text("PassengerEnabled off\nDirectoryIndex index.html\nOptions -Indexes\n")
        (pending / OWNER).write_text(json.dumps({"run_id": run, "git_sha": sha, "owner": "mpw-arcade-lab-v1"}))
        for p in pending.rglob("*"):
            p.chmod(0o755 if p.is_dir() else 0o644)
        if DEST.exists() or DEST.is_symlink():
            raise RuntimeError("Concurrent release; do not overwrite")
        pending.rename(DEST)
    finally:
        if pending.is_dir() and not pending.is_symlink():
            shutil.rmtree(pending)
    print("STATIC_ARCADE_DEPLOYED", sha, len(html), len(imgs))

def rollback(run, sha):
    valid(run, sha)
    inspect()
    marker = DEST / OWNER
    if not marker.is_file() or marker.is_symlink():
        raise RuntimeError("No release ownership marker; refuse rollback")
    if json.loads(marker.read_text()) != {"run_id": run, "git_sha": sha, "owner": "mpw-arcade-lab-v1"}:
        raise RuntimeError("Ownership mismatch; refuse rollback")
    private = HOME / ".mpw-arcade-failed-releases"
    private.mkdir(mode=0o700, exist_ok=True)
    quarantine = private / ("failed-" + run)
    if quarantine.exists():
        raise RuntimeError("Quarantine collision")
    DEST.rename(quarantine)
    print("OWNED_RELEASE_QUARANTINED", quarantine)

if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in ("deploy", "rollback"):
        raise SystemExit("Usage: deploy|rollback RUN_ID GIT_SHA")
    {"deploy": deploy, "rollback": rollback}[sys.argv[1]](sys.argv[2], sys.argv[3])
