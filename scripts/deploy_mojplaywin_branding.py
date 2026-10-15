#!/usr/bin/env python3
"""Safely merge the MojPlayWin changes into the shared Passenger app."""
import ast
import difflib
import json
import os
import pwd
import re
import shutil
import sys
import tempfile
from pathlib import Path

HOME = Path("/home/zomorod2")
DOCROOT = HOME / "mojplaywin.com"
APP_ROOT = HOME / "Saeit-staging"
BACKUP_ROOT = HOME / ".mojplaywin-backups"
BASELINE_ROOT = Path("deploy_baseline")
MERGED_FILES = (
    Path("config/urls.py"),
    Path("core/services_views.py"),
    Path("core/commerce_views.py"),
    Path("core/views.py"),
    Path("core/templates/base.html"),
)
OWNED_FILES = (
    Path("core/mojplaywin_views.py"),
    Path("core/templates/mojplaywin/home.html"),
    Path("core/templates/mojplaywin/store.html"),
    Path("core/templates/mojplaywin/section.html"),
)
FILES = MERGED_FILES + OWNED_FILES
ASSETS = (
    "site/heroes/research.webp", "site/heroes/game-studio.webp",
    "site/heroes/education-detail.webp", "site/heroes/store.webp",
    "site/heroes/ai.webp", "site/heroes/knowledge.webp",
    "site/heroes/agriculture.webp", "site/heroes/industry.webp",
    "site/heroes/economy.webp", "site/heroes/marketplace.webp",
    "site/heroes/platform-home.webp", "site/ghanadi/cafe.webp",
)

def safe_id(value):
    if not re.fullmatch(r"[0-9]{1,20}", str(value)):
        raise ValueError("Invalid deployment run ID")
    return str(value)

def atomic_write(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=f".{path.name}.mojplaywin-", delete=False) as stream:
        temp = Path(stream.name)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temp, mode)
    os.replace(temp, path)

def ensure_safe_path(path):
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError(f"Refusing symlink: {path}")
    current = path.parent
    while current not in (APP_ROOT, HOME, Path("/")):
        if current.is_symlink():
            raise RuntimeError(f"Refusing symlink parent: {current}")
        current = current.parent

def subsequence_positions(haystack, needle):
    if not needle:
        return []
    width = len(needle)
    return [i for i in range(len(haystack) - width + 1) if haystack[i:i+width] == needle]

def apply_three_way(base_text, desired_text, live_text, label):
    base = base_text.splitlines(keepends=True)
    desired = desired_text.splitlines(keepends=True)
    live = live_text.splitlines(keepends=True)
    changes = [op for op in difflib.SequenceMatcher(a=base, b=desired, autojunk=False).get_opcodes()
               if op[0] != "equal"]
    for tag, i1, i2, j1, j2 in reversed(changes):
        old, new = base[i1:i2], desired[j1:j2]
        if old:
            positions = subsequence_positions(live, old)
            if len(positions) == 1:
                at = positions[0]
                live[at:at+len(old)] = new
                continue
            if not positions and len(subsequence_positions(live, new)) == 1:
                continue
            raise RuntimeError(f"Safe merge conflict in {label}: expected one matching source hunk, found {len(positions)}")
        # For an insertion, locate its unique boundary using unchanged neighboring lines.
        prefix = base[max(0, i1-2):i1]
        suffix = base[i1:min(len(base), i1+2)]
        boundaries = []
        for at in range(len(live)+1):
            if prefix and live[max(0, at-len(prefix)):at] != prefix:
                continue
            if suffix and live[at:at+len(suffix)] != suffix:
                continue
            if (prefix or at == 0) and (suffix or at == len(live)):
                boundaries.append(at)
        if len(boundaries) == 1:
            live[boundaries[0]:boundaries[0]] = new
            continue
        if new and len(subsequence_positions(live, new)) == 1:
            continue
        raise RuntimeError(f"Safe merge conflict in {label}: insertion boundary is not unique")
    return "".join(live)

def restart_passenger():
    restart = DOCROOT / "tmp" / "restart.txt"
    restart.parent.mkdir(parents=True, exist_ok=True)
    restart.touch()

def rollback(run_id):
    run_id = safe_id(run_id)
    backup = BACKUP_ROOT / f"mojplaywin-main-{run_id}"
    manifest_path = backup / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        print("NO_MOJPLAYWIN_BACKUP_TO_RESTORE")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for relative in FILES:
        target = APP_ROOT / relative
        ensure_safe_path(target)
        entry = manifest[str(relative)]
        saved = backup / relative
        if entry["existed"]:
            if not saved.is_file() or saved.is_symlink():
                raise RuntimeError(f"Missing or unsafe backup: {relative}")
            atomic_write(target, saved.read_text(encoding="utf-8"), entry["mode"])
        elif target.exists():
            if target.is_dir():
                raise RuntimeError(f"Unexpected directory at target: {target}")
            target.unlink()
    restart_passenger()
    (backup / "ROLLED_BACK").write_text("yes\n", encoding="utf-8")
    print("MOJPLAYWIN_ROLLBACK_COMPLETE")

