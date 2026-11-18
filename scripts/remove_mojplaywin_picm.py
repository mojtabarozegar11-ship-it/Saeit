#!/usr/bin/env python3
"""One-shot, fail-closed removal of the retired PICM runtime from cPanel."""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, signal
from pathlib import Path

HOME = Path("/home/zomorod2")
ROOT = HOME / "Saeit-staging"
DOCROOT = HOME / "mojplaywin.com"
BACKUP_ROOT = HOME / ".mojplaywin-backups" / "picm-removal"

def safe_path(path: Path) -> None:
    path = path.resolve(strict=False)
    for base in (ROOT.resolve(), DOCROOT.resolve(), HOME.resolve()):
        try:
            path.relative_to(base)
            return
        except ValueError:
            pass
    raise RuntimeError("PICM_PATH_OUTSIDE_ALLOWED_ROOT")

def copy_backup(src: Path, backup: Path) -> dict:
    safe_path(src)
    if src.is_symlink():
        raise RuntimeError("PICM_SYMLINK_REFUSED:" + str(src))
    if not src.exists():
        return {"exists": False}
    backup.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, backup, symlinks=True)
    else:
        shutil.copy2(src, backup)
    data = src.read_bytes() if src.is_file() else b""
    return {"exists": True, "kind": "dir" if src.is_dir() else "file",
            "bytes": src.stat().st_size if src.is_file() else None,
            "sha256": hashlib.sha256(data).hexdigest() if data else None}

def remove_path(path: Path, backup: Path, manifest: dict) -> None:
    safe_path(path)
    rec = copy_backup(path, backup)
    manifest[str(path)] = rec
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink():
        raise RuntimeError("PICM_SYMLINK_REFUSED:" + str(path))
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()

def stop_workers() -> list[int]:
    stopped = []
    proc = Path("/proc")
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            pid = int(entry.name)
            if pid == os.getpid():
                continue
            uid = (entry / "status").read_text(errors="replace")
            if "Uid:\\t" not in uid and not uid.startswith("Uid:"):
                continue
            cmd = (entry / "cmdline").read_bytes().replace(b"\\0", b" ").decode(errors="replace")
            if "ops/picm-vps/worker.py" not in cmd:
                continue
            os.kill(pid, signal.SIGTERM)
            stopped.append(pid)
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError, OSError):
            continue
    return stopped

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--source-commit", required=True)
    a=ap.parse_args()
    if not a.run_id.isdigit() or not re.fullmatch(r"[0-9a-f]{40}", a.source_commit):
        raise SystemExit("PICM_INVALID_INPUT")
    if os.geteuid() != 1003 and os.environ.get("USER") not in ("zomorod2", ""):
        raise SystemExit("PICM_WRONG_ACCOUNT")
    if ROOT.is_symlink() or DOCROOT.is_symlink():
        raise SystemExit("PICM_UNSAFE_APP_ROOT")
    if not ROOT.is_dir() or not DOCROOT.is_dir():
        raise SystemExit("PICM_APP_ROOT_MISSING")
    backup=BACKUP_ROOT / a.run_id
    if backup.exists() or backup.is_symlink():
        raise SystemExit("PICM_BACKUP_COLLISION")
    backup.mkdir(mode=0o700, parents=True)
    manifest={"operation":"PICM_FULL_REMOVAL","source_commit":a.source_commit,
              "run_id":a.run_id,"targets":{}}
    stopped=stop_workers()
    manifest["stopped_worker_pids"]=stopped
    urls=ROOT/"config/urls.py"
    if urls.exists():
        text=urls.read_text(encoding="utf-8")
        markers=("SAEIT_PICM_V1_OWNER_SCOPED_ROUTES","SAEIT_PICM_PRIVATE_LOGIN_V1",
                 "SAEIT_PICM_WORKSPACE_V1","SAEIT_PICM_REFERENCE_UPLOAD_V1",
                 "MOJPLAYWIN_PRIVATE_MEDIA_OWNER_V1")
        if any(m in text for m in markers):
            pos=[text.find(m) for m in markers if m in text]
            cut=text.rfind("\n#",0,min(pos)+1)+1 if min(pos)>0 else min(pos)
            tail=text[cut:]
            if any(line.strip() and "picm" not in line.casefold() for line in tail.splitlines()):
                raise SystemExit("PICM_UNEXPECTED_CONFIG_TAIL")
            new=text[:cut].rstrip()+"\n"
            remove_path(urls, backup/"config/urls.py", manifest["targets"])
            urls.parent.mkdir(parents=True,exist_ok=True)
            urls.write_text(new,encoding="utf-8")
            manifest["targets"][str(urls)]["post_action"]="rewritten_without_picm_routes"
        elif "picm" in text.casefold():
            raise SystemExit("PICM_UNMARKED_CONFIG_REFERENCE")
    candidates=[
      ROOT/"core/picm_access.py",ROOT/"core/picm_auth.py",ROOT/"core/picm_storyboard.py",
      ROOT/"core/picm_views.py",ROOT/"core/private_media_library.py",
      ROOT/"templates/picm",ROOT/"ops/picm-gpu",ROOT/"ops/picm-vps",
      ROOT/"scripts/deploy_mojplaywin_picm.py",ROOT/"scripts/deploy_picm_login.py",
      ROOT/"scripts/deploy_private_media.py",
      ROOT/"runtime/retired_picm_manifest.json",
      ROOT/"scripts/mpw_retired_subsite_policy.py",
      ROOT/"tests/test_mpw_retired_picm_policy_c101_20261116.py",
      HOME/".picm-queue",HOME/".private-media-library",
      HOME/".local/share/saeit-picm",
      DOCROOT/"picm",
    ]
    for base in (ROOT/"scripts",ROOT/"tests",ROOT/".github/workflows"):
        if base.is_dir():
            for p in base.iterdir():
                if p.name.lower().startswith("picm") or p.name.lower().startswith("deploy_picm"):
                    candidates.append(p)
    seen=set()
    for p in candidates:
        if str(p) in seen: continue
        seen.add(str(p))
        remove_path(p,backup/"targets"/p.name,manifest["targets"])
    for restart_root in (ROOT,DOCROOT):
        if not restart_root.is_symlink():
            tmp=restart_root/"tmp"
            tmp.mkdir(exist_ok=True)
            (tmp/"restart.txt").touch()
    (backup/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"PICM_REMOVAL":"PASS","backup":str(backup),
                      "stopped_worker_pids":stopped,
                      "target_count":len(manifest["targets"])},ensure_ascii=False))

if __name__=="__main__":
    main()