def deploy(run_id, commit_sha, stage_arg):
    run_id = safe_id(run_id)
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise ValueError("Invalid source commit")
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Unexpected cPanel account")
    if DOCROOT.is_symlink() or not DOCROOT.is_dir():
        raise RuntimeError("MojPlayWin document root is missing or redirected")
    if APP_ROOT.is_symlink() or not APP_ROOT.is_dir():
        raise RuntimeError("MojPlayWin application root is missing or redirected")
    for required in (DOCROOT / ".htaccess", DOCROOT / "passenger_wsgi.py"):
        if not required.is_file() or required.is_symlink():
            raise RuntimeError(f"Missing or unsafe MojPlayWin routing file: {required}")
    if "Saeit-staging" not in (DOCROOT / "passenger_wsgi.py").read_text(encoding="utf-8", errors="replace"):
        raise RuntimeError("Passenger no longer points to the verified Saeit-staging app")

    stage = Path(stage_arg)
    expected_stage = HOME / f".mojplaywin-main-{run_id}"
    if stage != expected_stage or stage.is_symlink() or not stage.is_dir():
        raise RuntimeError("Unexpected or unsafe staging directory")
    for relative in FILES:
        source = stage / relative
        if source.is_symlink() or not source.is_file():
            raise RuntimeError(f"Staged source missing or unsafe: {relative}")
        ensure_safe_path(APP_ROOT / relative)
    for relative in MERGED_FILES:
        baseline = stage / BASELINE_ROOT / relative
        if baseline.is_symlink() or not baseline.is_file():
            raise RuntimeError(f"Pinned baseline missing or unsafe: {relative}")
    for asset in ASSETS:
        target = APP_ROOT / "core" / "static" / asset
        if target.is_symlink() or not target.is_file():
            raise RuntimeError(f"Existing site image missing: {asset}")

    outputs = {}
    for relative in MERGED_FILES:
        source = (stage / relative).read_text(encoding="utf-8")
        baseline = (stage / BASELINE_ROOT / relative).read_text(encoding="utf-8")
        live_path = APP_ROOT / relative
        if not live_path.is_file():
            raise RuntimeError(f"Active app file is missing: {relative}")
        live = live_path.read_text(encoding="utf-8")
        outputs[relative] = apply_three_way(baseline, source, live, str(relative))
        if relative.suffix == ".py":
            ast.parse(outputs[relative], filename=str(relative))

    for relative in OWNED_FILES:
        source = (stage / relative).read_text(encoding="utf-8")
        target = APP_ROOT / relative
        if target.exists() and not target.is_file():
            raise RuntimeError(f"Unexpected directory at MojPlayWin-owned path: {relative}")
        if target.is_file():
            existing = target.read_text(encoding="utf-8", errors="replace")
            if "mojplaywin" not in existing.lower():
                raise RuntimeError(f"Refusing to replace non-MojPlayWin content: {relative}")
        outputs[relative] = source

    backup = BACKUP_ROOT / f"mojplaywin-main-{run_id}"
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("Deployment backup already exists")
    backup.mkdir(mode=0o700, parents=True)
    manifest = {}
    for relative in FILES:
        target = APP_ROOT / relative
        existed = target.is_file()
        mode = target.stat().st_mode & 0o777 if existed else 0o644
        manifest[str(relative)] = {"existed": existed, "mode": mode}
        if existed:
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
    (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    try:
        for relative in FILES:
            target = APP_ROOT / relative
            atomic_write(target, outputs[relative], manifest[str(relative)]["mode"])
        restart_passenger()
    except Exception:
        rollback(run_id)
        raise
    (backup / "DEPLOYED.json").write_text(json.dumps({"commit": commit_sha, "run_id": run_id}), encoding="utf-8")
    print(f"MOJPLAYWIN_DEPLOYED commit={commit_sha}")
    print(f"MOJPLAYWIN_BACKUP={backup}")

def main():
    if len(sys.argv) == 4 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    elif len(sys.argv) == 5 and sys.argv[1] == "deploy":
        deploy(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit("Usage: deploy RUN_ID COMMIT_SHA STAGE_DIR | rollback RUN_ID")

if __name__ == "__main__":
    main()
